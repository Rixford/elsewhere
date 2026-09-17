// Exercise the real evaluation UI without a model or browser service.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{
  constructor(){this.children=[];this.style={};this.attributes={};this.value='';this.checked=false;this.hidden=false;this.contentWindow={postMessage(){}};}
  append(...children){this.children.push(...children);}replaceChildren(){this.children=[];}setAttribute(k,v){this.attributes[k]=v;}removeAttribute(k){delete this.attributes[k];}remove(){}focus(){}select(){}cloneNode(){return new Element();}replaceWith(){}getBoundingClientRect(){return{x:0,y:0,width:1000,height:700};}
  set innerHTML(_){throw new Error('Untrusted evaluation content must use textContent');}
}
const elements=new Map(),calls=[],responses=new Map();
const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
get('eval-repeats').value='2';get('eval-budget').value='5200';get('eval-seed').value='4';
responses.set('/api/evaluations',[]);
responses.set('/api/evaluations/start',{id:'eval-one'});
responses.set('/api/jobs/eval-one',{id:'eval-one',kind:'evaluation',state:'reviewing',stage:'Measuring',revision:1,page:{html:'<html>fixture</html>',capability:'cap'}});
const context=vm.createContext({console,crypto:{randomUUID:()=> 'tab'},location:{hash:'#test'},history:{replaceState(){}},
  document:{getElementById:get,createElement:()=>new Element(),addEventListener(){}},setTimeout(){},clearTimeout(){},setInterval(){},addEventListener(){},
  fetch:async(url,options)=>{calls.push({url,body:options.body?JSON.parse(options.body):null});return {ok:true,json:async()=>responses.has(url)?responses.get(url):{engine:'ready',settings:{},history:[],router:{provider:'local',model:'Qwen3.5-4B'}}};}});
context.window=context;
vm.runInContext(fs.readFileSync(__dirname+'/web/app.js','utf8'),context);
vm.runInContext(fs.readFileSync(__dirname+'/web/evaluate.js','utf8'),context);
const run=code=>vm.runInContext(code,context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function main(){
  await tick();assert.equal(get('evaluation').hidden,false);
  run("evaluationState.cards[0].prompt.value='A map of regret';evaluationState.cards[0].criteria.value='Three contrasting routes';evaluationState.cards[0].kind.value='translation'");
  await run('runEvaluation()');await tick();
  const request=calls.find(c=>c.url==='/api/evaluations/start').body;
  assert.equal(request.cases[0].kind,'translation');assert.equal(request.cases[0].criteria,'Three contrasting routes');assert.equal(request.repeats,2);
  assert.equal(run('state.job'),'eval-one');assert.equal(run('state.jobTab'),null);
  assert.equal(get('validation-frame').style.width,'1280px');assert.equal(get('validation-frame').style.height,'720px');
  run('evaluationMode(false)');assert.equal(get('evaluation').hidden,true);assert.equal(run('state.job'),'eval-one');
  console.log('PASS: Evaluate defaults on, preserves typed transfer criteria, fixes measurement dimensions and permits Explore during a run');
  const record={id:'eval-one',state:'done',protocol:{version:'v1'},fingerprint:'same',spec:request,model:'fixture',attempts:[{id:'1.1',case:0,repeat:1,state:'error',raw:'<script>not executed</script>',error:'fixture failure'}],ratings:{},summary:{scheduled:2,measured:0,checks_passed:0,failed:1,cancelled:0,not_run:1,generation_seconds:0,usage:null,estimated_cost:null}};
  responses.set('/api/jobs/eval-one',{state:'done',stage:'Saved',revision:1});responses.set('/api/evaluations/eval-one',record);
  await run("pollEvaluation('eval-one')");await tick();
  assert.equal(run('state.job'),null);assert.equal(run('state.tabs[0].pages.length'),0);assert.equal(get('evaluation').hidden,true);
  assert.equal(get('eval-report').hidden,false);assert.match(get('eval-progress').textContent,/1 failed, 1 not run/);
  console.log('PASS: failed and skipped outcomes remain visible in reports without stealing Explore focus or entering browser history');
  const before=calls.filter(c=>c.url==='/api/evaluations/start').length;
  run("evaluationState.showModels=true;loadEvaluation('eval-one')");await tick();
  assert.equal(calls.filter(c=>c.url==='/api/evaluations/start').length,before);
  assert.equal(run('evaluationState.record.attempts[0].raw'),'<script>not executed</script>');
  console.log('PASS: inspecting raw output and revealing models cannot execute output or start another generation');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
