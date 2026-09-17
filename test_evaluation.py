import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import urllib.request
import urllib.error
from unittest.mock import Mock, patch

from backend import App
from cloud import ProviderError, ProviderRefusal
from engine import Cancelled
from evaluation import INSTRUCTIONS, validate_spec
from sanitize import sanitize

HTML='<html><head><title>A thought</title><style>article{position:absolute;left:20px}body{font-family:Arial}</style></head><body><article><h1>A city that listens</h1><p>Three approaches to a quieter city that remains full of life.</p><details><summary>Tradeoffs</summary><p>People need places to meet and places to rest.</p></details></article></body></html>'
SPEC={'cases':[{'kind':'concept','prompt':'a quiet city','criteria':'Show tradeoffs'}],'repeats':2,'seed':4,'budget':2000}

class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.app=App(Path(self.temp.name),start_engine=False)
        self.app.engine.state='ready'
    def tearDown(self):self.app.stop();self.temp.cleanup()
    def start(self,spec=None):
        with patch('evaluation.threading.Thread.start'):reply=self.app.start_evaluation(spec or SPEC)
        job=self.app.jobs[reply['id']];self.app.active=None
        record=self.app.read_evaluation(reply['id']);record.pop('ratings')
        return job,record
    def measured(self,job):
        job['layout']={'width':1280,'overflow':False,'samples':[{'width':1280,'overflow':False},{'width':640,'overflow':False}]}
        job['rendered'].set()
    def run_fixture(self,job,record,**kwargs):
        with patch.object(job['runner'],'complete',return_value=(HTML,{'finish':'stop','seconds':1.25,'usage':{'input_tokens':20,'output_tokens':50}}),**kwargs) as complete,patch.object(self.app,'wait_render',side_effect=self.measured):
            self.app.run_evaluation(job,record)
        return complete
    def test_isolated_repeats_preserve_raw_and_never_generate_repair(self):
        job,record=self.start()
        with patch.object(self.app.engine,'generate') as generate,patch.object(self.app.engine,'patch') as repair,patch.object(self.app.engine,'review') as review:
            call=self.run_fixture(job,record)
        self.assertEqual(job['state'],'done');self.assertEqual(call.call_count,2)
        self.assertEqual([c.kwargs['seed'] for c in call.call_args_list],[4,5])
        self.assertEqual(call.call_args.args[0],[{'role':'system','content':INSTRUCTIONS},{'role':'user','content':json.dumps(SPEC['cases'][0])}])
        generate.assert_not_called();repair.assert_not_called();review.assert_not_called()
        result=self.app.read_evaluation(job['id'])
        self.assertEqual(result['summary']['checks_passed'],2)
        for a in result['attempts']:
            self.assertEqual(a['raw'],HTML);self.assertEqual(a['raw_sha256'],hashlib.sha256(HTML.encode()).hexdigest())
        self.assertFalse(self.app.pages);self.assertFalse(self.app.domains)
    def test_eval_sanitizer_has_guards_without_explore_repairs(self):
        page=sanitize(HTML+'<script>fetch("https://example.com")</script>',evaluation=True)
        self.assertIn("connect-src 'none'",page['html'])
        self.assertNotIn('repairCollisions',page['html']);self.assertNotIn('box-sizing:border-box',page['html'])
        self.assertIn('position:absolute',page['html']);self.assertIn('script',page['removed'])
    def test_bad_response_is_recorded_and_other_repetition_runs(self):
        job,record=self.start()
        call=self.run_fixture(job,record,side_effect=[('No page',{'finish':'stop','seconds':1}),(HTML,{'finish':'stop','seconds':1})])
        result=self.app.read_evaluation(job['id']);self.assertEqual(call.call_count,2)
        self.assertEqual(result['summary']['failed'],1);self.assertEqual(result['summary']['measured'],1)
        self.assertEqual(result['attempts'][0]['raw'],'No page')
    def test_fixed_width_checks_reject_wrong_measurements(self):
        job,record=self.start({**SPEC,'repeats':1})
        with patch.object(job['runner'],'complete',return_value=(HTML,{'finish':'stop'})),patch.object(self.app,'wait_render'):
            self.app.run_evaluation(job,record)
        self.assertEqual(record['summary']['failed'],1)
        self.assertIn('1280 and 640',record['attempts'][0]['error'])
    def test_overflow_is_measured_and_never_repaired(self):
        job,record=self.start({**SPEC,'repeats':1})
        def overflow(j):self.measured(j);j['layout']['overflow']=True;j['layout']['samples'][1]['overflow']=True
        with patch.object(job['runner'],'complete',return_value=(HTML,{'finish':'stop'})),patch.object(job['runner'],'patch') as repair,patch.object(self.app,'wait_render',side_effect=overflow):self.app.run_evaluation(job,record)
        self.assertEqual(record['summary']['measured'],1);self.assertEqual(record['summary']['checks_passed'],0);repair.assert_not_called()
    def test_partial_provider_failure_stops_batch_without_retry(self):
        job,record=self.start();error=ProviderError('Connection ended');error.partial_text='<html><body>partial'
        call=self.run_fixture(job,record,side_effect=error)
        self.assertEqual(record['state'],'error');self.assertEqual(record['summary']['not_run'],1)
        self.assertEqual(record['attempts'][0]['raw'],error.partial_text);call.assert_called_once()
    def test_review_is_advisory_and_refusal_is_terminal(self):
        job,record=self.start({**SPEC,'review':True})
        with patch.object(self.app.engine,'review',side_effect=ProviderRefusal('Declined')):self.run_fixture(job,record)
        self.assertEqual(record['state'],'error');self.assertEqual(record['summary']['not_run'],1)
        self.assertEqual(record['attempts'][0]['raw'],HTML)
    def test_review_technical_error_keeps_attempt(self):
        job,record=self.start({**SPEC,'review':True,'repeats':1})
        with patch.object(self.app.engine,'review',side_effect=ProviderError('Review unavailable')):self.run_fixture(job,record)
        self.assertEqual(record['summary']['measured'],1);self.assertTrue(record['attempts'][0]['review']['unavailable'])
    def test_cancel_accounts_for_unrun_attempts(self):
        job,record=self.start();self.run_fixture(job,record,side_effect=Cancelled())
        self.assertEqual(record['state'],'cancelled');self.assertEqual(record['summary']['cancelled'],1);self.assertEqual(record['summary']['not_run'],1)
    def test_ratings_separate_and_summary_export_has_no_content(self):
        job,record=self.start();self.run_fixture(job,record)
        original=self.app.evaluation_path(job['id']).read_bytes()
        self.app.rate_evaluation({'id':job['id'],'attempt':'1.1','scores':dict.fromkeys(('intent','criteria','identity','coherence','visual'),4),'note':'private note'})
        self.assertEqual(original,self.app.evaluation_path(job['id']).read_bytes())
        export=self.app.export_evaluation({'id':job['id']})
        text=Path(export['path']).read_text();self.assertNotIn('quiet city',text);self.assertNotIn('private note',text);self.assertNotIn('<html>',text)
        with self.assertRaises(ValueError):self.app.export_evaluation({'id':job['id'],'include_content':True})
        with self.assertRaises(ValueError):self.app.delete_evaluation({'id':job['id']})
        self.app.delete_evaluation({'id':job['id'],'confirmed':True});self.assertFalse(self.app.evaluation_path(job['id']).exists())
    def test_restart_preserves_raw_and_marks_interrupted_work(self):
        job,record=self.start();record['attempts'][0].update(state='rendering',raw=HTML)
        self.app.save_evaluation(record);self.app.stop();self.app=App(self.app.data,start_engine=False)
        restored=self.app.read_evaluation(job['id']);self.assertEqual(restored['state'],'interrupted');self.assertEqual(restored['attempts'][0]['raw'],HTML);self.assertEqual(restored['summary']['not_run'],1)
    def test_cloud_requires_confirmation_and_seed_is_labeled_unsupported(self):
        self.app.configure_router({'provider':'openai','model':'gpt-6-astra','api_key':'test-only-fake','cloud_consent':True})
        with self.assertRaises(ValueError):self.start()
        job,record=self.start({**SPEC,'cloud_confirmed':True})
        self.assertIsNone(record['attempts'][0]['seed']);self.assertNotIn('test-only-fake',json.dumps(record))
    def test_validation_limits_and_fingerprint(self):
        for fields in ({'repeats':True},{'cases':[]},{'budget':9000},{'seed':-1},{'prices':{'input':float('nan'),'output':1}}):
            with self.assertRaises(ValueError):validate_spec({**SPEC,**fields})
        job,record=self.start();job2,record2=self.start({**SPEC,'repeats':3})
        self.assertEqual(record['fingerprint'],record2['fingerprint'])
        _,record3=self.start({**SPEC,'budget':3000});self.assertNotEqual(record['fingerprint'],record3['fingerprint'])

    def test_http_endpoints_require_authentication_and_origin(self):
        for path,body,headers in [('/api/evaluations',None,{}),('/api/evaluations/start',SPEC,{'X-Elsewhere-Token':self.app.token})]:
            request=urllib.request.Request(self.app.origin+path,data=json.dumps(body).encode() if body else None,headers=headers)
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
            self.assertEqual(error.exception.code,403)
        request=urllib.request.Request(self.app.origin+'/api/evaluations',headers={'X-Elsewhere-Token':self.app.token})
        with urllib.request.urlopen(request) as response:self.assertEqual(json.load(response),[])
        request=urllib.request.Request(self.app.origin+'/api/evaluations/start',data=json.dumps({**SPEC,'repeats':50}).encode(),headers={'X-Elsewhere-Token':self.app.token,'Origin':self.app.origin})
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
        self.assertEqual(error.exception.code,400)

    def test_explicit_prices_unknown_usage_and_compare_identity(self):
        job,record=self.start({**SPEC,'prices':{'input':2,'output':8}});self.run_fixture(job,record)
        self.assertAlmostEqual(record['summary']['estimated_cost'],.00088)
        self.assertEqual(record['summary']['usage'],{'input_tokens':40,'output_tokens':100})
        with self.assertRaises(ValueError):self.app.start_evaluation({**SPEC,'cases':[{'kind':'unknown','prompt':'test'}]})
        with self.assertRaises(ValueError):self.app.read_evaluation('../settings')

    def test_active_explore_worker_blocks_evaluation_and_clear_preserves_runs(self):
        self.app.jobs['busy']={'thread':Mock(is_alive=lambda:True),'state':'generating'};self.app.active='busy'
        with self.assertRaises(ValueError):self.app.start_evaluation(SPEC)
        self.app.jobs.clear();self.app.active=None
        job,record=self.start();self.run_fixture(job,record)
        self.app.clear_history();self.assertEqual(self.app.read_evaluation(record['id'])['state'],'done')

if __name__=='__main__':unittest.main()
