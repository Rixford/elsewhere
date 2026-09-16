(() => {
  'use strict';
  const capability = __CAPABILITY__;
  const send = (kind, extra = {}) => parent.postMessage({elsewhere: true, capability, kind, ...extra}, '*');
  addEventListener('message',event=>{if(event.source===parent&&event.data?.capability===capability&&event.data.freeze){const style=document.createElement('style');style.textContent='*,*::before,*::after{animation-play-state:paused!important;transition:none!important}';document.head.append(style);}});
  const intent = el => el.dataset.prompt || el.dataset.intent || el.getAttribute('aria-label') || el.value || el.textContent.trim().slice(0, 200);
  const note = message => {
    let box = document.getElementById('elsewhere-local-note');
    if (!box) { box = document.createElement('div'); box.id = 'elsewhere-local-note'; document.body.appendChild(box); }
    box.textContent = message;
    box.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);padding:12px 20px;border-radius:12px;background:#20232e;color:white;font:14px system-ui;z-index:2147483647;box-shadow:0 4px 24px #0004;max-width:90vw';
    setTimeout(() => box.remove(), 4000);
  };
  document.addEventListener('click', event => {
    const el = event.target.closest('a,button,input[type="submit"],input[type="button"],input[type="reset"],[role="tab"],[data-target],[data-prompt]');
    if (!el || el.disabled) return;
    if (['BUTTON','INPUT'].includes(el.tagName) && el.form && ['submit','reset'].includes(el.type)) return;
    event.preventDefault();
    const targetId = el.dataset.target || el.getAttribute('aria-controls');
    if (targetId) {
      const target = document.getElementById(targetId.replace(/^#/, ''));
      if (target) {
        if (el.getAttribute('role') === 'tab') {
          document.querySelectorAll('[role="tab"]').forEach(tab => tab.setAttribute('aria-selected', String(tab === el)));
          document.querySelectorAll('[role="tabpanel"]').forEach(panel => panel.hidden = panel !== target);
        } else { target.hidden = !target.hidden; el.setAttribute('aria-expanded', String(!target.hidden)); }
        return;
      }
    }
    if (el.dataset.anchor && el.dataset.anchor !== '#') {
      const target = document.getElementById(el.dataset.anchor.slice(1));
      if (target) { target.scrollIntoView({behavior: 'smooth'}); return; }
    }
    const prompt = intent(el);
    if (!prompt) return;
    if (parent === window) { note('Open this page in Elsewhere to imagine the next destination.'); return; }
    send('navigate', {prompt, label: el.textContent.trim().slice(0,200)});
  });
  document.addEventListener('submit', event => {
    event.preventDefault();
    const form = event.target;
    const terms = [...form.querySelectorAll('input,textarea,select')].filter(el => !el.disabled && ['text','search','textarea','select-one','number','date'].includes(el.type) && el.value.trim()).map(el => ((el.name || el.getAttribute('aria-label') || el.placeholder || 'Input') + ': ' + el.value.trim()).slice(0,300));
    const action = (event.submitter && intent(event.submitter)) || form.dataset.prompt || form.getAttribute('aria-label') || 'Explore';
    if (parent === window) { note('Open this page in Elsewhere to continue.'); return; }
    if (terms.length || event.submitter) send('navigate', {prompt: [action,...terms].join(' — ').slice(0,600), label: action});
    else note('This is a local simulation. Nothing was submitted.');
  });
  document.addEventListener('input', event => {
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
  addEventListener('load', () => { setTimeout(report, 120); send('ready'); });
  // A parent handshake avoids depending on a single load/resize message.
  addEventListener('message', event => {if(event.source===parent && event.data?.capability===capability && event.data.measure) report();});
  let timer;
  addEventListener('resize', () => {clearTimeout(timer);timer=setTimeout(report,200);});
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && ['l','t','w'].includes(event.key.toLowerCase())) {event.preventDefault();send('shortcut',{key:event.key.toLowerCase()});}
  });
})();
