"""Manual browser smoke fixture; no model, downloads, or real user history.

Run with Python, open the printed loopback URL, enter any prompt, and submit
Ascend with a name/class. The next page displays the resulting intent.
"""
import json
import tempfile
import threading
import html
from pathlib import Path
from backend import App
from engine import Cancelled

PAGE = '''<!doctype html><html><head><title>Interaction fixture</title>
<style>body{font:18px system-ui;padding:24px}main{max-width:600px;margin:auto}input,button{padding:12px;max-width:100%}form{display:flex;flex-direction:column;gap:12px}</style></head>
<body><main><h1>The Spire</h1><p>A deterministic fixture for local form navigation and review queues.</p>
<form><input name="name" placeholder="Your Name" required><input name="class" placeholder="Your Class" required><input type="submit" value="Ascend"></form>
<button data-target="details" type="button">Show details</button><p id="details" hidden style="position:absolute;top:0;left:0">Local toggles work and this expanded paragraph must occupy its own space.</p>
<button data-dialog="modal">Open dialog</button><dialog id="modal"><h2>Local dialog</h2><button data-close="true">Close dialog</button></dialog>
<p style="min-height:900px">Scroll here to verify that Back restores position.</p></main></body></html>'''

class FixtureEngine:
    state='ready'
    error=''
    process=None
    def interrupt(self): pass
    def stop(self): pass
    def generate(self,prompt,context,cancel,seed,progress,repair=None):
        raw=PAGE if not prompt.startswith('Ascend') else '<html><body><h1>Arrived</h1><p>'+html.escape(prompt)+'</p></body></html>'
        return raw, {'finish':'stop','seconds':0,'characters':len(raw)}
    def review(self,page,layout,screenshot,cancel):
        if cancel.wait(8): raise Cancelled()
        return {'issues':[],'summary':'Fixture review complete.','visual':False}

if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='elsewhere-smoke-') as data:
        app=App(data,start_engine=False)
        app.engine=FixtureEngine()
        print(app.url,flush=True)
        try: threading.Event().wait()
        except KeyboardInterrupt: pass
        finally: app.stop()
