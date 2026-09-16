"""Small official-API adapters. Credentials live in backend memory only."""
import http.client
import json
import re
import threading
import time

from engine import Engine, Cancelled

PRESETS = {
    'openai': ['gpt-6-astra', 'gpt-5.6-sol', 'gpt-5.6-terra', 'gpt-5.6-luna'],
    'anthropic': ['claude-opus-5', 'claude-sonnet-5', 'claude-fable-5-1', 'claude-haiku-4-5-20251001'],
}
HOSTS = {'openai': ('api.openai.com', '/v1/responses'), 'anthropic': ('api.anthropic.com', '/v1/messages')}


class ProviderError(RuntimeError):
    """Provider errors/refusals stop the pipeline; never retry with another model."""


def checked_route(body, keys):
    provider=body.get('provider','local')
    if provider not in ('local', *HOSTS): raise ValueError('Choose Local, OpenAI or Anthropic.')
    if provider=='local': return {'provider':'local','model':'Qwen3.5-4B-Q4_K_M'}, None
    model=body.get('model','')
    prefix=r'gpt-[a-zA-Z0-9.-]+' if provider=='openai' else r'claude-[a-zA-Z0-9.-]+'
    if not isinstance(model,str) or len(model)>100 or not re.fullmatch(prefix,model):
        raise ValueError('Enter a valid model ID for the selected provider.')
    if body.get('cloud_consent') is not True:
        raise ValueError('Confirm that prompts and page context may be sent to this provider.')
    key=body.get('api_key','')
    if not isinstance(key,str) or len(key)>4096 or any(ord(c)<33 or ord(c)>126 for c in key):
        raise ValueError('The API key contains invalid characters.')
    key=key or keys.get(provider)
    if not key: raise ValueError('Enter an API key for this app session.')
    workspace=body.get('workspace','')
    if not isinstance(workspace,str) or len(workspace)>100 or (workspace and not re.fullmatch(r'wrkspc_[a-zA-Z0-9_-]+',workspace)):
        raise ValueError('Invalid Claude workspace ID.')
    return {'provider':provider,'model':model,'workspace':workspace if provider=='anthropic' else ''}, key


