// Execute the actual shell script with a minimal DOM to reproduce asynchronous races.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(){this.style={};this.contentWindow={postMessage(){}};this.children=[];this.hidden=false;this.value='';this.attributes={};}
  replaceChildren(){this.children=[];} append(...nodes){this.children.push(...nodes);} setAttribute(name,value){this.attributes[name]=value;} removeAttribute(name){delete this.attributes[name];} focus(){} select(){}
  getBoundingClientRect(){return {x:0,y:98,width:1264,height:680};}
  cloneNode(){return new Element();} replaceWith(){}
}
const elements=new Map();
const listeners=new Map();
const calls=[];
let resolveCancel;
const responses=new Map();
let nextJob=0;
const context=vm.createContext({
  console,crypto:{randomUUID:()=> 'tab-one'},location:{hash:'#token'},history:{replaceState(){}},
  document:{getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},createElement(){return new Element();},addEventListener(){}},
  setInterval(){},setTimeout(fn,delay){if(delay===180)queueMicrotask(fn);},clearTimeout(){},
  addEventListener(name,callback){listeners.set(name,callback);},
  fetch:async(url,options)=>{
    calls.push({url,body:options.body?JSON.parse(options.body):null});
    if(url==='/api/cancel')return new Promise(resolve=>{resolveCancel=()=>resolve({ok:true,json:async()=>({stopped:true})});});
    if(responses.has(url))return {ok:true,json:async()=>responses.get(url)};
    if(url==='/api/generate')return {ok:true,json:async()=>({id:'generated-'+(++nextJob)})};
    return {ok:true,json:async()=>({engine:'ready',settings:{},history:[]})};
  }
});
context.window=context;
vm.runInContext(fs.readFileSync(__dirname+'/web/app.js','utf8'),context);
async function main(){
  vm.runInContext("state.job='j';state.validation={job:'j',revision:1,page:{capability:'cap'}}",context);
  const report=width=>listeners.get('message')({source:context.document.getElementById('validation-frame').contentWindow,data:{elsewhere:true,capability:'cap',kind:'layout',width,overflow:false,overflowing:[]}});
  report(1249);report(1249);
  assert.equal(calls.filter(c=>c.url==='/api/rendered').length,0,'duplicate wide report must not finish validation');
  report(625);report(625);
  const reports=calls.filter(c=>c.url==='/api/rendered');
  assert.equal(reports.length,1,'exactly one complete report');
  assert.deepEqual(JSON.parse(JSON.stringify(reports[0].body.layout.samples)),[{width:1249,overflow:false},{width:625,overflow:false}]);
  console.log('PASS: duplicate layout events cannot skip the narrow-width check');

  vm.runInContext("state.job='old-job';state.jobTab='old-tab'",context);
  const pending=vm.runInContext('stop()',context);
  assert.ok(resolveCancel);
  // Simulate an independently accepted replacement while the old cancellation response arrives.
  vm.runInContext("state.job='new-job';state.jobTab='new-tab'",context);
  resolveCancel();await pending;
  assert.equal(vm.runInContext('state.job',context),'new-job');
  assert.equal(vm.runInContext('state.jobTab',context),'new-tab');
  console.log('PASS: late cancellation cannot clear a newer job');
  vm.runInContext("state.job='review';state.current='tab-one';state.displayed={job:'review',page:{capability:'page-cap'}}",context);
  const click=prompt=>listeners.get('message')({source:context.document.getElementById('page').contentWindow,data:{elsewhere:true,capability:'page-cap',kind:'navigate',prompt}});
  click('Ascend');click('Explore');
  assert.equal(vm.runInContext('state.queued.prompt',context),'Explore');
  assert.equal(calls.filter(c=>c.url==='/api/generate').length,0);
  vm.runInContext("state.job=null;followQueued('finished-parent')",context);
  await new Promise(resolve=>setImmediate(resolve));
  const generation=calls.find(c=>c.url==='/api/generate');
  assert.equal(generation.body.prompt,'Explore');
  assert.equal(generation.body.parent,'finished-parent');
  console.log('PASS: review clicks queue the latest intent with the completed parent');
  vm.runInContext("state.job=null;state.starting=false;state.tabs=[{id:'tab-one',pages:[{id:'a',title:'A',html:'a',capability:'a'},{id:'b',title:'B',html:'b',capability:'b'}],index:1}];state.current='tab-one';state.displayed=null",context);
  const before=calls.filter(c=>c.url==='/api/generate').length;
  await context.document.getElementById('back').onclick();
  assert.equal(vm.runInContext('current().index',context),0);
  await context.document.getElementById('forward').onclick();
  assert.equal(vm.runInContext('current().index',context),1);
  assert.equal(calls.filter(c=>c.url==='/api/generate').length,before);
  console.log('PASS: Back and Forward restore cache without model calls');

  vm.runInContext("state.tabs.push({id:'tab-two',pages:[],index:-1});state.job='building';state.jobTab='tab-one';state.lastPrompt='First page';state.progress={stage:'Reviewing',revision:1,page:{id:'draft',html:'draft',capability:'draft'}};state.displayed=null",context);
  const cancels=calls.filter(c=>c.url==='/api/cancel').length;
  await vm.runInContext("switchTab('tab-two')",context);
  assert.equal(vm.runInContext('state.current',context),'tab-two');
  assert.equal(vm.runInContext('state.job',context),'building');
  await vm.runInContext("switchTab('tab-one')",context);
  assert.equal(vm.runInContext('state.displayed.page.id',context),'draft');
  await vm.runInContext("switchTab('tab-two')",context);
  responses.set('/api/pages/bookmark',{id:'bookmark',title:'Bookmarked',html:'saved',capability:'bookmark'});
  await vm.runInContext("openSavedPage('bookmark')",context);
  assert.equal(vm.runInContext('saved().id',context),'bookmark');
  assert.equal(vm.runInContext('state.job',context),'building');
  assert.equal(calls.filter(c=>c.url==='/api/cancel').length,cancels);
  console.log('PASS: switching tabs and opening bookmarks never cancel another tab');

  const generations=calls.filter(c=>c.url==='/api/generate').length;
  await vm.runInContext("navigate('Old topic','bookmark',null,{label:'Old topic'})",context);
  await vm.runInContext("navigate('Metaphysics','bookmark',null,{label:'Metaphysics',destination:'/'})",context);
  assert.equal(vm.runInContext('state.pending.length',context),1);
  assert.equal(vm.runInContext('state.pending[0].prompt',context),'Metaphysics');
  assert.equal(calls.filter(c=>c.url==='/api/generate').length,generations);
  responses.set('/api/jobs/building',{state:'done',revision:1,stage:'Done',page:{id:'draft',html:'draft',capability:'draft'},result:{id:'finished',title:'Finished',html:'finished',capability:'finished'}});
  await vm.runInContext("pollJob('building')",context);
  await new Promise(resolve=>setImmediate(resolve));
  const next=calls.filter(c=>c.url==='/api/generate').at(-1);
  assert.equal(next.body.prompt,'Metaphysics');
  assert.equal(next.body.parent,'bookmark');
  assert.equal(next.body.link.destination,'/');
  assert.equal(vm.runInContext('state.current',context),'tab-two');
  assert.equal(vm.runInContext('state.tabs[0].pages.at(-1).id',context),'finished');
  assert.equal(vm.runInContext('state.jobTab',context),'tab-two');
  console.log('PASS: requests queue per tab and start with their original parent and link');

  await vm.runInContext("switchTab('tab-one')",context);
  const active=vm.runInContext('state.job',context);
  responses.set('/api/jobs/'+active,{state:'done',stage:'Done',revision:1,result:{id:'second',title:'Second',html:'second',capability:'second'}});
  await vm.runInContext('pollJob(state.job)',context);
  assert.equal(vm.runInContext('state.current',context),'tab-one');
  assert.equal(vm.runInContext('state.displayed.page.id',context),'finished');
  assert.equal(vm.runInContext('state.tabs[1].pages.at(-1).id',context),'second');
  console.log('PASS: background completion keeps the selected tab and visible page');

  vm.runInContext("state.job='review-again';state.jobTab='tab-one';state.queued={prompt:'Deep dive',tab:'tab-one',fromJob:true,link:{label:'Deep dive'}}",context);
  await vm.runInContext("switchTab('tab-two')",context);
  responses.set('/api/jobs/review-again',{state:'done',stage:'Done',revision:1,result:{id:'reviewed',title:'Reviewed',html:'reviewed',capability:'reviewed'}});
  await vm.runInContext("pollJob('review-again')",context);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(vm.runInContext('state.current',context),'tab-two');
  assert.equal(vm.runInContext('state.jobTab',context),'tab-one');
  assert.equal(calls.filter(c=>c.url==='/api/generate').at(-1).body.parent,'reviewed');
  console.log('PASS: a review-time link follows its completed parent after switching away');

  vm.runInContext("state.status={settings:{dark_settings:true},router:{provider:'local',presets:{openai:['gpt-6-astra'],anthropic:['claude-opus-5']},keys:{}}};state.panel=null;showSettings()",context);
  assert.equal(elements.get('panel').attributes['data-dark'],'true');
  const descendants=node=>[node,...node.children.flatMap(descendants)];
  const inputs=descendants(elements.get('panel-content'));
  const password=inputs.find(node=>node.attributes['aria-label']==='API key');
  assert.equal(password.type,'password');assert.equal(password.autocomplete,'off');assert.equal(password.value,'');
  const provider=inputs.find(node=>node.attributes['aria-label']==='Model provider');
  provider.value='anthropic';provider.onchange();
  assert.ok(inputs.some(node=>node.textContent?.includes('API charges')));
  password.value='transient-test-key';
  vm.runInContext("panel('Recent pages','history')",context);
  assert.equal(elements.get('panel').attributes['data-dark'],'false');
  assert.ok(!descendants(elements.get('panel-content')).includes(password));
  console.log('PASS: dark mode is Settings-only and key entry is masked, transient and disclosed');

  vm.runInContext("state.job=null;state.starting=false;state.stopping=null;state.pending=[];state.tabs=[{id:'tab-one',pages:[{id:'private',title:'Private',html:'private'}],index:0},{id:'tab-two',pages:[{id:'private'},{id:'kept',title:'Kept',html:'kept'}],index:1}];state.current='tab-one';confirmClearHistory()",context);
  assert.equal(calls.filter(c=>c.url==='/api/history/clear').length,0,'opening confirmation must not clear data');
  responses.set('/api/history/clear',{cleared:true,bookmarks:['kept']});
  const deletion=descendants(elements.get('panel-content')).find(node=>node.textContent==='Delete history');
  await deletion.onclick();
  assert.equal(calls.filter(c=>c.url==='/api/history/clear').length,1);
  assert.equal(vm.runInContext('state.tabs[0].pages.length',context),0);
  assert.equal(vm.runInContext('state.tabs[1].pages.length',context),1);
  assert.equal(vm.runInContext('state.tabs[1].pages[0].id',context),'kept');
  assert.equal(vm.runInContext('state.clearingHistory',context),false);
  console.log('PASS: clearing history requires confirmation and resets tab history while retaining bookmarks');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
