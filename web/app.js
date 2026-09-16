'use strict';
const $ = id => document.getElementById(id);
const token = location.hash.slice(1);
history.replaceState(null, '', '/');
const state = {tabs:[],current:null,job:null,jobTab:null,starting:false,startTab:null,stopping:null,revision:0,status:null,displayed:null,validation:null,panel:null,lastPrompt:'',timer:null,queued:null,pending:[],progress:null,switchEpoch:0,tabSignature:null};
async function api(path, body) {
  const response = await fetch('/api/' + path, {method:body ? 'POST':'GET',headers:{'X-Elsewhere-Token':token,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined});
  const result = await response.json();
  if(!response.ok) throw new Error(result.error || 'The local application did not respond.');
  return result;
}
function toast(message) { $('toast').textContent=message;$('toast').hidden=false;clearTimeout(state.timer);state.timer=setTimeout(()=>$('toast').hidden=true,6000); }
const current = () => state.tabs.find(t=>t.id===state.current);
const saved = () => {const t=current();return t?.pages[t.index] || null;};
function tabTitle(tab) {const queued=state.pending.find(p=>p.tab===tab.id);return tab.id===state.jobTab && state.job ? '◌ '+state.lastPrompt : queued?'… '+queued.prompt:(tab.pages[tab.index]?.title || 'New possibility');}
function drawTabs() {
  const signature=JSON.stringify(state.tabs.map(tab=>[tab.id,tabTitle(tab),tab.id===state.current]));
  if(signature!==state.tabSignature){state.tabSignature=signature;
  $('tabs').replaceChildren();
  for(const tab of state.tabs) {
    const el=document.createElement('div');el.className='tab'+(tab.id===state.current?' active':'');el.setAttribute('role','tab');el.setAttribute('aria-selected',String(tab.id===state.current));el.tabIndex=0;
    const label=document.createElement('span');label.textContent=tabTitle(tab);el.append(label);
    const close=document.createElement('button');close.textContent='×';close.title='Close tab';close.setAttribute('aria-label','Close '+label.textContent);close.onclick=e=>{e.stopPropagation();closeTab(tab.id);};el.append(close);
    el.onclick=()=>switchTab(tab.id);el.onkeydown=e=>{if(e.key==='Enter')switchTab(tab.id);};$('tabs').append(el);
  }
  }
  const t=current();$('back').disabled=!t || (t.index<=0&&!(state.jobTab===t.id&&t.index>=0));$('forward').disabled=!t || t.index>=t.pages.length-1;
  $('reload').disabled=!saved();$('reimagine').disabled=!saved();$('details-button').hidden=!saved();
  $('stop').hidden=!state.job||state.current!==state.jobTab;
  const marked=!!state.status?.bookmarks?.some(p=>p.id===saved()?.id);
  $('bookmark').disabled=!saved()||(!!state.job&&state.jobTab===state.current);$('bookmark').textContent=marked?'★':'☆';$('bookmark').setAttribute('aria-label',marked?'Remove bookmark':'Bookmark this page');
}
function newTab() {if(state.tabs.length>=8){toast('Eight tabs are open. Close one to keep things light.');return;} const tab={id:crypto.randomUUID(),pages:[],index:-1};state.tabs.push(tab);switchTab(tab.id);$('address').focus();}
async function captureView(){const page=state.displayed;if(!page)return;return new Promise(resolve=>{page.captureDone=resolve;$('page').contentWindow.postMessage({snapshot:true,capability:page.page.capability},'*');setTimeout(resolve,180);});}
async function switchTab(id) {const epoch=++state.switchEpoch;if(state.displayed)await captureView();if(epoch!==state.switchEpoch||!state.tabs.some(t=>t.id===id))return;state.current=id;renderCurrent();closePanel();}
async function closeTab(id) {if(state.starting&&state.startTab===id){toast('Starting this page; try again in a moment.');return;}state.pending=state.pending.filter(p=>p.tab!==id);if(state.queued?.tab===id)state.queued=null;if(state.jobTab===id&&state.job)await stop(false);const index=state.tabs.findIndex(t=>t.id===id);if(index<0)return;state.tabs.splice(index,1);if(!state.tabs.length)newTab();else if(state.current===id)await switchTab(state.tabs[Math.max(0,index-1)].id);drawTabs();drainQueue();}
function showPage(page, job=null, revision=0) {
  state.displayed={page,job,revision};
  $('blank').hidden=true;$('error').hidden=true;$('loading').hidden=true;
  // A fresh sandbox prevents a cancelled srcdoc navigation from leaving a
  // restored history entry with a detached, blank document in Chromium hosts.
  const oldFrame=$('page'),frame=oldFrame.cloneNode(false);
  frame.hidden=false;frame.srcdoc=page.html;oldFrame.replaceWith(frame);
  $('address').value=job?state.lastPrompt:page.prompt;
  $('imagined-label').hidden=false;
  $('review-chip').hidden=!job;
}
function renderSaved() {
  const page=saved();state.displayed=null;
  $('error').hidden=true;$('loading').hidden=true;$('review-chip').hidden=true;
  if(page){showPage(page);$('page-status').textContent=`Imagined in ${page.seconds}s · ${state.status?.bookmarks?.some(p=>p.id===page.id)?'bookmarked':'cached'}`;}
  else{$('page').hidden=true;$('page').removeAttribute('srcdoc');$('blank').hidden=false;$('address').value='';$('imagined-label').hidden=true;$('page-status').textContent='A blank page. An open possibility.';}
  drawTabs();
}
function renderCurrent(){
  if(state.job&&state.jobTab===state.current){
    const job=state.progress;
    if(job?.page){state.revision=job.revision;showPage(job.page,state.job,job.revision);}
    else{state.displayed=null;$('page').hidden=true;$('blank').hidden=true;$('error').hidden=true;$('loading').hidden=false;$('review-chip').hidden=true;}
    $('address').value=state.lastPrompt;$('loading-stage').textContent=job?.stage||'Imagining your page';$('review-stage').textContent=job?.stage||'Imagining your page';$('page-status').textContent=job?.stage||'Imagining your page';drawTabs();return;
  }
  renderSaved();
  const failure=current()?.failure;
  if(failure&&!saved()){$('blank').hidden=true;$('error').hidden=false;$('error-message').textContent=failure.message;$('address').value=failure.prompt;}
  const pending=state.pending.find(p=>p.tab===state.current);
  if(pending){$('page-status').textContent='Queued · another tab is using the model';if(!saved()){$('blank').hidden=true;$('loading').hidden=false;$('loading-stage').textContent='Queued for the model';$('loading-detail').textContent='You can browse other tabs while this waits.';$('address').value=pending.prompt;}}
}
function enqueue(request){state.pending=state.pending.filter(p=>p.tab!==request.tab);state.pending.push(request);drawTabs();toast('Queued in this tab. The other page will continue building.');}
function drainQueue(){if(state.job||state.starting||state.stopping)return;const next=state.pending.shift();if(!next)return;if(!state.tabs.some(t=>t.id===next.tab)){drainQueue();return;}navigate(next.prompt,next.parent,next.seed,next.link,next.tab);}
async function navigate(prompt, parentId=null, seed=null, link=null, tabId=state.current) {
  prompt=prompt.trim();if(!prompt)return;
  const tab=state.tabs.find(t=>t.id===tabId);if(!tab)return;
  tab.failure=null;
  if(state.starting||(state.job&&state.jobTab!==tab.id)){enqueue({tab:tab.id,prompt,parent:parentId,seed,link});if(state.current===tab.id)renderCurrent();return;}
  state.starting=true;
  state.startTab=tab.id;
  tab.request={prompt,parent:parentId,seed,link};
  state.pending=state.pending.filter(p=>p.tab!==tab.id);
  state.queued=null;
  try {
    if(state.current===tab.id)await captureView();
    if(state.stopping)await state.stopping;else if(state.job)await stop(false);
    if(state.current===tab.id)closePanel();state.lastPrompt=prompt;
    const result=await api('generate',{prompt,parent:parentId,seed,link});
    state.job=result.id;state.jobTab=tab.id;state.revision=0;state.progress=null;
    if(state.current===tab.id){$('address').value=prompt;$('blank').hidden=true;$('page').hidden=true;$('error').hidden=true;$('loading').hidden=false;$('loading-stage').textContent='Imagining your page';$('loading-detail').textContent='';$('review-chip').hidden=true;}
    $('stop').hidden=false;
    drawTabs();pollJob(result.id);
  }catch(error){toast(error.message);}finally{state.starting=false;state.startTab=null;if(!state.job)drainQueue();}
}
async function pollJob(id) {
  if(state.job!==id)return;
  try {
    const job=await api('jobs/'+id);
    if(state.job!==id)return;
    const visible=state.current===state.jobTab;
    if(job.page&&state.progress?.revision===job.revision)job.page.viewState=state.displayed?.job===id?state.displayed.page.viewState:state.progress.page?.viewState;
    state.progress=job;
    if(job.page&&(state.validation?.job!==id||state.validation?.revision!==job.revision)){
      state.validation={page:job.page,job:id,revision:job.revision};
      const rect=$('viewport').getBoundingClientRect();$('validation-frame').style.width=rect.width+'px';$('validation-frame').style.height=rect.height+'px';$('validation-frame').srcdoc=job.page.html;
    }
    const validation=state.validation;
    if(validation?.job===id&&!validation.reported){$('validation-frame').contentWindow.postMessage({measure:true,capability:validation.page.capability},'*');}
    if(visible){
      $('loading-stage').textContent=job.stage;
      $('loading-detail').textContent=`${Math.floor(Date.now()/1000-job.started)}s${job.chars?' · '+Math.round(job.chars/4).toLocaleString()+' approximate tokens':''}`;
      $('review-stage').textContent=job.stage;
      $('page-status').textContent=job.stage;
      if(job.page&&(state.revision!==job.revision||state.displayed?.job!==id)) {state.revision=job.revision;showPage(job.page,id,job.revision);}
    }
    if(job.state==='done') {
      const tab=state.tabs.find(t=>t.id===state.jobTab);
      if(tab){job.result.viewState=state.displayed?.job===id?state.displayed.page.viewState:job.page?.viewState;tab.pages=tab.pages.slice(0,tab.index+1);tab.pages.push(job.result);tab.index=tab.pages.length-1;}
      state.job=null;state.jobTab=null;state.progress=null;$('stop').hidden=true;
      if(visible)renderSaved();drawTabs();refreshStatus();followQueued(job.result.id);return;
    }
    if(job.state==='error'||job.state==='cancelled') {
      const owner=state.tabs.find(t=>t.id===state.jobTab);
      if(owner&&job.state==='error'){owner.failure={...owner.request,message:job.error};if(!visible)toast('Page failed in '+state.lastPrompt+': '+job.error);}
      state.job=null;state.jobTab=null;state.progress=null;$('stop').hidden=true;
      if(visible){renderSaved();if(job.state==='error'){if(saved())toast(job.error);else{$('blank').hidden=true;$('error').hidden=false;$('error-message').textContent=job.error;$('address').value=state.lastPrompt;}}}
      drawTabs();if(state.queued){state.queued=null;toast('The page could not finish. Your queued link was not opened; retry the page first.');}drainQueue();return;
    }
  } catch(error) {toast(error.message);}
  setTimeout(()=>pollJob(id),500);
}
async function stop(runNext=true) {
  state.queued=null;
  if(state.stopping)return state.stopping;
  const id=state.job;if(!id)return;
  state.stopping=(async()=>{
    let stopped=false;
    for(let attempt=0;attempt<2&&!stopped;attempt++){const result=await api('cancel',{id});stopped=result.stopped;}
    if(!stopped)throw new Error('The model is still stopping. Wait a moment before navigating.');
    if(state.job===id){const visible=state.current===state.jobTab;state.job=null;state.jobTab=null;state.progress=null;$('stop').hidden=true;if(visible)renderSaved();drawTabs();}
  })();
  try{await state.stopping;}finally{state.stopping=null;if(runNext)drainQueue();}
}
function followQueued(parentId){
  const queued=state.queued;state.queued=null;
  if(queued&&state.tabs.some(t=>t.id===queued.tab)){state.pending=state.pending.filter(p=>p.tab!==queued.tab);state.pending.push({...queued,parent:queued.fromJob?parentId:queued.parent});}
  drainQueue();
}
async function refreshStatus() {
  try{
    state.status=await api('status');const ready=state.status.engine==='ready';
    $('engine-dot').className=state.status.engine;
    const cloud=state.status.router?.provider && state.status.router.provider!=='local';
    $('mode-label').textContent=cloud?'CLOUD':'LOCAL';
    $('engine-status').textContent=ready?(cloud?state.status.router.provider==='openai'?'OpenAI · '+state.status.model:'Claude · '+state.status.model:'On device · Qwen3.5 4B'):state.status.engine==='error'?'Model unavailable':'Loading local model…';
    $('engine-status').title=state.status.error || (cloud?'Cloud selected for new requests. Active jobs keep their original model.':'All new generation happens on this computer.');
    applySettingsTheme();
    $('go').disabled=!ready;drawTabs();
  }catch(error){$('engine-status').textContent='Disconnected';}
}
function applySettingsTheme(){$('panel').setAttribute('data-dark',String(state.panel==='settings'&&!!state.status?.settings.dark_settings));}
function closePanel(){$('panel').hidden=true;$('panel-content').replaceChildren();state.panel=null;applySettingsTheme();}
function panel(title,kind){state.panel=kind;$('panel').hidden=false;$('panel-title').textContent=title;$('panel-content').replaceChildren();applySettingsTheme();return $('panel-content');}
function paragraph(parent,text,cls='panel-note'){const p=document.createElement('p');p.className=cls;p.textContent=text;parent.append(p);return p;}
function action(parent,text,fn){const b=document.createElement('button');b.className='secondary';b.textContent=text;b.onclick=fn;parent.append(b);return b;}
async function showHistory(){if(state.panel==='history'){closePanel();return;}await refreshStatus();const content=panel('Recent pages','history');paragraph(content,'New pages are cached for 24 hours and expire on a later launch. Bookmark pages to keep them. Your older archive is preserved.');if(!state.status?.history.length)paragraph(content,'Your first destination is waiting in the address bar.');for(const item of state.status?.history||[]){const button=document.createElement('button');button.className='history-item';const title=document.createElement('strong');title.textContent=item.title;const desc=document.createElement('small');desc.textContent=item.prompt+' · '+new Date(item.created*1000).toLocaleDateString();button.append(title,desc);button.onclick=()=>openSavedPage(item.id);content.append(button);}}
async function openSavedPage(id){
  const tab=current();if(!tab)return;
  try{await captureView();state.pending=state.pending.filter(p=>p.tab!==tab.id);if(state.job&&state.jobTab===tab.id)await stop(false);const page=await api('pages/'+id);if(!state.tabs.includes(tab))return;tab.pages=tab.pages.slice(0,tab.index+1);tab.pages.push(page);tab.index=tab.pages.length-1;if(state.current===tab.id){renderSaved();closePanel();}drawTabs();drainQueue();}catch(e){toast(e.message);}
}
async function toggleBookmark(){const page=saved();if(!page||state.displayed?.job)return;try{const enabled=!state.status?.bookmarks?.some(p=>p.id===page.id);await api('bookmark',{id:page.id,enabled});await refreshStatus();toast(enabled?'Bookmarked permanently on this computer.':'Bookmark removed. The page remains in the temporary cache.');}catch(e){toast(e.message);}}
async function showBookmarks(){if(state.panel==='bookmarks'){closePanel();return;}await refreshStatus();const content=panel('Bookmarks','bookmarks');paragraph(content,'Saved permanently on this computer. Use the star or Ctrl+D to save the current page.');for(const item of state.status?.bookmarks||[]){action(content,item.title,()=>openSavedPage(item.id));}if(!state.status?.bookmarks?.length)paragraph(content,'No bookmarks yet.');}
function modelSettings(content){
  const route=state.status?.router||{provider:'local',presets:{}};
  const form=document.createElement('div');form.className='model-settings';content.append(form);
  function field(label,node){const wrap=document.createElement('label');wrap.className='model-field';const text=document.createElement('span');text.textContent=label;wrap.append(text,node);form.append(wrap);return wrap;}
  function option(select,value,title){const node=document.createElement('option');node.value=value;node.textContent=title;select.append(node);}
  const provider=document.createElement('select');provider.id='model-provider';provider.setAttribute('aria-label','Model provider');
  for(const [value,title] of [['local','Local · Qwen3.5 4B'],['openai','OpenAI API'],['anthropic','Anthropic · Claude API']])option(provider,value,title);
  provider.value=route.provider;field('Model provider',provider);
  const model=document.createElement('select');model.setAttribute('aria-label','Cloud model');const modelField=field('Model',model);
  const custom=document.createElement('input');custom.type='text';custom.maxLength=100;custom.placeholder='Exact model ID';custom.setAttribute('aria-label','Custom model ID');const customField=field('Custom model ID',custom);
  const key=document.createElement('input');key.type='password';key.autocomplete='off';key.spellcheck=false;key.maxLength=4096;key.setAttribute('aria-label','API key');const keyField=field('API key · this app session only',key);
  const workspace=document.createElement('input');workspace.type='text';workspace.maxLength=100;workspace.placeholder='wrkspc_…';workspace.setAttribute('aria-label','Claude workspace ID');const workspaceField=field('Claude workspace ID (only if your key requires it)',workspace);
  const notice=paragraph(form,'');notice.className='model-notice';
  const use=action(form,'Use local model',async()=>{
    use.disabled=true;
    try{state.status.router=await api('router',{provider:provider.value,model:model.value==='custom'?custom.value.trim():model.value,api_key:key.value,workspace:workspace.value.trim(),cloud_consent:provider.value!=='local'});key.value='';await refreshStatus();key.placeholder=state.status.router.keys[provider.value]?'Session key is set; leave blank to keep it':'Paste your provider API key';toast(provider.value==='local'?'Local Qwen selected.':'Cloud model selected for new and queued requests.');}
    catch(e){toast(e.message);}finally{use.disabled=false;}
  });
  function render(){const cloud=provider.value!=='local';modelField.hidden=keyField.hidden=!cloud;workspaceField.hidden=provider.value!=='anthropic';model.replaceChildren();for(const id of route.presets[provider.value]||[])option(model,id,id);option(model,'custom','Custom model ID…');model.value=(route.presets[provider.value]||[]).includes(route.model)?route.model:(route.provider===provider.value&&route.model?'custom':(route.presets[provider.value]||[])[0]||'custom');custom.value=route.provider===provider.value?route.model||'':'';customField.hidden=!cloud||model.value!=='custom';key.value='';key.placeholder=state.status?.router?.keys?.[provider.value]?'Session key is set; leave blank to keep it':'Paste your provider API key';workspace.value=provider.value===route.provider?route.workspace||'':'';
    notice.textContent=cloud?'Using this model sends prompts, linked-page context, generated HTML and enabled review screenshots to '+(provider.value==='openai'?'OpenAI':'Anthropic')+'. API charges and provider data policies apply. Generation, review and any refinement use this model. Keys are forgotten on exit; restart returns to Local.':'Qwen runs on this computer without internet or an API key. Model changes apply to the next request; active builds keep their current model.';
    use.textContent=cloud?'Use '+(provider.value==='openai'?'OpenAI':'Claude')+' · cloud':'Use local model';
  }
  provider.onchange=render;model.onchange=()=>{customField.hidden=model.value!=='custom';};render();
  action(form,'Clear session API keys',async()=>{try{state.status.router=await api('router',{forget_keys:true});key.value='';await refreshStatus();state.panel=null;showSettings();toast('Keys cleared. Local Qwen selected.');}catch(e){toast(e.message);}});
}
function showSettings(){if(state.panel==='settings'){closePanel();return;}const content=panel('Settings','settings');
  modelSettings(content);
  for(const [key,title,description] of [['dark_settings','Dark settings panel','Use a dark theme here. Imagined pages keep their own design.'],['memory','Carry the world forward','Remember an imagined place’s details as you follow its links. Turn off for independent interpretations.'],['review','Validation reviewer','Check language and structure with a separate model call. The reviewer preserves invented content.'],['visual','Look at the page','Include a screenshot in the review. With a cloud model, this image is sent to that provider. Requires this tab to be visible.']]){
    const label=document.createElement('label');label.className='setting';const copy=document.createElement('span');const strong=document.createElement('strong');strong.textContent=title;const small=document.createElement('small');small.textContent=description;copy.append(strong,small);const input=document.createElement('input');input.type='checkbox';input.checked=!!state.status?.settings[key];input.onchange=async()=>{try{state.status.settings=await api('settings',{[key]:input.checked});applySettingsTheme();}catch(e){toast(e.message);input.checked=!input.checked;}};label.append(copy,input);content.append(label);
  }
  paragraph(content,'Everything you enter is a creative prompt. Addresses never contact a real website. Code checks always run. Changes apply to the next page.');
  paragraph(content,'One selected model · separate validation context · at most one refinement.');
  paragraph(content,'Saved on this computer: '+(state.status?.data_path||''));
}
function showDetails(){const page=saved();if(!page)return;if(state.panel==='details'){closePanel();return;}const content=panel('Behind this page','details');paragraph(content,page.title);const dl=document.createElement('dl');dl.className='details-list';for(const [k,v] of [['Entry',page.prompt],['Model',page.model||'Qwen3.5 4B'],['Seed',page.provider&&page.provider!=='local'?'Not supported by cloud APIs':String(page.seed)],['Time',page.seconds+' seconds'],['Memory',page.settings.memory?'On':'Off'],['Review',page.review?.unavailable?'Unavailable':page.review?(page.review.visual?'Visual + language':'Language + structure'):'Code checks only'],['Refinement',page.repaired?'One pass':'None']]){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=k;dd.textContent=v;dl.append(dt,dd);}content.append(dl);if(page.review)paragraph(content,page.review.summary+(page.repaired?' This report describes the first version; the refinement was checked by code.':''),'review-report');for(const issue of page.review?.issues||[])paragraph(content,issue.detail,'review-report');const actions=document.createElement('div');actions.className='detail-actions';content.append(actions);
  action(actions,'Export HTML',async()=>{try{const result=await api('export',{id:page.id});toast('Saved: '+result.path);}catch(e){toast(e.message);}});
  action(actions,'View HTML',()=>{const pre=document.createElement('pre');pre.className='source';pre.textContent=page.html;content.append(pre);});
  action(actions,'Generation record',async()=>{try{const trace=await api('trace',{id:page.id});const pre=document.createElement('pre');pre.className='source';pre.textContent=JSON.stringify(trace,null,2);content.append(pre);}catch(e){toast(e.message);}});
  action(actions,page.provider&&page.provider!=='local'?'Imagine again':'Repeat seed',()=>navigate(page.prompt,null,page.seed));
}
window.addEventListener('message',event=>{
  if(event.source===$('validation-frame').contentWindow){
    const v=state.validation,d=event.data;
    if(v&&d&&d.elsewhere===true&&d.capability===v.page.capability&&d.kind==='layout'&&v.job===state.job&&!v.reported){
      const sample={width:Number(d.width)||0,overflow:d.overflow===true,overflowing:Array.isArray(d.overflowing)?d.overflowing.slice(0,6):[]};
      if(!v.wide){v.wide=sample;if(sample.width>640){$('validation-frame').style.width='640px';return;}}
      if(v.wide.width>640&&sample.width>640)return; // Ignore duplicate wide reports queued before resize.
      v.reported=true;
      const samples=v.wide===sample?[sample]:[v.wide,sample];
      api('rendered',{id:v.job,revision:v.revision,layout:{width:v.wide.width,overflow:samples.some(s=>s.overflow),overflowing:samples.flatMap(s=>s.overflowing).slice(0,6),samples:samples.map(s=>({width:s.width,overflow:s.overflow}))}}).catch(()=>{v.reported=false;});
    }
    return;
  }
  const displayed=state.displayed,data=event.data;
  if(event.source!==$('page').contentWindow||!displayed||!data||data.elsewhere!==true||data.capability!==displayed.page.capability)return;
  if((data.kind==='viewstate'||data.kind==='navigate')&&data.view&&typeof data.view==='object'&&JSON.stringify(data.view).length<250000){displayed.page.viewState=data.view;if(displayed.job===state.job&&state.progress?.page?.capability===displayed.page.capability)state.progress.page.viewState=data.view;displayed.captureDone?.();delete displayed.captureDone;}
  if(data.kind==='ready'&&displayed.page.viewState){$('page').contentWindow.postMessage({restore:displayed.page.viewState,capability:displayed.page.capability},'*');}
  if(data.kind==='navigate'&&typeof data.prompt==='string'&&data.prompt.trim()&&data.prompt.length<=600){
    if(state.job&&displayed.job===state.job){state.queued={prompt:data.prompt,tab:state.current,fromJob:true,parent:displayed.page.id||saved()?.id,link:data.link};toast('Link queued until this page finishes checking. Clicking another link replaces it.');}
    else navigate(data.prompt,displayed.page.id||saved()?.id,null,data.link);
  }
  if(data.kind==='shortcut'){if(data.key==='l'){$('address').focus();$('address').select();}if(data.key==='t')newTab();if(data.key==='w')closeTab(state.current);if(data.key==='d')toggleBookmark();}
});
// Read by the desktop screenshot provider; not a backend command bridge.
window.elsewhereCaptureInfo=()=>({job:state.displayed?.job,revision:state.displayed?.revision,panel:!!state.panel,rect:(()=>{const r=$('page').getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height,viewportWidth:innerWidth,viewportHeight:innerHeight};})()});
window.elsewherePauseMotion=()=>{try{$('review-chip').hidden=true;$('page').contentWindow.postMessage({freeze:true,capability:state.displayed?.page.capability},'*');}catch{}};
$('address-form').onsubmit=e=>{e.preventDefault();navigate($('address').value);};
$('new-tab').onclick=newTab;$('back').onclick=async()=>{const t=current();if(!t)return;state.pending=state.pending.filter(p=>p.tab!==t.id);await captureView();if(state.job&&state.jobTab===t.id){await stop();return;}if(t.index>0){t.index--;if(current()===t)renderSaved();}};$('forward').onclick=async()=>{const t=current();if(!t)return;state.pending=state.pending.filter(p=>p.tab!==t.id);await captureView();if(state.jobTab===t.id)await stop();if(t.index<t.pages.length-1){t.index++;if(current()===t)renderSaved();}};
$('reload').onclick=async()=>{if(state.jobTab===state.current)await stop();renderSaved();};$('reimagine').onclick=()=>{const p=saved();if(p)navigate(p.prompt,p.id);};$('retry').onclick=()=>{const failed=current()?.failure;navigate(failed?.prompt||$('address').value,failed?.parent,failed?.seed,failed?.link);};$('stop').onclick=()=>stop().catch(e=>toast(e.message));
$('history-button').onclick=showHistory;$('settings-button').onclick=showSettings;$('close-panel').onclick=closePanel;$('details-button').onclick=showDetails;
$('bookmark').onclick=toggleBookmark;$('bookmarks-button').onclick=showBookmarks;
document.addEventListener('keydown',event=>{
  if(event.key==='F5'){event.preventDefault();$('reload').click();}
  if(event.ctrlKey){const key=event.key.toLowerCase();if(['l','t','w','r'].includes(key)){event.preventDefault();if(key==='l'){$('address').focus();$('address').select();}if(key==='t')newTab();if(key==='w')closeTab(state.current);if(key==='r')$('reload').click();}}
  if(event.ctrlKey&&event.key.toLowerCase()==='d'){event.preventDefault();toggleBookmark();}
  if(event.altKey&&event.key==='ArrowLeft'){event.preventDefault();$('back').click();}if(event.altKey&&event.key==='ArrowRight'){event.preventDefault();$('forward').click();}
  if(event.key==='Escape'){if(state.panel)closePanel();else if(state.job&&state.jobTab===state.current)stop();}
});
newTab();refreshStatus();setInterval(refreshStatus,4000);