class CloudEngine(Engine):
    def __init__(self, route, key):
        # Reuse generation/review/repair prompts, not the local server lifecycle.
        self.provider=route['provider']
        self.model=route['model']
        self.workspace=route.get('workspace','')
        self.key=key
        self.state='ready'
        self.error=''
        self.connection=None
        self.lock=threading.Lock()
        self.stopping=threading.Event()

    def payload(self, messages, tokens, json_output):
        system='\n'.join(m['content'] for m in messages if m['role']=='system')
        converted=[]
        for message in messages:
            if message['role']=='system': continue
            content=message['content']
            if isinstance(content,list):
                blocks=[]
                for block in content:
                    if block['type']=='text':
                        blocks.append({'type':'input_text' if self.provider=='openai' else 'text','text':block['text']})
                    elif block['type']=='image_url':
                        uri=block['image_url']['url']
                        if not uri.startswith('data:image/png;base64,'): raise ValueError('Only local PNG review images are supported.')
                        if self.provider=='openai': blocks.append({'type':'input_image','image_url':uri})
                        else: blocks.append({'type':'image','source':{'type':'base64','media_type':'image/png','data':uri.split(',',1)[1]}})
                content=blocks
            converted.append({'role':message['role'],'content':content})
        # Cloud reasoning also consumes the output budget. No local sampling or
        # seed parameters are passed to APIs that do not support them.
        budget=tokens+4096
        if self.provider=='openai':
            payload={'model':self.model,'instructions':system,'input':converted,'stream':True,'store':False,'max_output_tokens':budget}
            if self.model.startswith(('gpt-5','gpt-6')): payload['reasoning']={'effort':'low'}
            if json_output: payload['text']={'format':{'type':'json_object'}}
            return payload
        return {'model':self.model,'system':system,'messages':converted,'stream':True,'max_tokens':budget}

    def generate(self, *args, **kwargs):
        raw,stats=super().generate(*args,**kwargs)
        if not re.search(r'<html\b',raw,re.I):
            raise ProviderError('The provider returned a response instead of an HTML page. It was not automatically retried.')
        return raw,stats

    def complete(self, messages, cancel, *, tokens=3200, temperature=.9, seed=0, progress=None, json_output=False):
        with self.lock:
            if cancel.is_set(): raise Cancelled()
            host,path=HOSTS[self.provider]
            headers={'Content-Type':'application/json','Accept':'text/event-stream'}
            if self.provider=='openai': headers['Authorization']='Bearer '+self.key
            else:
                headers.update({'x-api-key':self.key,'anthropic-version':'2023-06-01'})
                if self.workspace: headers['anthropic-workspace-id']=self.workspace
            payload=self.payload(messages,tokens,json_output)
            conn=http.client.HTTPSConnection(host,timeout=60)
            self.connection=conn
            started=time.monotonic()
            # Close even an idle stream at the total deadline; cancellation closes
            # the socket too. No automatic retries that could duplicate billing.
            deadline=threading.Timer(240,self.interrupt)
            deadline.daemon=True
            deadline.start()
            pieces=[]
            count=0
            finish=None
            terminal=False
            usage={}
            try:
                conn.request('POST',path,json.dumps(payload).encode('utf-8'),headers)
                response=conn.getresponse()
                if response.status!=200:
                    hints={400:'Check the model ID and its supported features.',401:'Check your API key.',403:'This key does not have access to the requested model.',404:'This model is unavailable to your account.',429:'Rate limit or API credit limit reached. Wait or check provider billing.'}
                    raise ProviderError(f'{self.provider.title()} API returned {response.status}. '+hints.get(response.status,'The provider could not complete the request. Try again later.'))
                event_lines=[]
                while True:
                    if cancel.is_set(): raise Cancelled()
                    line=response.readline(1048577)
                    if len(line)>1048576: raise ProviderError('The provider sent an oversized stream event.')
                    if not line: break
                    if line.strip():
                        if line.startswith(b'data:'): event_lines.append(line[5:].strip())
                        if sum(map(len,event_lines))>1048576: raise ProviderError('The provider sent an oversized stream event.')
                        continue
                    if not event_lines: continue
                    event=json.loads(b'\n'.join(event_lines));event_lines=[]
                    kind=event.get('type','')
                    text=''
                    if kind in ('error','response.failed','response.cancelled'):
                        raise ProviderError('The provider stopped this request. Check your model access, quota or provider status.')
                    if self.provider=='openai':
                        if kind.startswith('response.refusal'):
                            raise ProviderError('OpenAI declined this request. It was not retried or sent to another model.')
                        if kind=='response.output_text.delta': text=event.get('delta','')
                        if kind in ('response.completed','response.incomplete'):
                            final=event.get('response',{})
                            if any(block.get('type')=='refusal' for item in final.get('output',[]) for block in item.get('content',[])):
                                raise ProviderError('OpenAI declined this request. It was not retried or sent to another model.')
                            if kind=='response.incomplete':
                                raise ProviderError('OpenAI could not finish within the output limit. Try a shorter page request.')
                            usage=final.get('usage',{})
                            terminal=True;finish='stop';break
                    else:
                        delta=event.get('delta',{})
                        # Current Claude responses can include a structured refusal
                        # alongside legacy stop_reason=refusal.
                        details=delta.get('stop_details') or event.get('stop_details') or event.get('message',{}).get('stop_details') or {}
                        refusal=event.get('refusal') or event.get('message',{}).get('refusal') or delta.get('refusal') or details.get('type')=='refusal'
                        if refusal or event.get('content_block',{}).get('type')=='refusal':
                            raise ProviderError('Claude declined this request. It was not retried or sent to another model.')
                        if kind=='content_block_delta' and delta.get('type')=='text_delta': text=delta.get('text','')
                        if kind=='message_start': usage.update(event.get('message',{}).get('usage',{}))
                        if kind=='message_delta':
                            reason=delta.get('stop_reason')
                            if reason and reason not in ('end_turn','stop_sequence'):
                                raise ProviderError('Claude did not complete the page ('+str(reason)[:40]+'). The request was not retried.')
                            if reason: finish='stop'
                            usage.update(event.get('usage',{}))
                        if kind=='message_stop': terminal=True;break
                    if text:
                        count+=len(text)
                        if count>180000: raise ProviderError('The generated document exceeded the size limit.')
                        pieces.append(text)
                        if progress: progress(count)
                if cancel.is_set(): raise Cancelled()
                if not terminal or finish!='stop': raise ProviderError('The provider connection ended before completion. Retry when ready.')
                if not pieces: raise ProviderError('The provider returned no usable text.')
                safe_usage={k:v for k,v in usage.items() if k in ('input_tokens','output_tokens','total_tokens','cache_read_input_tokens','cache_creation_input_tokens') and isinstance(v,int)}
                return ''.join(pieces), {'seconds':round(time.monotonic()-started,2),'finish':finish,'characters':count,'usage':safe_usage}
            except ProviderError:
                raise
            except Exception:
                if cancel.is_set(): raise Cancelled() from None
                raise ProviderError('The cloud request could not complete. Check your connection or provider status; no automatic retry was made.') from None
            finally:
                deadline.cancel()
                self.connection=None
                conn.close()
