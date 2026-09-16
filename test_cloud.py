"""Official wire-format fixtures only. Tests never contact a provider or use a real key."""
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock

from backend import App
from cloud import CloudEngine, ProviderError, ProviderRefusal, checked_route
from engine import Cancelled, REVIEW_SCHEMA, PATCH_SCHEMA

KEY='test-only-secret-not-a-real-key'
HTML='<html><head><title>Cloud fixture</title></head><body><h1>The Library</h1><p>A complete invented page of stories and ideas.</p></body></html>'


def stream(*events):
    response=io.BytesIO(b''.join(b'event: test\r\ndata: '+json.dumps(e).encode()+b'\r\n\r\n' for e in events))
    response.status=200
    return response


class CloudTests(unittest.TestCase):
    def engine(self,provider='openai'):
        return CloudEngine({'provider':provider,'model':'gpt-6-astra' if provider=='openai' else 'claude-opus-5','workspace':'wrkspc_test'},KEY)

    def run_stream(self,engine,response,cancel=None):
        conn=Mock();conn.getresponse.return_value=response
        with patch('cloud.http.client.HTTPSConnection',return_value=conn) as https:
            result=engine.complete([{'role':'system','content':'System rules'},{'role':'user','content':'Imagine a library'}],cancel or threading.Event())
        return result,conn,https

    def test_openai_stream_and_official_endpoint(self):
        result,conn,https=self.run_stream(self.engine(),stream({'type':'response.output_text.delta','delta':HTML},{'type':'response.completed','response':{'usage':{'input_tokens':32,'output_tokens':64}}}))
        self.assertEqual(result[0],HTML)
        self.assertEqual(result[1]['usage']['output_tokens'],64)
        https.assert_called_once_with('api.openai.com',timeout=60)
        args=conn.request.call_args.args
        self.assertEqual(args[:2],('POST','/v1/responses'))
        payload=json.loads(args[2])
        self.assertFalse(payload['store'])
        self.assertNotIn(KEY,args[2].decode())
        self.assertEqual(args[3]['Authorization'],'Bearer '+KEY)
        for key in ('temperature','seed','top_p','top_k'): self.assertNotIn(key,payload)
        conn.close.assert_called_once()

    def test_claude_stream_version_workspace_and_image(self):
        engine=self.engine('anthropic')
        result,conn,https=self.run_stream(engine,stream({'type':'message_start','message':{'usage':{'input_tokens':20}}},{'type':'content_block_delta','delta':{'type':'thinking_delta','thinking':'Not page content'}},{'type':'content_block_delta','delta':{'type':'text_delta','text':HTML}},{'type':'message_delta','delta':{'stop_reason':'end_turn'},'usage':{'output_tokens':70}},{'type':'message_stop'}))
        self.assertEqual(result[0],HTML)
        self.assertEqual(result[1]['usage'],{'input_tokens':20,'output_tokens':70})
        https.assert_called_once_with('api.anthropic.com',timeout=60)
        args=conn.request.call_args.args
        self.assertEqual(args[1],'/v1/messages')
        self.assertEqual(args[3]['anthropic-version'],'2023-06-01')
        self.assertEqual(args[3]['anthropic-workspace-id'],'wrkspc_test')
        payload=json.loads(args[2]);self.assertEqual(payload['system'],'System rules')
        self.assertNotIn('temperature',payload)
        messages=[{'role':'user','content':[{'type':'image_url','image_url':{'url':'data:image/png;base64,aGVsbG8='}}]}]
        self.assertEqual(engine.payload(messages,500,False)['messages'][0]['content'][0]['source']['data'],'aGVsbG8=')
        self.assertEqual(self.engine().payload(messages,500,False)['input'][0]['content'][0]['type'],'input_image')

    def test_refusals_and_incomplete_streams_are_terminal(self):
        fixtures=[('openai',{'type':'response.refusal.delta','delta':'Declined'}),('openai',{'type':'response.incomplete','response':{}}),('openai',{'type':'error','message':KEY}),('anthropic',{'type':'message_delta','delta':{'stop_reason':'refusal'}}),('anthropic',{'type':'message_delta','delta':{'stop_reason':'end_turn','stop_details':{'type':'refusal'}}}),('anthropic',{'type':'message_delta','delta':{'stop_reason':'max_tokens'}})]
        for provider,event in fixtures:
            with self.subTest(provider=provider,event=event),self.assertRaises(ProviderError):
                self.run_stream(self.engine(provider),stream(event))
        with self.assertRaisesRegex(ProviderError,'before completion'):
            self.run_stream(self.engine(),stream({'type':'response.output_text.delta','delta':'partial'}))

    def test_api_error_does_not_echo_credentials_or_retry(self):
        response=stream();response.status=401
        conn=Mock();conn.getresponse.return_value=response
        with patch('cloud.http.client.HTTPSConnection',return_value=conn),self.assertRaises(ProviderError) as caught:
            self.engine().complete([],threading.Event())
        self.assertNotIn(KEY,str(caught.exception))
        self.assertIn('API key',str(caught.exception))
        self.assertEqual(conn.request.call_count,1)

    def test_cancel_before_call_and_during_stream(self):
        cancel=threading.Event();cancel.set()
        with patch('cloud.http.client.HTTPSConnection') as https,self.assertRaises(Cancelled): self.engine().complete([],cancel)
        https.assert_not_called()
        cancel.clear();engine=self.engine();response=stream({'type':'response.output_text.delta','delta':'first'})
        conn=Mock();conn.getresponse.return_value=response
        def progress(_):cancel.set();engine.interrupt()
        with patch('cloud.http.client.HTTPSConnection',return_value=conn),self.assertRaises(Cancelled):engine.complete([],cancel,progress=progress)
        conn.sock.shutdown.assert_called_once()

    def test_json_output_and_no_automatic_reprompt_of_plain_refusal(self):
        for schema in (REVIEW_SCHEMA, PATCH_SCHEMA):
            output=self.engine().payload([],550,schema)['text']['format']
            self.assertEqual(output['type'],'json_schema')
            self.assertTrue(output['strict'])
            self.assertEqual(output['schema'],schema)
        engine=self.engine()
        with patch.object(engine,'complete',return_value=('I cannot provide that.',{})) as call,self.assertRaises(ProviderError):
            engine.generate('request',None,threading.Event(),0,None)
        call.assert_called_once()

    def test_review_and_patch_send_their_explicit_schemas(self):
        engine=self.engine()
        with patch.object(engine,'complete',return_value=('{"issues":[],"summary":"Clear"}',{})) as call:
            report=engine.review({'html':HTML,'text':'Library'}, {}, None, threading.Event())
        self.assertEqual(call.call_args.kwargs['json_output'],REVIEW_SCHEMA)
        self.assertEqual(report['summary'],'Clear')
        with patch.object(engine,'complete',return_value=('{"replacements":[{"old":"The Library","new":"Our Library"}]}',{})) as call:
            raw,_=engine.patch(HTML,['Change title'],threading.Event(),0)
        self.assertEqual(call.call_args.kwargs['json_output'],PATCH_SCHEMA)
        self.assertIn('Our Library',raw)

    def test_api_diagnostics_include_parameter_without_echoing_raw_message(self):
        response=io.BytesIO(json.dumps({'error':{'message':KEY+' private page text','code':'unsupported_value','param':'text.format.type','type':KEY}}).encode())
        response.status=400
        with self.assertRaises(ProviderError) as caught:
            self.run_stream(self.engine(),response)
        self.assertIn('code=unsupported_value',str(caught.exception))
        self.assertIn('param=text.format.type',str(caught.exception))
        self.assertNotIn(KEY,str(caught.exception))
        self.assertNotIn('private page text',str(caught.exception))


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=App(Path(self.temp.name),start_engine=False)

    def tearDown(self):
        self.app.stop();self.temp.cleanup()

    def configure(self,provider='openai'):
        return self.app.configure_router({'provider':provider,'model':'gpt-6-astra' if provider=='openai' else 'claude-opus-5','api_key':KEY,'cloud_consent':True})

    def job(self):
        with patch('backend.threading.Thread.start'): result=self.app.start_job({'prompt':'library'})
        self.app.active=None
        return self.app.jobs[result['id']]

    def test_keys_are_session_only_and_never_in_public_status_or_snapshot(self):
        self.assertEqual(self.app.route['provider'],'local')
        state=self.configure()
        self.assertTrue(state['keys']['openai'])
        self.assertNotIn(KEY,json.dumps(self.app.status()))
        job=self.job()
        self.assertNotIn(KEY,json.dumps(self.app.snapshot(job)))
        self.app.stop();self.app=App(self.app.data,start_engine=False)
        self.assertEqual(self.app.route['provider'],'local')
        self.assertFalse(self.app.api_keys)
        for file in self.app.data.rglob('*.json'): self.assertNotIn(KEY,file.read_text())

    def test_active_job_keeps_route_and_cloud_trace_has_no_keys(self):
        self.configure();job=self.job();job['settings'].update(review=False,visual=False)
        self.app.configure_router({'provider':'local'})
        with patch.object(job['runner'],'complete',return_value=(HTML,{'finish':'stop'})),patch.object(self.app,'wait_render'):
            self.app.run_job(job)
        self.assertEqual(job['state'],'done',job['error'])
        self.assertEqual(job['result']['provider'],'openai')
        self.assertNotIn('runner',job)
        for file in self.app.data.rglob('*.json'): self.assertNotIn(KEY,file.read_text())

    def test_provider_refusal_during_review_stops_without_fallback_or_repair(self):
        self.configure();job=self.job();runner=job['runner']
        with patch.object(runner,'generate',return_value=(HTML,{'finish':'stop'})),patch.object(runner,'review',side_effect=ProviderRefusal('Provider declined')),patch.object(runner,'patch') as repair,patch.object(self.app.engine,'generate') as local,patch.object(self.app,'wait_render'):
            self.app.run_job(job)
        self.assertEqual(job['state'],'error');repair.assert_not_called();local.assert_not_called()
        self.assertIsNone(self.app.page_path(job['id']))

    def test_review_api_failure_keeps_valid_page_without_more_generation(self):
        self.configure();job=self.job();runner=job['runner']
        with patch.object(runner,'generate',return_value=(HTML,{'finish':'stop'})) as generate,patch.object(runner,'review',side_effect=ProviderError('OpenAI API returned 400')),patch.object(runner,'patch') as repair,patch.object(self.app.engine,'generate') as local,patch.object(self.app,'wait_render'):
            self.app.run_job(job)
        self.assertEqual(job['state'],'done',job['error'])
        self.assertTrue(job['result']['review']['unavailable'])
        self.assertIn('400',job['result']['review']['summary'])
        self.assertIn('The Library',self.app.load_page(job['id'])['html'])
        self.assertEqual(self.app.pages[0]['id'],job['id'])
        generate.assert_called_once();repair.assert_not_called();local.assert_not_called()

    def test_targeted_patch_api_failure_keeps_original_page(self):
        self.configure();job=self.job();runner=job['runner']
        review={'issues':[{'severity':'error','detail':'Fix a spelling mistake'}],'summary':'One issue','visual':False}
        with patch.object(runner,'generate',return_value=(HTML,{'finish':'stop'})) as generate,patch.object(runner,'review',return_value=review),patch.object(runner,'patch',side_effect=ProviderError('OpenAI API returned 400')) as repair,patch.object(self.app,'wait_render'):
            self.app.run_job(job)
        self.assertEqual(job['state'],'done',job['error'])
        self.assertFalse(job['result']['repaired'])
        self.assertIn('original retained',job['result']['review']['summary'])
        self.assertIn('The Library',self.app.load_page(job['id'])['html'])
        generate.assert_called_once();repair.assert_called_once()

    def test_review_failure_does_not_bypass_failed_layout(self):
        self.configure();job=self.job();runner=job['runner']
        def overflow(_):job['layout']={'overflow':True,'width':625}
        with patch.object(runner,'generate',return_value=(HTML,{'finish':'stop'})) as generate,patch.object(runner,'review',side_effect=ProviderError('API returned 400')),patch.object(self.app,'wait_render',side_effect=overflow):
            self.app.run_job(job)
        self.assertEqual(job['state'],'error')
        self.assertIn('layout or structure',job['error'])
        self.assertEqual(generate.call_count,2)
        self.assertIsNone(self.app.page_path(job['id']))

    def test_cancellation_during_review_does_not_save_page(self):
        self.configure();job=self.job();runner=job['runner']
        with patch.object(runner,'generate',return_value=(HTML,{'finish':'stop'})),patch.object(runner,'review',side_effect=Cancelled()),patch.object(self.app,'wait_render'):
            self.app.run_job(job)
        self.assertEqual(job['state'],'cancelled')
        self.assertIsNone(self.app.page_path(job['id']))

    def test_invalid_route_missing_consent_and_key_are_rejected(self):
        for body in [{'provider':'proxy'},{'provider':'openai','model':'gpt-6-astra','api_key':KEY},{'provider':'openai','model':'gpt-6-astra','cloud_consent':True},{'provider':'anthropic','model':'gpt-6-astra','api_key':KEY,'cloud_consent':True}]:
            with self.subTest(body=body),self.assertRaises(ValueError):self.app.configure_router(body)
        self.assertEqual(self.app.route['provider'],'local')
        self.configure();self.app.configure_router({'forget_keys':True})
        self.assertFalse(self.app.api_keys)
        self.assertEqual(self.app.route['provider'],'local')


if __name__=='__main__': unittest.main()
