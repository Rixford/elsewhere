import copy
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from engine import Engine, Cancelled, GENERATE, REVIEW
from sanitize import sanitize

ROOT = Path(__file__).resolve().parent
TERMINAL = {'done','error','cancelled'}

def atomic_json(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)

def site_identity(page):
    """An immutable seed carried by descendants, independent of recent siblings."""
    if isinstance(page.get('site'),dict): return copy.deepcopy(page['site'])
    css=re.findall(r'<style[^>]*>(.*?)</style>',page.get('html',''),re.S|re.I)
    # Saved HTML begins with host defaults; the model's CSS follows them.
    return {'root_page':page.get('id'),'entry':page.get('prompt',''),'title':page.get('title',''),
            'content':page.get('text','')[:3000], 'style_css':'\n'.join(css[1:] if len(css)>1 else css)[:3000]}

class App:
    def __init__(self, data, start_engine=True):
        self.data = Path(data)
        self.data.mkdir(parents=True, exist_ok=True)
        (self.data / 'pages').mkdir(exist_ok=True)
        (self.data / 'exports').mkdir(exist_ok=True)
        (self.data / 'cache').mkdir(exist_ok=True)
        (self.data / 'bookmarks').mkdir(exist_ok=True)
        # Expire only the explicitly temporary cache, never the legacy archive.
        cutoff = time.time() - 86400
        for path in (self.data/'cache').glob('*.json'):
            if path.stat().st_mtime < cutoff:
                path.unlink()
        self.engine = Engine(data)
        self.token = secrets.token_urlsafe(32)
        self.script_nonce = secrets.token_urlsafe(24)
        self.lock = threading.RLock()
        self.jobs = {}
        self.active = None
        self.stopped = False
        self.capture = None
        self.guard_status = 'browser'
        self.blocked_requests = 0
        self.settings = {'memory': True, 'visual': True, 'review': True}
        self.domains = {}
        self.pages = []
        self.bookmarks = {}
        for path in (self.data/'bookmarks').glob('*.json'):
            if path.name.endswith('.trace.json'): continue
            try:
                page=json.loads(path.read_text(encoding='utf-8'))
                self.bookmarks[page['id']]={k:page[k] for k in ('id','title','prompt','created')}
            except (OSError,ValueError,KeyError): pass
        for name, default in [('settings',self.settings),('domains',{}),('history',[])]:
            try:
                value = json.loads((self.data / f'{name}.json').read_text(encoding='utf-8'))
                if isinstance(value, type(default)):
                    if name == 'settings':
                        self.settings.update({k:bool(value[k]) for k in self.settings if k in value})
                    elif name == 'domains': self.domains = value
                    else: self.pages = [p for p in value if self.page_path(p.get('id','')) is not None][:300]
            except (OSError,ValueError):
                pass
        self.server = ThreadingHTTPServer(('127.0.0.1',0), self.handler())
        self.server.daemon_threads = True
        self.origin = f'http://127.0.0.1:{self.server.server_port}'
        self.url = self.origin + '/#' + self.token
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        if start_engine:
            threading.Thread(target=self.engine.start, daemon=True).start()

    def status(self):
        if self.engine.state=='ready' and self.engine.process and self.engine.process.poll() is not None:
            self.engine.state='error'
            self.engine.error='The local model stopped. Close and reopen Elsewhere to reload it.'
        with self.lock: bookmarks=list(self.bookmarks.values())
        return {'engine':self.engine.state, 'error':self.engine.error, 'model':'Qwen3.5 · 4B', 'settings':self.settings, 'active':self.active, 'history':self.pages, 'bookmarks':bookmarks, 'data_path':str(self.data), 'guards':self.guard_status, 'blocked_requests':self.blocked_requests}

    def page_path(self, page_id):
        if not re.fullmatch(r'[0-9a-f]{32}',str(page_id)): return None
        for folder in ('bookmarks','cache','pages'):
            path=self.data/folder/f'{page_id}.json'
            if path.exists(): return path
        return None

    def bookmark(self, page_id, enabled):
        with self.lock:
            page=self.load_page(page_id)
            source=self.page_path(page_id)
            target=self.data/'bookmarks'/f'{page_id}.json'
            trace=source.with_name(f'{page_id}.trace.json')
            if enabled:
                atomic_json(target,page)
                if trace.exists(): atomic_json(target.with_name(trace.name),json.loads(trace.read_text(encoding='utf-8')))
                self.bookmarks[page_id]={k:page[k] for k in ('id','title','prompt','created')}
            elif target.exists():
                # Unbookmark returns the snapshot to cache, preserving Back.
                atomic_json(self.data/'cache'/target.name,page)
                saved_trace=target.with_name(f'{page_id}.trace.json')
                if saved_trace.exists():
                    atomic_json(self.data/'cache'/saved_trace.name,json.loads(saved_trace.read_text(encoding='utf-8')))
                    saved_trace.unlink()
                target.unlink()
                self.bookmarks.pop(page_id,None)
        return {'bookmarked':enabled}

    def snapshot(self, job):
        with self.lock:
            return copy.deepcopy({k:v for k,v in job.items() if k not in ('cancel','rendered','thread','raw','context')})

    def cancel(self, job_id):
        job = self.jobs.get(job_id)
        if job and job['state'] not in TERMINAL:
            job['cancel'].set()
            job['rendered'].set()
            self.engine.interrupt()
            job['state'] = 'cancelled'

    def start_job(self, body):
        prompt = body.get('prompt', '')
        if not isinstance(prompt,str) or not prompt.strip() or len(prompt) > 1200:
            raise ValueError('Enter between 1 and 1,200 characters.')
        if self.engine.state != 'ready':
            raise ValueError(self.engine.error or 'The local model is still loading.')
        with self.lock:
            if self.active and self.jobs[self.active]['state'] in TERMINAL:
                self.jobs[self.active]['thread'].join(timeout=1)
            if self.active and self.jobs[self.active]['thread'].is_alive():
                raise ValueError('Stop the current generation before starting another.')
            # At most eight live job records; complete traces are on disk.
            for key in list(self.jobs)[:-7]:
                if self.jobs[key]['state'] in TERMINAL:
                    del self.jobs[key]
            parent = self.load_page(body.get('parent','')) if self.settings['memory'] and body.get('parent') else None
            entry = prompt.strip()
            domain=None
            if re.match(r'^(?:https?://)?[\w-]+(?:\.[\w-]+)+(?:[/?:#]|$)',entry):
                try:domain=urlsplit(entry if '://' in entry else 'https://'+entry).hostname
                except ValueError:pass  # Even malformed addresses remain valid creative prompts.
            key = domain or (parent.get('world') if parent else 'world-' + uuid.uuid4().hex[:12])
            # A fresh address should recall the model's associations, not inherit an
            # unrelated interpretation previously saved for that domain.
            context = None
            if parent:
                root=parent
                root_entries=(str(key).lower(), 'https://'+str(key).lower(), 'http://'+str(key).lower())
                if not parent.get('site') and parent.get('prompt','').lower().rstrip('/') not in root_entries:
                    # Recover the seed for pre-update pages where only the world
                    # domain survived, rather than promoting a drifting child.
                    for item in self.pages:
                        if item.get('created',0)>parent.get('created',float('inf')): continue
                        if str(item.get('prompt','')).lower().rstrip('/') in root_entries:
                            try: root=self.load_page(item['id'])
                            except (ValueError,OSError): pass
                            else: break
                link=body.get('link') or {}
                if not isinstance(link,dict): raise ValueError('Expected link context.')
                link={k:v[:limit] for k,limit in [('label',200),('destination',500),('excerpt',1000)] if isinstance((v:=link.get(k)),str)}
                context = {'site':site_identity(root),'previous_entry':parent['prompt'],'previous_title':parent['title'],'previous_content':parent.get('text','')[:1800], 'clicked_link':link}
                destination=link.get('destination','')
                linked_domain=None
                if re.match(r'^https?://',destination,re.I):
                    try: linked_domain=urlsplit(destination).hostname
                    except ValueError: pass
                # An explicit external destination starts another imagined site.
                external=linked_domain or domain
                if external and external!=parent.get('world'):
                    context=None
                    key=external
                    if linked_domain and not domain: entry=f'{destination} — {entry}'
                else: key=parent.get('world') or key
            seed = body.get('seed')
            if not isinstance(seed,int) or not 0 <= seed <= 2147483647:
                seed = secrets.randbelow(2147483647)
            jid = uuid.uuid4().hex
            job = {'id':jid,'prompt':entry,'world':key,'seed':seed,'state':'generating','stage':'Imagining your page','chars':0,'started':time.time(),'revision':0,'page':None,'review':None,'error':'','settings':dict(self.settings),'context':context,'cancel':threading.Event(),'rendered':threading.Event(),'layout':{},'repair':False}
            self.jobs[jid] = job
            self.active = jid
            worker = threading.Thread(target=self.run_job,args=(job,),daemon=True)
            job['thread'] = worker
            worker.start()
            return {'id':jid}

    def set_page(self, job, raw):
        capability=secrets.token_urlsafe(24)
        page = sanitize(raw, capability, job['prompt'][:80], self.script_nonce)
        job['raw'] = raw
        job['revision'] += 1
        # The capability is carried separately for the trusted shell's message checks.
        page['capability'] = capability
        job['rendered'].clear()
        job['layout'] = {}
        job['page'] = page
        return page

    def wait_render(self, job):
        deadline = time.monotonic() + 30
        while not job['rendered'].wait(.1) and time.monotonic() < deadline:
            if job['cancel'].is_set(): raise Cancelled()
        if job['cancel'].is_set(): raise Cancelled()
        if not job['rendered'].is_set():
            raise ValueError('The browser did not return layout measurements within 30 seconds. Keep the app open and try again; the model already produced a page.')

    def run_job(self, job):
        trace = {'id':job['id'],'prompt':job['prompt'],'seed':job['seed'],'world':job['world'],'settings':job['settings'],'context':job['context'],'model':'Qwen3.5-4B-Q4_K_M','runtime':'llama.cpp b11007','started':job['started']}
        trace.update(generator_instructions=GENERATE,reviewer_instructions=REVIEW,sampling={'temperature':.9,'repair_temperature':.35,'review_temperature':.1,'top_p':.92,'top_k':40,'max_output_tokens':5200,'context_tokens':16384})
        try:
            progress = lambda n: job.update(chars=n)
            raw, stats = self.engine.generate(job['prompt'],job['context'],job['cancel'],job['seed'],progress)
            trace['original_html'] = raw
            trace['generation'] = stats
            issues = []
            structural_issues = False
            try:
                page = self.set_page(job,raw)
                if stats['finish'] == 'length' and '</html>' not in raw.lower():
                    issues.append('The HTML was truncated. Finish the entire page within the output budget, making it shorter.')
            except ValueError as exc:
                page = None
                issues.append(str(exc))
            if page:
                job.update(state='reviewing',stage='Checking layout')
                self.wait_render(job)
                issues.extend(page['issues'])
                if job['layout'].get('overflow'):
                    issues.append('Horizontal overflow at viewport width ' + str(job['layout'].get('width')))
                structural_issues = bool(issues)
                screenshot = None
                if job['settings']['visual'] and self.capture and job['rendered'].is_set():
                    try:
                        screenshot = self.capture(job['id'], job['revision'])
                    except Exception as exc:
                        trace['capture_error'] = str(exc)[:300]
                if job['settings']['review']:
                    job['stage'] = 'Reviewing visuals and language' if screenshot else 'Reviewing language and structure'
                    try:
                        review = self.engine.review(page,job['layout'],screenshot,job['cancel'])
                    except Cancelled:
                        raise
                    except Exception as exc:
                        review = {'issues':[],'summary':'Model review unavailable: '+str(exc)[:160],'visual':False,'unavailable':True}
                    job['review'] = review
                    trace['review'] = review
                    issues.extend(x['detail'] for x in review['issues'] if x['severity'] == 'error')
            if issues:
                job.update(state='repairing', stage='Refining presentation', repair=True, chars=0)
                if page and not structural_issues:
                    try:
                        raw, stats = self.engine.patch(raw,issues[:4],job['cancel'],job['seed'])
                        trace['repair_mode'] = 'targeted'
                    except ValueError as exc:
                        # A failed cosmetic patch must not discard a structurally
                        # usable page or force another expensive model call.
                        trace['patch_warning'] = str(exc)
                        job['review']['summary'] += ' Targeted refinement could not be applied; original retained.'
                        job['repair'] = False
                else:
                    raw, stats = self.engine.generate(job['prompt'],job['context'],job['cancel'],job['seed'],progress,repair={'raw':raw,'issues':issues[:6]})
                    trace['repair_mode'] = 'full'
                trace['repair_html'] = raw
                trace['repair_reasons'] = issues
                trace['repair_stats'] = stats
                page = self.set_page(job, raw)
                job.update(state='reviewing',stage='Checking the refinement')
                self.wait_render(job)
                if (stats['finish'] == 'length' and '</html>' not in raw.lower()) or job['layout'].get('overflow') or page['issues']:
                    raise ValueError('The page still has a layout or structure problem after one refinement. Your previous page is preserved; try Reimagine.')
            if job['cancel'].is_set(): raise Cancelled()
            if not page: raise ValueError('No usable page was produced.')
            result = {**page,'id':job['id'],'prompt':job['prompt'],'world':job['world'],'seed':job['seed'],'created':time.time(),'seconds':round(time.time()-job['started'],1),'review':job['review'],'repaired':job['repair'],'settings':job['settings'],'layout':job['layout']}
            result['site']=copy.deepcopy(job['context']['site']) if job['context'] else site_identity(result)
            result['parent']=job['context']['previous_entry'] if job['context'] else None
            with self.lock:
                if job['cancel'].is_set(): raise Cancelled()
                atomic_json(self.data/'cache'/f"{job['id']}.json",result)
                self.pages.insert(0,{k:result[k] for k in ('id','title','prompt','created','seconds','seed')})
                self.pages = self.pages[:300]
                atomic_json(self.data/'history.json',self.pages)
                if job['settings']['memory']:
                    self.domains[job['world']] = {'title':page['title'],'established_content':page['text'][:2000], 'style_hint':re.search(r'<style[^>]*>(.*?)</style>',raw,re.S).group(1)[:1200] if re.search(r'<style[^>]*>(.*?)</style>',raw,re.S) else ''}
                    self.domains = dict(list(self.domains.items())[-80:])
                    atomic_json(self.data/'domains.json',self.domains)
                job.update(state='done',stage='Ready',result=result)
        except Cancelled:
            job.update(state='cancelled',stage='Stopped')
        except Exception as exc:
            job.update(state='error',stage='Could not finish this page',error=str(exc))
        finally:
            trace.update(state=job['state'],error=job['error'],seconds=round(time.time()-job['started'],2))
            atomic_json(self.data/'cache'/f"{job['id']}.trace.json",trace)

    def load_page(self, page_id):
        if not re.fullmatch(r'[0-9a-f]{32}',str(page_id)):
            raise ValueError('Invalid page ID.')
        path=self.page_path(page_id)
        if path is None: raise ValueError('This temporary page has expired. Bookmarks remain available.')
        page = json.loads(path.read_text(encoding='utf-8'))
        # Reapply current containment and controller fixes to old snapshots. The
        # original trace remains unchanged for reproducibility.
        trace_path = path.with_name(f'{page_id}.trace.json')
        raw = page['html']
        if trace_path.exists():
            trace = json.loads(trace_path.read_text(encoding='utf-8'))
            raw = trace.get('repair_html') or trace.get('original_html') or raw
        page.update(sanitize(raw, page['capability'], page['title'], self.script_nonce))
        page['html'] = re.sub(r"nonce-[A-Za-z0-9_-]+", 'nonce-'+self.script_nonce, page['html'])
        page['html'] = re.sub(r'nonce="[A-Za-z0-9_-]+"', 'nonce="'+self.script_nonce+'"', page['html'])
        return page

    def stop(self):
        if self.stopped:return
        self.stopped=True
        if self.active: self.cancel(self.active)
        self.engine.stop()
        if self.active:
            worker=self.jobs[self.active]['thread']
            if worker is not threading.current_thread():worker.join(timeout=3)
        self.server.shutdown()
        self.server.server_close()

    def handler(self):
        app = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass

            def send(self,status,data,kind='application/json; charset=utf-8'):
                if isinstance(data,(dict,list)): data=json.dumps(data,ensure_ascii=False)
                if isinstance(data,str): data=data.encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type',kind)
                self.send_header('Content-Length',str(len(data)))
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Referrer-Policy','no-referrer')
                self.send_header('X-Frame-Options','DENY')
                self.send_header('Content-Security-Policy',f"default-src 'none'; script-src 'self' 'nonce-{app.script_nonce}'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self' about:; font-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
                self.end_headers()
                try: self.wfile.write(data)
                except (BrokenPipeError,ConnectionResetError): pass

            def authorized(self):
                if not self.path.startswith('/') or self.path.startswith('//'):
                    self.send(403,{'error':'Only local request paths are accepted.'}); return False
                if self.headers.get('Host') != f'127.0.0.1:{app.server.server_port}':
                    self.send(403,{'error':'Unrecognized host.'}); return False
                if self.path.startswith('/api/'):
                    if not secrets.compare_digest(self.headers.get('X-Elsewhere-Token',''),app.token):
                        self.send(403,{'error':'This session is not authorized.'}); return False
                    if self.command == 'POST' and self.headers.get('Origin') != app.origin:
                        self.send(403,{'error':'Unrecognized origin.'}); return False
                return True

            def do_GET(self):
                if not self.authorized(): return
                try:
                    path=urlsplit(self.path).path
                    if path == '/api/status': self.send(200,app.status())
                    elif path.startswith('/api/jobs/'):
                        job=app.jobs.get(path.rsplit('/',1)[-1])
                        self.send(200,app.snapshot(job)) if job else self.send(404,{'error':'Job not found.'})
                    elif path.startswith('/api/pages/'):
                        self.send(200,app.load_page(path.rsplit('/',1)[-1]))
                    elif path in ('/','/index.html','/app.js','/app.css'):
                        name='index.html' if path=='/' else path[1:]
                        self.send(200,(ROOT/'web'/name).read_bytes(),mimetypes.guess_type(name)[0]+'; charset=utf-8')
                    else: self.send(404,{'error':'Not found.'})
                except (ValueError,OSError): self.send(404,{'error':'Page not found.'})

            def do_POST(self):
                if not self.authorized(): return
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0 < length <= 25000: raise ValueError('Request is too large or empty.')
                    body=json.loads(self.rfile.read(length))
                    if not isinstance(body,dict): raise ValueError('Expected an object.')
                    if self.path=='/api/generate': self.send(200,app.start_job(body))
                    elif self.path=='/api/cancel':
                        job=app.jobs.get(body.get('id'))
                        app.cancel(body.get('id'))
                        if job:job['thread'].join(timeout=10)
                        self.send(200,{'ok':True,'stopped':not job or not job['thread'].is_alive()})
                    elif self.path=='/api/rendered':
                        job=app.jobs.get(body.get('id'))
                        if job and job['revision']==body.get('revision') and job['state'] not in TERMINAL:
                            report=body.get('layout',{})
                            if not isinstance(report,dict) or not isinstance(report.get('width'),(int,float)) or report['width']<100:
                                raise ValueError('A visible-sized layout is required.')
                            job['layout']={'overflow':report.get('overflow') is True,'width':report.get('width'), 'overflowing':report.get('overflowing',[])[:6], 'samples':report.get('samples',[])[:2]}
                            job['rendered'].set()
                        self.send(200,{'ok':True})
                    elif self.path=='/api/settings':
                        with app.lock:
                            app.settings.update({k:body[k] for k in app.settings if isinstance(body.get(k),bool)})
                            atomic_json(app.data/'settings.json',app.settings)
                        self.send(200,app.settings)
                    elif self.path=='/api/bookmark':
                        if not isinstance(body.get('enabled'),bool): raise ValueError('Expected bookmark state.')
                        self.send(200,app.bookmark(body.get('id'),body['enabled']))
                    elif self.path=='/api/export':
                        page=app.load_page(body.get('id'))
                        path=app.data/'exports'/f"{page['id']}.html"
                        path.write_text(page['html'],encoding='utf-8')
                        self.send(200,{'path':str(path)})
                    elif self.path=='/api/trace':
                        pid=body.get('id','')
                        if not re.fullmatch(r'[0-9a-f]{32}',pid): raise ValueError('Invalid page ID.')
                        path=app.page_path(pid)
                        if path is None: raise ValueError('Page expired.')
                        trace=json.loads(path.with_name(f'{pid}.trace.json').read_text(encoding='utf-8'))
                        self.send(200,trace)
                    else: self.send(404,{'error':'Not found.'})
                except (ValueError,TypeError,KeyError,OSError) as exc:
                    self.send(400,{'error':str(exc)[:400]})
        return Handler
