"""Regression checks for generated-document containment and local API boundaries."""
import http.client
import json
from pathlib import Path
import tempfile
import unittest
import html5lib

from backend import App, site_identity
from sanitize import sanitize, stylesheet, declarations

BASE='<h1>Expedition</h1><p><strong>Mission:</strong> Rescue the last library in the dunes and bring its stories home.</p>'

class DocumentTests(unittest.TestCase):
    def test_submit_survives_without_generated_handlers(self):
        page=sanitize(BASE+'<form onsubmit="alert(1)"><input type="submit" value="Ascend"></form>')
        self.assertIn('type="submit"',page['html'])
        self.assertNotIn('onsubmit=',page['html'])
        self.assertIn("form-action 'none'",page['html'])

    def test_inline_text_is_preserved(self):
        page=sanitize(BASE)
        self.assertIn('Rescue the last library',page['text'])

    def test_comments_never_become_visible_elements(self):
        page=sanitize(BASE+'<!-- Card 1 --><svg><defs><!-- Gradient --></defs><filter id="unused"/></svg>')
        self.assertNotIn('Card 1',page['text'])
        self.assertNotIn('Gradient',page['html'])
        self.assertNotIn('<span',page['html'])

    def test_accidentally_escaped_identifier_quotes_are_normalized(self):
        page=sanitize(BASE+'''<form class='\\"btn\\"' data-target='\\"form-section\\"'></form>''')
        self.assertIn('class="btn"',page['html'])
        self.assertIn('data-target="form-section"',page['html'])

    def test_executable_and_external_content_removed(self):
        raw=BASE+'''<script>alert(1)</script><iframe src="https://bad.test"></iframe>
        <img src="http://127.0.0.1:80/secret"><meta http-equiv="refresh" content="0;url=https://bad.test">
        <link rel="stylesheet" href="https://bad.test/x"><object data="file:///C:/private"></object>
        <svg onload="fetch('https://bad.test')"><foreignObject>bad</foreignObject><use href="https://bad.test/a"/><path fill="url(https://bad.test)" d="M0 0"/></svg>
        <div onclick="alert(1)" style="background:url(https://bad.test);color:red">Safe content</div>'''
        page=sanitize(raw,'test-capability')
        tree=html5lib.parse(page['html'],namespaceHTMLElements=False)
        scripts=list(tree.iter('script'))
        self.assertEqual(len(scripts),1)
        self.assertIn('test-capability',scripts[0].text)
        self.assertNotIn('bad.test',page['html'])
        self.assertNotIn('onclick=',page['html'])
        self.assertIn("connect-src 'none'",page['html'])

    def test_css_escape_and_nested_resource_blocked(self):
        css=stylesheet(r'@import "https://bad.test"; @font-face{src:url(https://bad.test)} @media(min-width:20px){p{background:u\72l(https://bad.test);color:green}} p{background:image-set("https://bad.test" 1x);margin:2px}')
        self.assertNotIn('bad.test',css)
        self.assertIn('color:green',css)
        self.assertIn('margin:2px',css)

    def test_links_become_intents(self):
        html=sanitize(BASE+'<a href="https://real.test/moon">Moon</a><a href="javascript:alert(1)">No</a>')['html']
        self.assertIn('data-intent="https://real.test/moon"',html)
        self.assertNotIn('javascript:',html)

    def test_duplicate_ids_are_reported(self):
        self.assertTrue(sanitize(BASE+'<p id="x">one</p><p id="x">two</p>')['issues'])

    def test_large_document_rejected(self):
        with self.assertRaises(ValueError):sanitize(BASE+'x'*180000)

    def test_deep_document_rejected(self):
        with self.assertRaises(ValueError):sanitize(BASE+'<div>'*60+'nested'+'</div>'*60)

