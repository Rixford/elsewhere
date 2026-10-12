"""Persistent browsing provenance without model calls or real user data."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from backend import App, atomic_json
from engine import Cancelled

HTML = '<html><head><title>Ocean library</title></head><body><h1>Ocean library</h1><p>Browse the imagined shelves beneath the waves, one story at a time.</p></body></html>'


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = App(self.temp.name, start_engine=False)
        self.app.engine.state = 'ready'
        self.app.settings.update(review=False, visual=False)

    def tearDown(self):
        self.app.stop()
        self.temp.cleanup()

    def job(self, **body):
        with patch('backend.threading.Thread.start'):
            result = self.app.start_job({'prompt':'ocean library', **body})
        self.app.active = None
        return self.app.jobs[result['id']]

    def generate(self, **body):
        job = self.job(**body)
        with patch.object(self.app.engine, 'generate', return_value=(HTML, {'finish':'stop'})), patch.object(self.app, 'wait_render'):
            self.app.run_job(job)
        self.assertEqual(job['state'], 'done', job['error'])
        return job

    def trace(self, job):
        return json.loads((self.app.data/'pages'/f"{job['id']}.trace.json").read_text(encoding='utf-8'))

    def test_new_page_and_trace_survive_expiry_and_restart(self):
        job = self.generate()
        for path in (self.app.data/'pages').glob('*.json'):
            os.utime(path, (time.time()-172800, time.time()-172800))
        self.app.stop()
        self.app = App(self.temp.name, start_engine=False)
        self.assertEqual(self.app.status()['history'][0]['id'], job['id'])
        self.assertEqual(self.app.load_page(job['id'])['title'], 'Ocean library')
        self.assertEqual(self.trace(job)['original_html'], HTML)

    def test_response_is_saved_before_sanitizing_and_done_record_before_bookmark(self):
        job = self.job()
        original_set_page = self.app.set_page
        def checked_set_page(*args):
            self.assertEqual(self.trace(job)['original_html'], HTML)
            self.assertNotEqual(job['state'], 'done')
            return original_set_page(*args)
        with patch.object(self.app.engine, 'generate', return_value=(HTML, {'finish':'stop'})), patch.object(self.app, 'wait_render'), patch.object(self.app, 'set_page', side_effect=checked_set_page):
            self.app.run_job(job)
        self.assertEqual(job['state'], 'done', job['error'])
        self.app.bookmark(job['id'], True)
        stored = self.app.data/'bookmarks'/f"{job['id']}.json"
        before = stored.read_bytes()
        self.app.clear_history()
        record = json.loads(Path(self.app.export_record(job['id'])['path']).read_text(encoding='utf-8'))
        self.assertEqual(record['generation']['state'], 'done')
        self.assertEqual(record['generation']['stored_html_sha256'], record['stored_html_sha256'])
        self.assertEqual(stored.read_bytes(), before)

    def test_record_preserves_original_refinement_snapshot_and_lineage(self):
        parent = self.generate()
        link = {'label':'Coral archives', 'destination':'/coral', 'excerpt':'Stories from the reef'}
        job = self.job(prompt='Coral archives', parent=parent['id'], link=link)
        job['settings']['review'] = True
        refined = HTML.replace('one story', 'one tale')
        review = {'issues':[{'severity':'error','detail':'Fixture correction'}], 'summary':'One correction', 'visual':False}
        with patch.object(self.app.engine, 'generate', return_value=(HTML, {'finish':'stop'})), patch.object(self.app.engine, 'review', return_value=review), patch.object(self.app.engine, 'patch', return_value=(refined, {'finish':'stop'})), patch.object(self.app, 'wait_render'):
            self.app.run_job(job)
        self.assertEqual(job['state'], 'done', job['error'])
        stored = json.loads(self.app.page_path(job['id']).read_text(encoding='utf-8'))
        self.app.api_keys['openai'] = 'private-test-key-never-export'
        with patch('backend.sanitize', side_effect=AssertionError('Export must not re-render')):
            output = Path(self.app.export_record(job['id'])['path'])
        record = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(record['schema_version'], 1)
        self.assertEqual(record['page'], stored)
        trace = record['generation']
        self.assertEqual(trace['original_html'], HTML)
        self.assertEqual(trace['repair_html'], refined)
        self.assertEqual(trace['original_sha256'], hashlib.sha256(HTML.encode()).hexdigest())
        self.assertEqual(trace['parent_id'], parent['id'])
        self.assertEqual(trace['link'], link)
        self.assertEqual(record['page']['parent_id'], parent['id'])
        self.assertIn('web/page-controller.js', trace['source_sha256'])
        self.assertNotIn(self.app.token, output.read_text(encoding='utf-8'))
        self.assertNotIn('private-test-key-never-export', output.read_text(encoding='utf-8'))
        self.assertNotIn(str(self.app.data), output.read_text(encoding='utf-8'))

    def test_memory_off_still_records_parent_without_using_context(self):
        parent = self.generate()
        self.app.settings['memory'] = False
        child = self.generate(parent=parent['id'])
        self.assertIsNone(self.trace(child)['context'])
        self.assertEqual(self.trace(child)['parent_id'], parent['id'])

    def test_partial_failures_and_cancellation_are_retained(self):
        for error in (RuntimeError('Stream ended'), Cancelled()):
            with self.subTest(error=type(error).__name__):
                job = self.job()
                error.partial_text = '<html><h1>Unfinished'
                with patch.object(self.app.engine, 'generate', side_effect=error):
                    self.app.run_job(job)
                self.assertEqual(self.trace(job)['partial_html'], error.partial_text)
                self.assertIn(job['state'], ('error','cancelled'))
                self.assertIsNone(self.app.page_path(job['id']))

    def test_legacy_page_without_trace_exports_honestly(self):
        pid = 'f'*32
        atomic_json(self.app.data/'pages'/f'{pid}.json', {'id':pid,'title':'Old page','html':HTML})
        record = json.loads(Path(self.app.export_record(pid)['path']).read_text(encoding='utf-8'))
        self.assertIsNone(record['generation'])
        self.assertEqual(record['page']['html'], HTML)

    def test_unbookmark_after_history_clear_restores_durable_page_and_trace(self):
        job=self.generate()
        self.app.bookmark(job['id'],True)
        self.app.clear_history()
        self.app.bookmark(job['id'],False)
        self.assertEqual(self.app.page_path(job['id']).parent.name,'pages')
        self.assertEqual(self.app.status()['history'][0]['id'],job['id'])
        self.assertEqual(self.trace(job)['original_html'],HTML)

    def test_completed_non_html_cloud_response_is_retained(self):
        self.app.configure_router({'provider':'openai','model':'gpt-6-astra','api_key':'test-only','cloud_consent':True})
        job=self.job()
        with patch.object(job['runner'],'complete',return_value=('No HTML in this response',{'finish':'stop','usage':{'output_tokens':6}})):
            self.app.run_job(job)
        self.assertEqual(job['state'],'error')
        self.assertEqual(self.trace(job)['partial_html'],'No HTML in this response')
        self.assertEqual(self.trace(job)['failed_response_stats']['usage']['output_tokens'],6)

    def request(self, path, body=None, authorized=True):
        conn = http.client.HTTPConnection('127.0.0.1', self.app.server.server_port)
        headers = {'X-Elsewhere-Token':self.app.token,'Origin':self.app.origin} if authorized else {}
        conn.request('POST' if body is not None else 'GET', path, json.dumps(body) if body is not None else None, headers)
        res=conn.getresponse(); data=res.read(); status=res.status; conn.close()
        return status, data

    def test_browser_only_routes_and_private_export_boundaries(self):
        status, html = self.request('/')
        self.assertEqual(status, 200)
        self.assertNotIn(b'evaluate.js', html)
        self.assertNotIn(b'id="evaluation"', html)
        self.assertIn(b'id="address-form"', html)
        self.assertEqual(self.request('/api/evaluations')[0], 404)
        self.assertEqual(self.request('/api/evaluations/start', {'tasks':[]})[0], 404)
        self.assertEqual(self.request('/evaluate.js')[0], 404)
        job = self.generate()
        self.assertEqual(self.request('/api/export-record', {'id':job['id']}, authorized=False)[0], 403)
        self.assertEqual(self.request('/api/export-record', {'id':'../private'})[0], 400)
        self.assertEqual(self.request('/api/export-record', {'id':job['id']})[0], 200)

    def test_old_evaluation_files_are_untouched(self):
        folder = self.app.data/'evaluations'; folder.mkdir()
        legacy = folder/'old-run.json'; legacy.write_text('{"keep":true}')
        self.app.stop(); self.app = App(self.temp.name, start_engine=False)
        self.app.clear_history()
        self.assertEqual(legacy.read_text(), '{"keep":true}')


if __name__ == '__main__': unittest.main()
