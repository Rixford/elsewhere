(() => {
  'use strict';
  const capability = __CAPABILITY__;
  const send = (kind, extra = {}) => parent.postMessage({elsewhere: true, capability, kind, ...extra}, '*');
  addEventListener('message',event=>{if(event.source===parent&&event.data?.capability===capability&&event.data.freeze){const style=document.createElement('style');style.textContent='*,*::before,*::after{animation-play-state:paused!important;transition:none!important}';document.head.append(style);}});
  const intent = el => el.dataset.prompt || el.dataset.intent || el.getAttribute('aria-label') || el.value || el.textContent.trim().slice(0, 200);
  const runtimeStyle=document.createElement('style');
  runtimeStyle.textContent='[hidden]{display:none!important}dialog{max-width:min(90vw,760px);max-height:85vh;overflow:auto;margin:auto;padding:24px;border:1px solid #aaa;border-radius:12px}dialog::backdrop{background:#0008}';
  document.head.append(runtimeStyle);
  const fields=()=>[...document.querySelectorAll('input,textarea,select')];
  const viewState=()=>({x:scrollX,y:scrollY,fields:fields().map((el,index)=>({index,type:el.type,value:['text','search','textarea','select-one','number','range','date','color'].includes(el.type)?el.value.slice(0,1000):null,checked:el.checked})),details:[...document.querySelectorAll('details')].map(el=>el.open),panels:[...document.querySelectorAll('[data-target],[role="tab"]')].map(el=>{const id=el.dataset.target||el.getAttribute('aria-controls');const target=id&&document.getElementById(id.replace(/^#/,''));return target?{id:target.id,hidden:target.hidden}:null}).filter(Boolean)});
  function restore(view){
    if(!view||typeof view!=='object')return;
    for(const item of (view.fields||[]).slice(0,200)){const el=fields()[item.index];if(el&&el.type===item.type){if(typeof item.value==='string'&&el.type!=='password'&&el.type!=='email'&&el.type!=='file')el.value=item.value.slice(0,1000);if(typeof item.checked==='boolean')el.checked=item.checked;}}
    [...document.querySelectorAll('details')].forEach((el,i)=>{if(typeof view.details?.[i]==='boolean')el.open=view.details[i];});
    for(const item of (view.panels||[]).slice(0,100)){const el=document.getElementById(item.id);if(el&&typeof item.hidden==='boolean'){el.hidden=item.hidden;if(!item.hidden)expandFlow(el);}}
    document.querySelectorAll('[data-target],[aria-controls]').forEach(control=>{const id=control.dataset.target||control.getAttribute('aria-controls');const panel=id&&document.getElementById(id.replace(/^#/,''));if(panel)control.setAttribute(control.getAttribute('role')==='tab'?'aria-selected':'aria-expanded',String(!panel.hidden));});
    requestAnimationFrame(()=>scrollTo(Number(view.x)||0,Number(view.y)||0));
  }
  function normalFlow(el){
    for(const [key,value] of Object.entries({position:'static',inset:'auto',transform:'none',height:'auto','max-height':'none',overflow:'visible'}))el.style.setProperty(key,value,'important');
  }
  function expandFlow(target){
    if(target.closest('dialog'))return;
    normalFlow(target);
    if(getComputedStyle(target).display==='none')target.style.setProperty('display','block');
    target.style.setProperty('visibility','visible','important');target.style.setProperty('opacity','1','important');
    for(let p=target.parentElement;p&&p!==document.body;p=p.parentElement){const css=getComputedStyle(p);if(p.scrollHeight>p.clientHeight+8&&['hidden','clip'].includes(css.overflowY)){p.style.setProperty('height','auto','important');p.style.setProperty('max-height','none','important');p.style.setProperty('overflow','visible','important');}}
  }
  function repairCollisions(){
    const textBlocks=[...document.querySelectorAll('p,h1,h2,h3,li,form')].filter(el=>el.getBoundingClientRect().height>0).slice(0,160);
    for(const el of [...document.querySelectorAll('header,nav,aside,section,article,main,div')].slice(0,400)){
      if(el.closest('dialog')||el.hidden||el.textContent.trim().length<35)continue;
      if(!['fixed','sticky','absolute'].includes(getComputedStyle(el).position))continue;
      const a=el.getBoundingClientRect();if(!a.width||!a.height)continue;
      // Once a sidebar stacks above an article, sticking a viewport-height
      // block there would cover the article as soon as the reader scrolls.
      if((el.tagName==='ASIDE'||/(?:^|\s)sidebar(?:\s|$)/.test(el.className))&&a.width>innerWidth*.65&&a.height>innerHeight*.4){normalFlow(el);continue;}
      const collision=textBlocks.some(other=>{if(el.contains(other)||other.contains(el))return false;const b=other.getBoundingClientRect();return Math.min(a.right,b.right)-Math.max(a.left,b.left)>24&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>12;});
      if(collision)normalFlow(el);
    }
  }
  let viewTimer;
  const remember=()=>{clearTimeout(viewTimer);viewTimer=setTimeout(()=>send('viewstate',{view:viewState()}),120);};
  addEventListener('scroll',remember,{passive:true});
  document.addEventListener('change',remember);
  document.addEventListener('toggle',()=>{repairCollisions();remember();},true);
  addEventListener('message',event=>{if(event.source!==parent||event.data?.capability!==capability)return;if(event.data.snapshot)send('viewstate',{view:viewState()});if(event.data.restore)restore(event.data.restore);});
  const note = message => {
    let box = document.getElementById('elsewhere-local-note');
    if (!box) { box = document.createElement('div'); box.id = 'elsewhere-local-note'; document.body.appendChild(box); }
    box.textContent = message;
    box.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);padding:12px 20px;border-radius:12px;background:#20232e;color:white;font:14px system-ui;z-index:2147483647;box-shadow:0 4px 24px #0004;max-width:90vw';
    setTimeout(() => box.remove(), 4000);
  };
  document.addEventListener('click', event => {
    const el = event.target.closest('a,button,input[type="submit"],input[type="button"],input[type="reset"],[role="tab"],[data-target],[data-prompt],[data-dialog],[data-close],[data-filter]');
    if (!el || el.disabled) return;
    if(['INPUT','TEXTAREA','SELECT'].includes(el.tagName)&&!['submit','button','reset'].includes(el.type))return;
    if (['BUTTON','INPUT'].includes(el.tagName) && el.form && ['submit','reset'].includes(el.type)) return;
    event.preventDefault();
    if(el.hasAttribute('data-close')){el.closest('dialog')?.close();return;}
    if(el.dataset.dialog){const dialog=document.getElementById(el.dataset.dialog.replace(/^#/,''));if(dialog?.tagName==='DIALOG'){if(dialog.open)dialog.close();dialog.showModal();return;}}
    if(el.dataset.filter && !['INPUT','TEXTAREA'].includes(el.tagName)){
      const container=document.getElementById(el.dataset.filter.replace(/^#/,''));
      if(container){const value=(el.dataset.value||el.textContent).trim().toLowerCase();[...container.children].forEach(child=>child.hidden=value!=='all'&&!child.textContent.toLowerCase().includes(value));remember();return;}
    }
    const targetId = el.dataset.target || el.getAttribute('aria-controls');
    if (targetId) {
      const target = document.getElementById(targetId.replace(/^#/, ''));
      if (target) {
        if (el.getAttribute('role') === 'tab') {
          const group=el.closest('[role="tablist"]')||el.parentElement;
          group.querySelectorAll('[role="tab"]').forEach(tab => {tab.setAttribute('aria-selected', String(tab === el));const id=tab.dataset.target||tab.getAttribute('aria-controls');const panel=id&&document.getElementById(id.replace(/^#/,''));if(panel){panel.hidden=panel!==target;if(panel!==target)panel.style.removeProperty('display');}});
          target.hidden=false;expandFlow(target);
        } else { const css=getComputedStyle(target); const opening=target.hidden||css.display==='none'||css.visibility==='hidden'; target.hidden=!opening; if(!opening)target.style.removeProperty('display'); el.setAttribute('aria-expanded', String(opening)); }
        if(!target.hidden)expandFlow(target);
        repairCollisions();remember();
        return;
      }
    }
    if (el.dataset.anchor && el.dataset.anchor !== '#') {
      const target = document.getElementById(el.dataset.anchor.slice(1));
      if (target) { target.scrollIntoView({behavior: 'smooth'}); return; }
    }
    const label=(el.getAttribute('aria-label')||el.textContent.trim()||el.value||'').slice(0,200);
    const destination=(el.dataset.intent||'').slice(0,500);
    const nearby=el.closest('article,section,li,p')||el.parentElement;
    const link={label,destination,excerpt:(nearby?.textContent||'').trim().slice(0,1000)};
    const prompt = el.dataset.prompt || label || intent(el);
    if (!prompt) return;
    if (parent === window) { note('Open this page in Elsewhere to imagine the next destination.'); return; }
    send('navigate', {prompt, label,link,view:viewState()});
  });
  document.addEventListener('submit', event => {
    event.preventDefault();
    const form = event.target;
    const terms = [...form.querySelectorAll('input,textarea,select')].filter(el => !el.disabled && ['text','search','textarea','select-one','number','date'].includes(el.type) && el.value.trim()).map(el => ((el.name || el.getAttribute('aria-label') || el.placeholder || 'Input') + ': ' + el.value.trim()).slice(0,300));
    const action = (event.submitter && intent(event.submitter)) || form.dataset.prompt || form.getAttribute('aria-label') || 'Explore';
    if (parent === window) { note('Open this page in Elsewhere to continue.'); return; }
    if (terms.length || event.submitter) send('navigate', {prompt: [action,...terms].join(' — ').slice(0,600), label: action,link:{label:action,excerpt:form.textContent.trim().slice(0,1000)},view:viewState()});
    else note('This is a local simulation. Nothing was submitted.');
  });
  document.addEventListener('input', event => {
    remember();
    const query = event.target;
    if (!query.dataset.filter) return;
    const container = document.getElementById(query.dataset.filter.replace(/^#/, ''));
    if (container) [...container.children].forEach(el => el.hidden = !el.textContent.toLowerCase().includes(query.value.toLowerCase()));
  });
  function report() {
    const width = document.documentElement.clientWidth;
    const overflowing = [...document.body.querySelectorAll('*')].filter(el => !['STYLE','SCRIPT'].includes(el.tagName) && el.getBoundingClientRect().width && el.getBoundingClientRect().right > width + 8).slice(0,6).map(el => ({tag:el.tagName, text:el.textContent.trim().slice(0,70)}));
    send('layout', {width, overflow: document.documentElement.scrollWidth > width + 8, overflowing, height: document.documentElement.scrollHeight});
  }
  addEventListener('load', () => { repairCollisions();setTimeout(report, 120); send('ready'); });
  // A parent handshake avoids depending on a single load/resize message.
  addEventListener('message', event => {if(event.source===parent && event.data?.capability===capability && event.data.measure) report();});
  let timer;
  addEventListener('resize', () => {clearTimeout(timer);timer=setTimeout(()=>{repairCollisions();report();},200);});
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && ['l','t','w','d'].includes(event.key.toLowerCase())) {event.preventDefault();send('shortcut',{key:event.key.toLowerCase()});}
  });
})();
