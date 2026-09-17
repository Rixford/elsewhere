"""Closed-book experiments. Records contain private prompts; never commit them."""
import copy
import hashlib
import json
import platform
import re
import secrets
import threading
import time
import uuid
from pathlib import Path

from cloud import CloudEngine, ProviderError, ProviderRefusal
from engine import Cancelled
from sanitize import sanitize

ROOT=Path(__file__).resolve().parent

PROTOCOL = 'elsewhere-closed-book-v1'
VIEWPORTS = [{'width':1280,'height':720},{'width':640,'height':720}]
KINDS = ('website','concept','search','translation')
DIMENSIONS = ('intent','criteria','identity','coherence','visual')
INSTRUCTIONS = '''You are taking a closed-book visual reconstruction and interpretation task.
Return one complete HTML document with inline CSS and inline SVG. No markdown.
Use only the supplied task and learned knowledge. No browsing, retrieval, reference images,
external assets, web fonts, JavaScript, canvas, or network calls. Use system fonts.
For a website task, express its recognizable learned identity; do not claim to fetch the current site.
For a concept, thought, or search, translate its meaning into a relevant visual information experience.
Search results are imagined, not retrieved or verified. For translation, transfer relevant structure
or visual understanding to the requested unrelated subject without losing its meaning.
Follow all typed criteria. Criteria can concern composition, content, style, accessibility or interaction.
Use semantic HTML and native controls such as details/summary when appropriate. Real logins and
transactions are unavailable. Finish the document within the output budget. No explanatory preface.'''

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def validate_spec(body):
    cases=body.get('cases')
    if not isinstance(cases,list) or not 1<=len(cases)<=6: raise ValueError('Use 1–6 tasks per run.')
    clean=[]
    for case in cases:
        if not isinstance(case,dict) or case.get('kind') not in KINDS: raise ValueError('Choose a task type.')
        prompt=case.get('prompt','');criteria=case.get('criteria','')
        if not isinstance(prompt,str) or not 1<=len(prompt.strip())<=1200: raise ValueError('Each task needs 1–1,200 characters.')
        if not isinstance(criteria,str) or len(criteria)>1600: raise ValueError('Criteria must be at most 1,600 characters.')
        clean.append({'kind':case['kind'],'prompt':prompt.strip(),'criteria':criteria.strip()})
    repeats=body.get('repeats',1);budget=body.get('budget',5200);seed=body.get('seed',0)
    for value,low,high,name in ((repeats,1,5,'repetitions'),(budget,1024,8192,'output budget'),(seed,0,2147483642,'seed')):
        if type(value) is not int or not low<=value<=high: raise ValueError('Invalid '+name+'.')
    prices=body.get('prices')
    if prices is not None:
        if not isinstance(prices,dict) or set(prices)!={'input','output'}: raise ValueError('Supply both token prices or leave both blank.')
        if any(type(v) not in (int,float) or not 0<=v<=10000 for v in prices.values()): raise ValueError('Invalid price per million tokens.')
    return {'cases':clean,'repeats':repeats,'budget':budget,'seed':seed,'review':body.get('review') is True,'prices':prices}

def summarize(record):
    attempts=record['attempts'];finished=[a for a in attempts if a['state']=='measured']
    passed=[a for a in finished if not a['checks']['issues'] and not a['layout']['overflow'] and a.get('stats',{}).get('finish')=='stop']
    generation=[a['stats'] for a in attempts if a.get('stats')]
    usage=[s.get('usage') for s in generation]+[a['review']['stats'].get('usage') for a in attempts if a.get('review',{}).get('stats')]
    all_usage=bool(usage) and all(isinstance(u,dict) and 'input_tokens' in u and 'output_tokens' in u for u in usage)
    totals={k:sum(u.get(k,0) for u in usage if isinstance(u,dict)) for k in ('input_tokens','output_tokens')}
    prices=record['spec']['prices']
    cost=sum(totals[k+'_tokens']*prices[k]/1e6 for k in ('input','output')) if all_usage and prices else None
    return {'scheduled':len(attempts),'measured':len(finished),'checks_passed':len(passed),
        'failed':sum(a['state']=='error' for a in attempts),'cancelled':sum(a['state']=='cancelled' for a in attempts),
        'not_run':sum(a['state'] in ('pending','skipped') for a in attempts),
        'generation_seconds':round(sum(s.get('seconds',0) for s in generation),2),
        'characters':sum(len(a.get('raw','')) for a in attempts),'usage':totals if all_usage else None,
        'estimated_cost':cost,'cost_note':'User-supplied rates; cache discounts and unsuccessful/unreported requests are not included. Not a billing total.'}

