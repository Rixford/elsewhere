'use strict';
const evaluationState={job:null,record:null,runs:[],cards:[],starting:false,showModels:false};
function evaluationMode(enabled){
  $('evaluation').hidden=!enabled;
  $('evaluate-button').setAttribute('aria-pressed',String(enabled));
  $('explore-button').setAttribute('aria-pressed',String(!enabled));
  if(enabled){closePanel();updateEvaluationPlan();}else renderCurrent();
  if(enabled)$('page-status').textContent='Closed-book evaluation · original responses preserved';
  drawTabs();
}
function evalNode(tag,text,parent,cls){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;if(parent)parent.append(el);return el;}
function evalButton(parent,label,callback){const button=evalNode('button',label,parent,'secondary');button.type='button';button.onclick=async()=>{try{await callback();}catch(e){toast(e.message);}};return button;}
function addEvaluationCase(value={kind:'concept',prompt:'',criteria:''}){
  if(evaluationState.cards.length>=6){toast('Use up to six tasks per run.');return;}
  const card=evalNode('div',undefined,$('eval-cases'),'eval-task');
  const label=evalNode('label','Task type',card);const kind=evalNode('select',undefined,label);
  for(const [id,name] of [['website','Familiar website'],['concept','Thought or concept'],['search','Search or question'],['translation','Transfer / reinterpretation']]){const option=evalNode('option',name,kind);option.value=id;}
  kind.value=value.kind;
  const promptLabel=evalNode('label','URL, idea, search, or translation',card);const prompt=evalNode('textarea',undefined,promptLabel);prompt.maxLength=1200;prompt.rows=3;prompt.placeholder='A museum of things we almost invented…';prompt.value=value.prompt;
  const criteriaLabel=evalNode('label','Your criteria (sent to the model)',card);const criteria=evalNode('textarea',undefined,criteriaLabel);criteria.maxLength=1600;criteria.rows=2;criteria.placeholder='E.g. show three contrasting viewpoints, use a timeline, avoid card grids.';criteria.value=value.criteria;
  const item={card,kind,prompt,criteria};evaluationState.cards.push(item);
  evalButton(card,'Remove task',()=>{if(evaluationState.cards.length===1)return;card.remove();evaluationState.cards=evaluationState.cards.filter(c=>c!==item);updateEvaluationPlan();});
  updateEvaluationPlan();
}
function evaluationSpec(){
  const input=$('eval-input-price').value,output=$('eval-output-price').value;
  if((input==='')!==(output===''))throw new Error('Enter both token prices or leave both blank.');
  return {cases:evaluationState.cards.map(c=>({kind:c.kind.value,prompt:c.prompt.value,criteria:c.criteria.value})),repeats:Number($('eval-repeats').value),budget:Number($('eval-budget').value),seed:Number($('eval-seed').value),review:$('eval-review').checked,prices:input===''?null:{input:Number(input),output:Number(output)},cloud_confirmed:$('eval-cloud').checked};
}
function updateEvaluationPlan(){
  const route=JSON.stringify(state.status?.router&&[state.status.router.provider,state.status.router.model]);
  if(evaluationState.route!==route){evaluationState.route=route;$('eval-cloud').checked=false;}
  const cloud=!!state.status?.router?.provider&&state.status.router.provider!=='local';
  $('eval-cloud-label').hidden=!cloud;
  const count=evaluationState.cards.length*(Number($('eval-repeats').value)||1);
  $('eval-plan').textContent=`${count} generation calls${$('eval-review').checked?` + up to ${count} advisory reviews`:''} · ${cloud?state.status.model:'Local Qwen3.5 4B'} · one task at a time. ${cloud?'Cloud seeds are unsupported.':'Each repetition increments the seed.'}`;
  $('eval-run').disabled=!!state.job||state.starting||evaluationState.starting||state.status?.engine!=='ready';
  const active=state.status?.active;
  if(active&&!state.job&&!state.starting&&evaluationState.probed!==active){
    evaluationState.probed=active;
    api('jobs/'+active).then(job=>{if(!state.job&&!state.starting&&job.kind==='evaluation'&&!['done','error','cancelled'].includes(job.state)){evaluationState.job=active;state.job=active;state.jobTab=null;$('eval-stop').hidden=false;pollEvaluation(active);updateEvaluationPlan();}}).catch(()=>{evaluationState.probed=null;});
  }
}
async function runEvaluation(){
  if(state.job||state.starting||evaluationState.starting){toast('Finish or stop the active task first.');return;}
  evaluationState.starting=true;state.starting=true;updateEvaluationPlan();
  try{
    const result=await api('evaluations/start',evaluationSpec());
    evaluationState.job=result.id;state.job=result.id;state.jobTab=null;state.validation=null;
    $('eval-stop').hidden=false;$('eval-cloud').checked=false;
    pollEvaluation(result.id);
  }catch(e){toast(e.message);}finally{evaluationState.starting=false;state.starting=false;updateEvaluationPlan();if(!state.job)drainQueue();}
}
async function pollEvaluation(id){
  if(evaluationState.job!==id)return;
  try{
    const job=await api('jobs/'+id);
    $('eval-progress').textContent=job.stage+(job.chars?` · ${job.chars.toLocaleString()} characters`:'');
    if(job.page&&(state.validation?.job!==id||state.validation?.revision!==job.revision)){
      state.validation={page:job.page,job:id,revision:job.revision};
      $('validation-frame').style.width='1280px';$('validation-frame').style.height='720px';$('validation-frame').srcdoc=job.page.html;
    }
    if(state.validation?.job===id&&!state.validation.reported)$('validation-frame').contentWindow.postMessage({measure:true,capability:state.validation.page.capability},'*');
    if(['done','error','cancelled'].includes(job.state)){
      // A cancellation response can arrive before the worker's final record write.
      const record=await api('evaluations/'+id);
      if(record.state==='running'){setTimeout(()=>pollEvaluation(id),500);return;}
      evaluationState.job=null;if(state.job===id){state.job=null;state.jobTab=null;state.validation=null;}
      $('eval-stop').hidden=true;await loadEvaluation(id);await listEvaluations();updateEvaluationPlan();drawTabs();drainQueue();return;
    }
  }catch(e){$('eval-progress').textContent=e.message+' · reconnecting; no model request will be retried.';}
  setTimeout(()=>pollEvaluation(id),600);
}
async function listEvaluations(){
  evaluationState.runs=await api('evaluations');const area=$('eval-runs');area.replaceChildren();evalNode('h3','Saved evaluations',area);
  if(!evaluationState.runs.length)evalNode('p','Your first run will appear here. Records stay local until you export them.',area,'eval-muted');
  evaluationState.runs.forEach((r,i)=>evalButton(area,`Run ${evaluationState.runs.length-i} · ${new Date(r.created*1000).toLocaleString()} · ${r.summary.measured}/${r.summary.scheduled} measured · ${r.state}`,()=>loadEvaluation(r.id)));
}
function summaryTable(parent,records){
  const wrap=evalNode('div',undefined,parent,'eval-table-scroll');const table=evalNode('table',undefined,wrap,'eval-table');
  const head=evalNode('tr',undefined,evalNode('thead',undefined,table));for(const h of ['Run','Measured / planned','Code + width checks','Errors / stopped / not run','Generation time','Reported tokens¹','Est. cost¹'])evalNode('th',h,head);
  const body=evalNode('tbody',undefined,table);
  records.forEach((r,i)=>{const s=r.summary,row=evalNode('tr',undefined,body);for(const val of [evaluationState.showModels?r.model:`${String.fromCharCode(65+i)} · ${r.id.slice(0,6)}`,`${s.measured} / ${s.scheduled}`,`${s.checks_passed} / ${s.scheduled}`,`${s.failed} / ${s.cancelled} / ${s.not_run}`,`${s.generation_seconds}s`,s.usage?`${s.usage.input_tokens} in / ${s.usage.output_tokens} out`:'Unavailable',s.estimated_cost===null?'Unknown':`$${s.estimated_cost.toFixed(4)}`])evalNode('td',val,row);});
  evalNode('p','¹ Reported usage includes advisory reviews when available. Costs use your entered rates and exclude unreported requests/cache discounts. Code checks do not grade meaning, visual quality, factual accuracy or interaction behavior.',parent,'eval-muted');
  const ratingsTable=evalNode('table',undefined,evalNode('div',undefined,parent,'eval-table-scroll'),'eval-table');
  const ratingHead=evalNode('tr',undefined,evalNode('thead',undefined,ratingsTable));for(const title of ['Human ratings','Intent','Criteria','Identity / transfer','Coherence','Visual clarity'])evalNode('th',title,ratingHead);
  const ratingBody=evalNode('tbody',undefined,ratingsTable);
  records.forEach((r,i)=>{const row=evalNode('tr',undefined,ratingBody);evalNode('td',evaluationState.showModels?r.model:String.fromCharCode(65+i),row);for(const key of ['intent','criteria','identity','coherence','visual']){const values=Object.values(r.ratings||{}).map(v=>v.scores?.[key]).filter(v=>Number.isInteger(v));evalNode('td',values.length?`${(values.reduce((a,b)=>a+b,0)/values.length).toFixed(1)} / 5 (n=${values.length})`:'Unscored',row);}});
}
async function loadEvaluation(id){
  const record=await api('evaluations/'+id);evaluationState.record=record;
  const area=$('eval-report');area.hidden=false;area.replaceChildren();
  evalNode('h2','Evaluation report',area);evalNode('p',`${record.state} · ${record.protocol.version} · protocol/task fingerprint ${record.fingerprint.slice(0,12)}`,area,'eval-muted');
  const actions=evalNode('div',undefined,area,'eval-actions');
  evalButton(actions,evaluationState.showModels?'Hide model labels':'Reveal model labels',()=>{evaluationState.showModels=!evaluationState.showModels;loadEvaluation(id);});
  evalButton(actions,'Reuse these tasks',()=>{
    $('eval-cases').replaceChildren();evaluationState.cards=[];record.spec.cases.forEach(addEvaluationCase);
    for(const name of ['repeats','budget','seed'])$('eval-'+name).value=record.spec[name];$('eval-review').checked=record.spec.review;
    $('eval-input-price').value='';$('eval-output-price').value='';$('eval-cloud').checked=false;updateEvaluationPlan();$('evaluation').scrollTop=0;
  });
  evalButton(actions,'Export summary',async()=>toast('Saved: '+(await api('evaluations/export',{id})).path));
  const confirmation=evalNode('label',undefined,area,'eval-check');const exportCheck=evalNode('input',undefined,confirmation);exportCheck.type='checkbox';evalNode('span','Full exports contain your prompts, generated source, and rating notes.',confirmation);
  evalButton(actions,'Export full record',async()=>{if(!exportCheck.checked)throw new Error('Check the full-export disclosure first.');toast('Saved: '+(await api('evaluations/export',{id,include_content:true,confirmed:true})).path);});
  const deleteButton=evalButton(actions,'Delete run…',()=>{deleteButton.hidden=true;const confirm=evalNode('div',undefined,area,'eval-actions');evalNode('span','Delete the local run and ratings? Existing exports stay saved.',confirm);evalButton(confirm,'Keep run',()=>{confirm.remove();deleteButton.hidden=false;});evalButton(confirm,'Delete permanently',async()=>{await api('evaluations/delete',{id,confirmed:true});area.hidden=true;evaluationState.record=null;await listEvaluations();});});
  const comparison=evalNode('div',undefined,area);summaryTable(comparison,[record]);
  const choose=evalNode('select',undefined,area);choose.setAttribute('aria-label','Compare with another run');evalNode('option','Compare with another run…',choose).value='';
  evaluationState.runs.filter(r=>r.id!==id).forEach((r,i)=>{const o=evalNode('option',`Run ${r.id.slice(0,6)} · ${r.summary.measured} measured`,choose);o.value=r.id;});
  choose.onchange=async()=>{try{comparison.replaceChildren();if(!choose.value){summaryTable(comparison,[record]);return;}const other=await api('evaluations/'+choose.value);if(other.fingerprint!==record.fingerprint)evalNode('p','Different tasks, budget, seeds, renderer, or environment. This is not a controlled comparison.',comparison,'eval-warning');summaryTable(comparison,[record,other]);}catch(e){toast(e.message);}};
  evalNode('p','Model labels are hidden in this report until revealed. This does not blind someone who selected the model or inspected its source metadata. Human ratings: 1 = misses the goal, 3 = mixed, 5 = strongly meets it; leave irrelevant dimensions unscored.',area,'eval-muted');
  const attemptSelect=evalNode('select',undefined,area);attemptSelect.setAttribute('aria-label','Select attempt');
  record.attempts.forEach(a=>{evalNode('option',`Task ${a.case+1} · attempt ${a.repeat} · ${a.state}`,attemptSelect).value=a.id;});
  const detail=evalNode('div',undefined,area);attemptSelect.onchange=()=>showAttempt(record,attemptSelect.value,detail);if(record.attempts.length){attemptSelect.value=record.attempts[0].id;showAttempt(record,attemptSelect.value,detail);}
  $('eval-progress').textContent=`Run ${record.state}. All planned attempts are accounted for; ${record.summary.measured} measured, ${record.summary.failed} failed, ${record.summary.not_run} not run.`;
  if(!$('evaluation').hidden)area.scrollIntoView?.({block:'start',behavior:'smooth'});
}
function showAttempt(record,id,parent){
  parent.replaceChildren();const attempt=record.attempts.find(a=>a.id===id),task=record.spec.cases[attempt.case];
  evalNode('h3',task.prompt,parent);evalNode('p',task.criteria||'No additional criteria.',parent,'eval-criteria');
  if(attempt.error)evalNode('p',attempt.error,parent,'eval-warning');
  if(attempt.checks)evalNode('p',`Parser errors: ${attempt.checks.parse_errors}. Removed element types: ${attempt.checks.removed.join(', ')||'none'}. Raw URL references: ${attempt.checks.raw_external_references} (may be links, not asset fetches). ${attempt.checks.issues.join(' ')}`,parent,'eval-muted');
  if(attempt.layout)evalNode('p',attempt.layout.samples.map(s=>`${s.width}px: ${s.overflow?'horizontal overflow':'no horizontal overflow detected'}`).join(' · '),parent,'eval-muted');
  if(attempt.rendered_html){
    const previewControls=evalNode('div',undefined,parent,'eval-actions');const wrap=evalNode('div',undefined,parent,'eval-preview');const frame=evalNode('iframe',undefined,wrap);frame.setAttribute('sandbox','allow-scripts allow-forms');frame.setAttribute('referrerpolicy','no-referrer');frame.title='Safety-sanitized first attempt';frame.style.width='1280px';frame.style.height='720px';frame.srcdoc=attempt.rendered_html;
    for(const width of [1280,640])evalButton(previewControls,width+'px',()=>{frame.style.width=width+'px';});
  }
  if(attempt.review)evalNode('p','Advisory model review (not a score): '+attempt.review.summary+' '+(attempt.review.issues||[]).map(i=>i.detail).join(' '),parent,'review-report');
  const ratings=record.ratings?.[id]||{};const grid=evalNode('div',undefined,parent,'eval-options');const fields={};
  for(const [dimension,title] of [['intent','Intent'],['criteria','Criteria'],['identity','Identity / transfer'],['coherence','Coherence'],['visual','Visual clarity']]){
    const label=evalNode('label',title,grid),select=evalNode('select',undefined,label);evalNode('option','Unscored',select).value='';for(let i=1;i<=5;i++)evalNode('option',String(i),select).value=String(i);select.value=ratings.scores?.[dimension]??'';fields[dimension]=select;
  }
  const noteLabel=evalNode('label','Human assessment notes',parent),note=evalNode('textarea',undefined,noteLabel);note.maxLength=2000;note.rows=2;note.value=ratings.note||'';
  evalButton(parent,'Save human assessment',async()=>{const scores=Object.fromEntries(Object.entries(fields).map(([k,v])=>[k,v.value===''?null:Number(v.value)]));await api('evaluations/rate',{id:record.id,attempt:id,scores,note:note.value});record.ratings[id]={scores,note:note.value};await loadEvaluation(record.id);toast('Assessment saved separately from the original response.');});
  const source=evalNode('details',undefined,parent);evalNode('summary','Original response and reproducibility record',source);
  evalNode('p','Original source is displayed as text, never executed. Safety sanitation and browser HTML parsing can change the rendered result.',source,'eval-muted');
  evalNode('pre',attempt.raw||'No output was returned.',source,'source');
  evalNode('pre',JSON.stringify({sha256:attempt.raw_sha256,stats:attempt.stats,seed:attempt.seed,protocol:record.protocol},null,2),source,'source');
}
$('evaluate-button').onclick=()=>evaluationMode(true);$('explore-button').onclick=()=>evaluationMode(false);
$('eval-run').onclick=runEvaluation;$('eval-model').onclick=showSettings;
$('eval-stop').onclick=async()=>{try{await api('cancel',{id:evaluationState.job});}catch(e){toast(e.message);}};
$('eval-add').onclick=()=>addEvaluationCase();$('eval-saved').onclick=()=>listEvaluations().catch(e=>toast(e.message));
for(const id of ['eval-repeats','eval-review','eval-budget'])$(id).onchange=updateEvaluationPlan;
$('eval-examples').onclick=()=>{
  if(evaluationState.cards.some(c=>c.prompt.value.trim())){toast('Remove or clear your current task text before loading examples.');return;}
  $('eval-cases').replaceChildren();evaluationState.cards=[];
  [{kind:'website',prompt:'wikipedia.org',criteria:'Express its recognizable information hierarchy using system fonts and inline graphics.'},{kind:'concept',prompt:'The feeling of remembering a place that never existed',criteria:'Use spatial composition to express the feeling. Avoid a generic product landing page.'},{kind:'search',prompt:'How could cities be quieter without becoming less lively?',criteria:'Organize three competing approaches and their tradeoffs. Mark any invented examples as hypothetical.'},{kind:'translation',prompt:'Translate the structure of an encyclopedia into a field guide to emotions',criteria:'Preserve recognizable reference-navigation patterns while adapting categories and visuals to emotional experiences.'}].forEach(addEvaluationCase);
};
$('address-form').onsubmit=e=>{e.preventDefault();if($('evaluation').hidden)navigate($('address').value);else{evaluationState.cards[0].prompt.value=$('address').value;evaluationState.cards[0].prompt.focus();toast('Task updated. Set criteria and press Run evaluation.');}};
addEvaluationCase();evaluationMode(true);listEvaluations().catch(e=>toast(e.message));
