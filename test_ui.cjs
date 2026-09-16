// Execute the actual shell script with a minimal DOM to reproduce asynchronous races.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(){this.style={};this.contentWindow={};this.children=[];this.hidden=false;this.value='';}
  replaceChildren(){this.children=[];} append(...nodes){this.children.push(...nodes);} setAttribute(){} removeAttribute(){} focus(){} select(){}
  getBoundingClientRect(){return {x:0,y:98,width:1264,height:680};}
}
const elements=new Map();
const listeners=new Map();
const calls=[];
let resolveCancel;
const context=vm.createContext({
  console,crypto:{randomUUID:()=> 'tab-one'},location:{hash:'#token'},history:{replaceState(){}},
  document:{getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},createElement(){return new Element();},addEventListener(){}},
  setInterval(){},setTimeout(){},clearTimeout(){},
  addEventListener(name,callback){listeners.set(name,callback);},
  fetch:async(url,options)=>{
    calls.push({url,body:options.body?JSON.parse(options.body):null});
    if(url==='/api/cancel')return new Promise(resolve=>{resolveCancel=()=>resolve({ok:true,json:async()=>({stopped:true})});});
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
  await Promise.resolve();await Promise.resolve();
  const generation=calls.find(c=>c.url==='/api/generate');
  assert.equal(generation.body.prompt,'Explore');
  assert.equal(generation.body.parent,'finished-parent');
  console.log('PASS: review clicks queue the latest intent with the completed parent');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