class EvaluationMixin:
    def evaluation_path(self,ident):
        if not isinstance(ident,str) or not re.fullmatch(r'[0-9a-f]{32}',ident): raise ValueError('Invalid evaluation ID.')
        return self.data/'evaluations'/f'{ident}.json'

    def save_evaluation(self,record):
        path=self.evaluation_path(record['id']);path.parent.mkdir(exist_ok=True)
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

    def read_evaluation(self,ident):
        path=self.evaluation_path(ident)
        record=json.loads(path.read_text(encoding='utf-8'))
        record['ratings']=json.loads(path.with_suffix('.ratings.json').read_text(encoding='utf-8')) if path.with_suffix('.ratings.json').exists() else {}
        for attempt in record['attempts']:
            if attempt.get('rendered_html'):
                attempt['rendered_html']=re.sub(r"nonce-[A-Za-z0-9_-]+",'nonce-'+self.script_nonce,attempt['rendered_html'])
                attempt['rendered_html']=re.sub(r'nonce="[A-Za-z0-9_-]+"','nonce="'+self.script_nonce+'"',attempt['rendered_html'])
        return record

    def recover_evaluations(self):
        for entry in self.list_evaluations():
            if entry['state']!='running':continue
            record=self.read_evaluation(entry['id']);record.pop('ratings',None)
            for attempt in record['attempts']:
                if attempt['state']=='pending':attempt['state']='skipped'
                elif attempt['state'] in ('generating','rendering'):attempt.update(state='error',error='Application exited before this attempt finished.')
            record.update(state='interrupted',summary=summarize(record));self.save_evaluation(record)

    def list_evaluations(self):
        folder=self.data/'evaluations';records=[]
        for path in folder.glob('*.json'):
            if not re.fullmatch(r'[0-9a-f]{32}\.json',path.name): continue
            try:
                r=json.loads(path.read_text(encoding='utf-8'))
                records.append({k:r[k] for k in ('id','created','state','provider','model','fingerprint','summary')})
            except (OSError,ValueError,KeyError): continue
        return sorted(records,key=lambda r:r['created'],reverse=True)

    def start_evaluation(self,body):
        spec=validate_spec(body)
        with self.lock:
            if self.active and self.jobs[self.active]['thread'].is_alive(): raise ValueError('Finish or stop the active model task first.')
            for key in list(self.jobs)[:-7]:
                if self.jobs[key]['state'] in ('done','error','cancelled'):del self.jobs[key]
            route=dict(self.route)
            runner=self.engine if route['provider']=='local' else CloudEngine(route,self.api_keys[route['provider']])
            if runner.state!='ready': raise ValueError(runner.error or 'The local model is loading.')
            if route['provider']!='local' and body.get('cloud_confirmed') is not True: raise ValueError('Confirm cloud charges for this evaluation run.')
            ident=uuid.uuid4().hex
            protocol={'version':PROTOCOL,'system_prompt':INSTRUCTIONS,'viewports':VIEWPORTS,'continuity':False,'repair':False,
                'renderer':'safety-sanitized; CSS animation paused and transitions disabled; no Explore CSS reset, collision repair or simulated controls',
                'interactions':'Native HTML only; no real navigation or submissions. Not an interaction benchmark.',
                'local_sampling':{'temperature':.7,'top_p':.92,'top_k':40,'context_tokens':16384},
                'cloud_sampling':'Provider defaults; low reasoning for GPT-5/6; no seed support; output budget adds 4096 for reasoning',
                'retrieval':'No tools or target-site requests configured; cloud provider internals are not observable',
                'environment':{'os':platform.system(),'release':platform.release(),'python':platform.python_version()},
                'renderer_hash':digest([(p,(ROOT/'web'/p).read_text(encoding='utf-8')) for p in ('evaluation-controller.js',)] + [('sanitize.py',(ROOT/'sanitize.py').read_text(encoding='utf-8'))])}
            record={'id':ident,'created':time.time(),'state':'running','provider':route['provider'],'model':route['model'],
                'spec':spec,'protocol':protocol,'attempts':[],
                'fingerprint':digest({'protocol':protocol,'cases':spec['cases'],'budget':spec['budget'],'seed':spec['seed']})}
            for c,case in enumerate(spec['cases']):
                for repeat in range(spec['repeats']):
                    record['attempts'].append({'id':f'{c+1}.{repeat+1}','case':c,'repeat':repeat+1,'seed':spec['seed']+repeat if route['provider']=='local' else None,'state':'pending'})
            record['summary']=summarize(record);self.save_evaluation(record)
            job={'id':ident,'kind':'evaluation','state':'generating','stage':'Starting evaluation','started':time.time(),'revision':0,'page':None,'chars':0,'error':'',
                'cancel':threading.Event(),'rendered':threading.Event(),'layout':{},'runner':runner,'provider':route['provider'],'model':route['model']}
            self.jobs[ident]=job;self.active=ident
            job['thread']=threading.Thread(target=self.run_evaluation,args=(job,record),daemon=True);job['thread'].start()
            return {'id':ident}

    def run_evaluation(self,job,record):
        runner=job['runner'];spec=record['spec'];failed=False
        try:
            for attempt in record['attempts']:
                if job['cancel'].is_set(): raise Cancelled()
                case=spec['cases'][attempt['case']];attempt.update(state='generating',started=time.time())
                messages=[{'role':'system','content':INSTRUCTIONS},{'role':'user','content':json.dumps(case,ensure_ascii=False)}]
                attempt['messages']=messages
                job.update(state='generating',page=None,chars=0,stage=f"Task {attempt['case']+1}/{len(spec['cases'])} · attempt {attempt['repeat']}/{spec['repeats']}")
                self.save_evaluation(record)
                try:
                    raw,stats=runner.complete(messages,job['cancel'],tokens=spec['budget'],seed=spec['seed']+attempt['repeat']-1,temperature=.7,progress=lambda n:job.update(chars=n))
                    attempt.update(raw=raw,raw_sha256=hashlib.sha256(raw.encode()).hexdigest(),stats=stats,state='rendering')
                    # Persist the unmodified response before parser or renderer work.
                    self.save_evaluation(record)
                    if not re.search(r'<html\b',raw,re.I): raise ValueError('Response is not an HTML document.')
                    capability=secrets.token_urlsafe(24)
                    page=sanitize(raw,capability,case['prompt'],self.script_nonce,evaluation=True);page['capability']=capability
                    attempt['checks']={k:page[k] for k in ('issues','removed','parse_errors')}
                    attempt['checks']['complete_document']=bool(re.search(r'</html\s*>',raw,re.I))
                    if not attempt['checks']['complete_document']: attempt['checks']['issues'].append('Missing closing HTML tag.')
                    attempt['checks']['raw_external_references']=len(re.findall(r'(?:https?:)?//[^\s<>"\x27]+',raw))
                    attempt['checks']['raw_scripts']=len(re.findall(r'<script\b',raw,re.I))
                    job['revision']+=1;job['rendered'].clear();job['layout']={};job.update(page=page,state='reviewing')
                    self.wait_render(job)
                    samples=job['layout'].get('samples',[])
                    if len(samples)!=2 or [s.get('width') for s in samples]!=[1280,640]: raise ValueError('Evaluation requires measurements at 1280 and 640 CSS pixels.')
                    attempt.update(layout=copy.deepcopy(job['layout']),state='measured',rendered_html=page['html'],title=page['title'])
                    if spec['review']:
                        job['stage']='Optional advisory review · original response unchanged'
                        try:attempt['review']=runner.review(page,job['layout'],None,job['cancel'])
                        except (Cancelled,ProviderRefusal):raise
                        except Exception as exc:attempt['review']={'unavailable':True,'summary':str(exc)[:300]}
                except Cancelled as exc:
                    if 'raw' not in attempt and getattr(exc,'partial_text',None):
                        attempt.update(raw=exc.partial_text,partial=True,raw_sha256=hashlib.sha256(exc.partial_text.encode()).hexdigest())
                    attempt['state']='cancelled';raise
                except Exception as exc:
                    attempt.update(state='error',error=str(exc)[:400])
                    if 'raw' not in attempt and getattr(exc,'partial_text',None):
                        attempt.update(raw=exc.partial_text,raw_sha256=hashlib.sha256(exc.partial_text.encode()).hexdigest(),partial=True)
                    if isinstance(exc,ProviderError):failed=True;break
                finally:
                    attempt['elapsed_seconds']=round(time.time()-attempt['started'],2)
                    record['summary']=summarize(record);self.save_evaluation(record)
            record['state']='error' if failed else 'done'
        except Cancelled:record['state']='cancelled'
        except Exception as exc:record.update(state='error',error=str(exc)[:400])
        finally:
            for attempt in record['attempts']:
                if attempt['state']=='pending':attempt['state']='skipped'
            record['summary']=summarize(record);record['finished']=time.time();self.save_evaluation(record)
            job.update(state=record['state'],stage='Evaluation saved',result={'evaluation':record['id']});job.pop('runner',None)

    def rate_evaluation(self,body):
        with self.lock:
            record=self.read_evaluation(body.get('id'))
            if record['state']=='running': raise ValueError('Wait for the evaluation to finish.')
            attempt=body.get('attempt');values=body.get('scores');note=body.get('note','')
            if attempt not in [a['id'] for a in record['attempts']]:raise ValueError('Unknown attempt.')
            if not isinstance(values,dict) or set(values)!=set(DIMENSIONS) or any(v is not None and (type(v) is not int or not 1<=v<=5) for v in values.values()):raise ValueError('Use 1–5 or unscored for each dimension.')
            if not isinstance(note,str) or len(note)>2000:raise ValueError('Notes must be at most 2,000 characters.')
            ratings=record['ratings'];ratings[attempt]={'scores':values,'note':note,'updated':time.time(),'source':'human'}
            path=self.evaluation_path(record['id']).with_suffix('.ratings.json');temp=path.with_suffix('.tmp')
            temp.write_text(json.dumps(ratings,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
            return {'saved':True}

    def export_evaluation(self,body):
        record=self.read_evaluation(body.get('id'))
        if record['state']=='running':raise ValueError('Wait for the evaluation to finish.')
        if body.get('include_content') is not True:
            # Summary export has no prompts, generated text, manual notes, or local paths.
            record={k:record[k] for k in ('id','provider','model','fingerprint','state','summary')}
            record['protocol']=PROTOCOL
        elif body.get('confirmed') is not True:raise ValueError('Confirm exporting private prompts and model responses.')
        path=self.data/'exports'/f"evaluation-{record['id']}{'-full' if body.get('include_content') else '-summary'}.json"
        path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        return {'path':str(path)}

    def delete_evaluation(self,body):
        with self.lock:
            ident=body.get('id');path=self.evaluation_path(ident)
            if body.get('confirmed') is not True:raise ValueError('Confirm deleting this evaluation.')
            if ident in self.jobs and self.jobs[ident]['thread'].is_alive():raise ValueError('Stop the run before deleting it.')
            path.unlink(missing_ok=True);path.with_suffix('.ratings.json').unlink(missing_ok=True)
            return {'deleted':True}
