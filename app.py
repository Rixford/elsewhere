"""Elsewhere desktop host. No inference or asset downloads occur here."""
import argparse
import io
import json
import logging
import os
from pathlib import Path
import sys
import threading
from urllib.parse import urlsplit

from backend import App

ROOT = Path(__file__).resolve().parent

def desktop(app):
    os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = '--disable-background-networking --disable-component-update --disable-sync --no-first-run --disable-features=msEdgeSidebarV2 --host-resolver-rules="MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1"'
    import webview
    webview.settings['ALLOW_DOWNLOADS'] = False
    webview.settings['ALLOW_FILE_URLS'] = False
    webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = False
    # Pinned pywebview adapter: attach guards before its on-ready handler navigates.
    from webview.platforms.edgechromium import EdgeChrome
    from Microsoft.Web.WebView2.Core import CoreWebView2WebResourceContext, CoreWebView2PermissionState, CoreWebView2CapturePreviewImageFormat
    from System import Action
    from System.IO import MemoryStream
    from System.Threading.Tasks import Task
    original_ready = EdgeChrome.on_webview_ready
    native = {}

    def ready(browser, sender, args):
        if not args.IsSuccess:
            return original_ready(browser,sender,args)
        core = sender.CoreWebView2
        def navigate(_sender, event):
            parsed=urlsplit(str(event.Uri))
            if str(event.Uri) not in ('about:blank','about:srcdoc') and not (parsed.scheme=='http' and parsed.netloc==urlsplit(app.origin).netloc and parsed.path in ('/','/index.html')):
                event.Cancel=True
                app.blocked_requests+=1
        def resource(_sender,event):
            url=str(event.Request.Uri)
            parsed=urlsplit(url)
            if not (parsed.scheme=='http' and parsed.netloc==urlsplit(app.origin).netloc):
                event.Response=core.Environment.CreateWebResourceResponse(None,403,'Offline','Content-Type: text/plain')
                app.blocked_requests+=1
        def permission(_sender,event):
            event.State=CoreWebView2PermissionState.Deny
            event.Handled=True
        core.NavigationStarting += navigate
        core.FrameNavigationStarting += navigate
        core.PermissionRequested += permission
        core.AddWebResourceRequestedFilter('*',CoreWebView2WebResourceContext.All)
        core.WebResourceRequested += resource
        native.update(browser=browser,core=core,handlers=(navigate,resource,permission))
        app.guard_status='native'
        original_ready(browser,sender,args)
        core.Settings.IsWebMessageEnabled=False  # No page-to-Python bridge.
        core.Settings.AreHostObjectsAllowed=False
        core.Settings.IsPasswordAutosaveEnabled=False
        core.Settings.IsGeneralAutofillEnabled=False
        core.Settings.AreDefaultScriptDialogsEnabled=False

    def no_popup(_browser,_sender,args):
        args.Handled=True
        app.blocked_requests+=1
    EdgeChrome.on_webview_ready=ready
    EdgeChrome.on_new_window_request=no_popup
    EdgeChrome.on_script_notify=lambda *args: None

    window=webview.create_window('Elsewhere',app.url,width=1280,height=840,min_size=(640,480),background_color='#fcfcfa',text_select=True)
    def capture(job_id,revision):
        browser=native.get('browser')
        if not browser:return None
        info=browser.evaluate_js('JSON.stringify(window.elsewhereCaptureInfo())',True)
        if isinstance(info,str):info=json.loads(info)
        if not info or info.get('job')!=job_id or info.get('revision')!=revision or info.get('panel'):
            return None
        browser.evaluate_js('window.elsewherePauseMotion(); true',True)
        finished=threading.Event()
        holder={}
        def begin():
            stream=MemoryStream()
            def complete(task):
                try:
                    if task.IsFaulted:raise RuntimeError(str(task.Exception))
                    holder['bytes']=bytes(stream.ToArray())
                except Exception as exc:holder['error']=str(exc)
                finally:stream.Dispose();finished.set()
            native['core'].CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png,stream).ContinueWith(Action[Task](complete))
        browser.webview.Invoke(Action(begin))
        if not finished.wait(8):return None
        check=browser.evaluate_js('JSON.stringify(window.elsewhereCaptureInfo())',True)
        if isinstance(check,str):check=json.loads(check)
        if not check or check.get('job')!=job_id or check.get('revision')!=revision:return None
        if not holder.get('bytes'):return None
        from PIL import Image
        image=Image.open(io.BytesIO(holder['bytes']))
        rect=info['rect'];sx=image.width/rect['viewportWidth'];sy=image.height/rect['viewportHeight']
        image=image.crop((round(rect['x']*sx),round(rect['y']*sy),round((rect['x']+rect['width'])*sx),round((rect['y']+rect['height'])*sy)))
        image.thumbnail((1100,850))
        output=io.BytesIO();image.save(output,format='PNG')
        return output.getvalue()
    app.capture=capture
    window.events.closed += app.stop
    webview.start(gui='edgechromium',private_mode=True,storage_path=str(app.data/'webview'),debug=False,icon=str(ROOT/'Elsewhere.ico') if (ROOT/'Elsewhere.ico').exists() else None)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--headless',action='store_true')
    parser.add_argument('--data')
    args=parser.parse_args()
    configured=(ROOT/'runtime-path.txt').read_text(encoding='utf-8').strip() if (ROOT/'runtime-path.txt').exists() else str(Path(os.environ['LOCALAPPDATA'])/'Elsewhere')
    data=Path(args.data or configured)
    (data/'logs').mkdir(parents=True,exist_ok=True)
    import msvcrt
    instance_lock=(data/'instance.lock').open('a+b')
    instance_lock.seek(0)
    try:
        msvcrt.locking(instance_lock.fileno(),msvcrt.LK_NBLCK,1)
        if instance_lock.read(1)==b'':instance_lock.write(b'0');instance_lock.flush()
    except OSError:
        instance_lock.close()
        return
    logging.basicConfig(filename=str(data/'logs'/'app.log'),level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    app=App(data)
    # Local test/diagnostic discovery; this token never appears in general logs.
    (data/'session.json').write_text(json.dumps({'origin':app.origin,'token':app.token,'pid':os.getpid()}),encoding='utf-8')
    try:
        if args.headless:
            threading.Event().wait()
        else:desktop(app)
    finally:
        app.stop()
        instance_lock.close()

if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:pass
    except Exception:
        logging.exception('Elsewhere failed to start')
        raise