class ApiTests(unittest.TestCase):
    def test_router_endpoint_requires_auth_origin_and_never_returns_key(self):
        body={'provider':'openai','model':'gpt-6-astra','api_key':'test-secret','cloud_consent':True}
        self.assertEqual(self.request('/api/router','POST',body)[0],403)
        headers={'X-Elsewhere-Token':self.app.token,'Origin':'null'}
        self.assertEqual(self.request('/api/router','POST',body,headers)[0],403)
        headers['Origin']=self.app.origin
        status,data=self.request('/api/router','POST',body,headers)
        self.assertEqual(status,200)
        self.assertNotIn(b'test-secret',data)
        self.assertEqual(json.loads(data)['provider'],'openai')

    def test_dark_settings_preference_survives_restart(self):
        headers={'X-Elsewhere-Token':self.app.token,'Origin':self.app.origin}
        self.assertEqual(self.request('/api/settings','POST',{'dark_settings':True},headers)[0],200)
        self.app.stop();self.app=App(self.app.data,start_engine=False)
        self.assertTrue(self.app.settings['dark_settings'])

    def store_page(self, pid, prompt, world='bruceleequotes.com', site=None):
        page={**sanitize('<style>body{color:gold}</style>'+BASE),'id':pid,'prompt':prompt,'world':world,'capability':'test-cap'}
        if site is not None: page['site']=site
        (self.app.data/'cache'/f'{pid}.json').write_text(json.dumps(page),encoding='utf-8')
        return page

    def begin_without_worker(self, body):
        from unittest.mock import patch
        self.app.engine.state='ready'
        with patch('backend.threading.Thread.start'):
            result=self.app.start_job(body)
        self.app.active=None
        return self.app.jobs[result['id']]

    def test_descendants_keep_seed_identity_and_clicked_topic(self):
        root=self.store_page('1'*32,'bruceleequotes.com')
        identity=site_identity(root)
        self.assertIn('color:gold',identity['style_css'])
        child=self.store_page('2'*32,'Martial arts',site=identity)
        self.app.domains['bruceleequotes.com']={'title':'Unrelated sibling'}
        link={'label':'Metaphysics','destination':'/','excerpt':'Bruce Lee on being and becoming.'}
        job=self.begin_without_worker({'prompt':'Metaphysics','parent':child['id'],'link':link})
        self.assertEqual(job['context']['site'],identity)
        self.assertEqual(job['context']['clicked_link'],link)
        self.assertEqual(job['context']['previous_entry'],'Martial arts')
        self.assertEqual(job['world'],'bruceleequotes.com')
        # The snapshot is independent of later branch mutations.
        identity['title']='Changed'
        self.assertNotEqual(job['context']['site']['title'],'Changed')

    def test_legacy_descendant_recovers_seed(self):
        root=self.store_page('1'*32,'bruceleequotes.com')
        child=self.store_page('2'*32,'Metaphysics')
        old=self.store_page('3'*32,'bruceleequotes.com')
        self.app.pages=[child,root,old]
        job=self.begin_without_worker({'prompt':'Growth','parent':child['id']})
        self.assertEqual(job['context']['site']['root_page'],root['id'])
        self.assertEqual(job['context']['previous_entry'],'Metaphysics')

    def test_bookmarked_child_carries_seed_after_backend_restart(self):
        from unittest.mock import patch
        root=self.store_page('1'*32,'bruceleequotes.com')
        self.app.settings.update(review=False,visual=False)
        job=self.begin_without_worker({'prompt':'Metaphysics','parent':root['id']})
        with patch.object(self.app.engine,'generate',return_value=(BASE,{'finish':'stop'})), patch.object(self.app,'wait_render'):
            self.app.run_job(job)
        self.assertEqual(job['state'],'done',job['error'])
        self.assertEqual(job['result']['site']['root_page'],root['id'])
        self.app.bookmark(job['id'],True)
        self.app.stop()
        self.app=App(self.app.data,start_engine=False)
        onward=self.begin_without_worker({'prompt':'Being and becoming','parent':job['id']})
        self.assertEqual(onward['context']['site']['root_page'],root['id'])
        self.assertEqual(onward['context']['previous_entry'],'Metaphysics')

    def test_external_link_and_memory_off_start_independent_pages(self):
        root=self.store_page('1'*32,'bruceleequotes.com')
        job=self.begin_without_worker({'prompt':'Search','parent':root['id'],'link':{'destination':'https://google.com/'}})
        self.assertIsNone(job['context'])
        self.assertEqual(job['world'],'google.com')
        self.app.settings['memory']=False
        job=self.begin_without_worker({'prompt':'Metaphysics','parent':root['id']})
        self.assertIsNone(job['context'])

    def test_bookmark_survives_cache_expiry_and_unbookmark_keeps_back(self):
        import os,time
        pid='b'*32
        page={**sanitize(BASE),'id':pid,'title':'Library','prompt':'library','created':time.time(),'capability':'cap'}
        cached=self.app.data/'cache'/f'{pid}.json'
        cached.write_text(json.dumps(page),encoding='utf-8')
        self.app.bookmark(pid,True)
        os.utime(cached,(time.time()-90000,time.time()-90000))
        self.app.stop()
        self.app=App(self.app.data,start_engine=False)
        self.assertFalse(cached.exists())
        self.assertEqual(self.app.status()['bookmarks'][0]['id'],pid)
        self.assertEqual(self.app.load_page(pid)['title'],'Library')
        self.app.bookmark(pid,False)
        self.assertTrue(cached.exists())
        self.assertEqual(self.app.status()['bookmarks'],[])
        self.assertEqual(self.app.load_page(pid)['id'],pid)

    def test_expiry_preserves_legacy_archive(self):
        import os,time
        legacy=self.app.data/'pages'/('c'*32+'.json')
        legacy.write_text('{}')
        os.utime(legacy,(time.time()-90000,time.time()-90000))
        self.app.stop()
        self.app=App(self.app.data,start_engine=False)
        self.assertTrue(legacy.exists())

    def test_bookmark_api_requires_boolean_and_valid_id(self):
        headers={'X-Elsewhere-Token':self.app.token,'Origin':self.app.origin}
        self.assertEqual(self.request('/api/bookmark','POST',{'id':'../private','enabled':True},headers)[0],400)
        self.assertEqual(self.request('/api/bookmark','POST',{'id':'a'*32,'enabled':'true'},headers)[0],400)

    def test_saved_page_recovers_submit_from_original_trace(self):
        pid='a'*32
        raw=BASE+'<form><input type="submit" value="Ascend"></form>'
        page={**sanitize(raw),'capability':'old','id':pid,'title':'Spire'}
        page['html']=page['html'].replace('type="submit"','type="text"')
        (self.app.data/'pages'/f'{pid}.json').write_text(json.dumps(page))
        (self.app.data/'pages'/f'{pid}.trace.json').write_text(json.dumps({'original_html':raw}))
        loaded=self.app.load_page(pid)
        self.assertIn('type="submit"',loaded['html'])
        self.assertEqual(loaded['html'].count('<script'),1)

    def test_fresh_domain_does_not_inherit_old_style(self):
        from unittest.mock import patch
        self.app.engine.state='ready'
        self.app.domains['google.com']={'title':'Unrelated archive'}
        with patch('backend.threading.Thread.start'):
            result=self.app.start_job({'prompt':'google.com'})
        self.assertIsNone(self.app.jobs[result['id']]['context'])
        self.app.active=None

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=App(Path(self.temp.name),start_engine=False)

    def tearDown(self):
        self.app.stop()
        self.temp.cleanup()

    def request(self,path,method='GET',body=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.app.server.server_port,timeout=3)
        conn.request(method,path,body=json.dumps(body) if body is not None else None,headers=headers or {})
        res=conn.getresponse();data=res.read();conn.close()
        return res.status,data

    def test_state_requires_token(self):
        self.assertEqual(self.request('/api/status')[0],403)
        self.assertEqual(self.request('/api/status',headers={'X-Elsewhere-Token':self.app.token})[0],200)

    def test_absolute_form_cannot_bypass_auth(self):
        self.assertEqual(self.request(self.app.origin+'/api/status')[0],403)

    def test_host_rebinding_rejected(self):
        self.assertEqual(self.request('/',headers={'Host':'evil.test'})[0],403)

    def test_post_requires_exact_origin(self):
        headers={'X-Elsewhere-Token':self.app.token,'Content-Type':'application/json','Origin':'null'}
        self.assertEqual(self.request('/api/settings','POST',{'memory':False},headers)[0],403)
        headers['Origin']=self.app.origin
        self.assertEqual(self.request('/api/settings','POST',{'memory':False},headers)[0],200)
        self.assertFalse(self.app.settings['memory'])

    def test_paths_do_not_expose_files(self):
        self.assertEqual(self.request('/../app.py')[0],404)
        self.assertEqual(self.request('/runtime-path.txt')[0],404)

    def test_capability_not_extracted_from_page_text(self):
        job={'revision':0,'rendered':__import__('threading').Event(),'prompt':'test'}
        page=self.app.set_page(job,BASE+'<code>const capability = "example";</code>')
        self.assertNotEqual(page['capability'],'example')
        self.assertIn('const capability = "'+page['capability']+'";',page['html'])

    def test_arbitrary_text_is_not_required_to_be_a_url(self):
        from unittest.mock import patch
        self.app.engine.state='ready'
        with patch('backend.threading.Thread.start'):
            result=self.app.start_job({'prompt':'an atlas of [impossible places'})
        self.assertEqual(self.app.jobs[result['id']]['prompt'],'an atlas of [impossible places')
        self.app.active=None

class PatchTests(unittest.TestCase):
    def test_exact_patch_and_ambiguous_patch(self):
        from engine import Engine
        from unittest.mock import patch
        import threading
        engine=Engine('.')
        with patch.object(engine,'complete',return_value=(json.dumps({'replacements':[{'old':'teh','new':'the'}]}),{})):
            self.assertEqual(engine.patch('teh page',[],threading.Event(),0)[0],'the page')
            with self.assertRaises(ValueError):engine.patch('teh teh',[],threading.Event(),0)

if __name__=='__main__':unittest.main(verbosity=2)
