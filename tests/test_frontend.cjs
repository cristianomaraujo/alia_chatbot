const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
function setup(fetch){
 const nodes={};const $=id=>nodes[id]??=( {hidden:true,textContent:'',disabled:false,value:'Não há nenhuma fonte de trauma',setAttribute(){},close(){}} );
 const ctx={$,current:{id:'case'},csrf:'token',busy:false,t:(_key,f)=>f,fetch,AbortController,setTimeout,clearTimeout,document:{querySelectorAll:()=>[$('send')]} };
 vm.createContext(ctx);
 const lines=fs.readFileSync('app/static/app.js','utf8').split('\n');
 vm.runInContext(lines.filter(x=>/^(function (setBusy|status)|async function (api|work))\(/.test(x)).join('\n'),ctx);
 return {ctx,nodes,$};
}
test('a failed send shows its error beside the composer and preserves the answer',async()=>{
 const {ctx,$}=setup(async()=>({ok:false,status:502,json:async()=>({detail:'Não foi possível registrar a resposta.'})}));
 await ctx.work(()=>ctx.api('/api/cases/case/chat','POST',{message:$('chatInput').value}));
 assert.equal($('chatError').hidden,false);assert.match($('chatError').textContent,/registrar/);
 assert.equal($('chatInput').value,'Não há nenhuma fonte de trauma');assert.equal($('send').disabled,false);
});
test('repeated clicks during an outstanding request send only once',async()=>{
 let release,calls=0;const {ctx,$}=setup(()=>{calls++;return new Promise(r=>release=()=>r({ok:true,json:async()=>({})}));});
 const first=ctx.work(()=>ctx.api('/api/cases/case/chat','POST',{}));
 await ctx.work(()=>ctx.api('/api/cases/case/chat','POST',{}));
 assert.equal(calls,1);assert.equal($('send').disabled,true);release();await first;assert.equal($('send').disabled,false);
});
test('a network failure offers record reconciliation before retry',async()=>{
 const {ctx,$}=setup(async()=>{throw Error('network');});
 await ctx.work(()=>ctx.api('/api/cases/case/chat','POST',{}));
 assert.equal($('reloadCase').hidden,false);assert.match($('chatError').textContent,/Atualize a ficha/);
 assert.equal($('send').disabled,false);
});
test('professional search uses only Estomatologia and the supplied location',()=>{
 const ctx={};vm.createContext(ctx);
 const line=fs.readFileSync('app/static/app.js','utf8').split('\n').find(x=>x.startsWith('function professionalSearchQuery('));
 vm.runInContext(line,ctx);
 assert.equal(ctx.professionalSearchQuery(' Curitiba ',' Brasil '),'Estomatologia Curitiba Brasil');
 assert.doesNotMatch(ctx.professionalSearchQuery('Lisboa','Portugal'),/medicina|medicine|oncology/i);
});

test('source pages render from new arrays and earlier saved string values',()=>{
 const ctx={};vm.createContext(ctx);
 const line=fs.readFileSync('app/static/app.js','utf8').split('\n').find(x=>x.startsWith('function sourcePageText('));
 vm.runInContext(line,ctx);
 assert.equal(ctx.sourcePageText('4–9, 15–21'),'4–9, 15–21');
 assert.equal(ctx.sourcePageText(['3','6']),'3, 6');
 assert.equal(ctx.sourcePageText(undefined),'');
});

function documentSetup(){
 const nodes={};const $=id=>nodes[id]??={value:''};
 const ctx={$,current:{id:'12345678-case',active_fields:['complaint'],facts:{complaint:'Dor'},fact_meta:{complaint:{state:'reported'}},assessment:{text:'REFLEXAO_PRIVADA',review_points:[{text:'PROCEDIMENTO_INTERNO'}],possibilities:[{kind:'hypothesis',pattern_id:'oral_lichen_planus',label:'Líquen plano oral'},{kind:'hypothesis',pattern_id:'lichenoid_contact',label:'Reação liquenoide de contato'}]}},selectedHypotheses:new Set(),demoMode:false,language:'pt',t:(_k,f)=>f,escape:s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),catalog:{fields:{complaint:{label:'Queixa'},intraoral:{label:'Exame intraoral'}}},stateLabel:s=>s,originLabel:s=>s};
 vm.createContext(ctx);
 const lines=fs.readFileSync('app/static/app.js','utf8').split('\n');
 vm.runInContext(lines.filter(x=>/^function (referralDocument|possibilityName|buildReferralBody)\(/.test(x)).join('\n'),ctx);
 $('referralBody').value='Descrição revisada pelo profissional';$('reason').value='Avaliação em Estomatologia';
 return {ctx,$};
}
test('referral excludes all internal reflection and hypotheses by default',()=>{
 const {ctx}=documentSetup();const html=ctx.referralDocument();
 assert.match(html,/Descrição revisada pelo profissional/);
 assert.doesNotMatch(html,/REFLEXAO_PRIVADA|PROCEDIMENTO_INTERNO|Líquen plano|Reação liquenoide/);
 ctx.selectedHypotheses.add('oral_lichen_planus');const selected=ctx.referralDocument();
 assert.match(selected,/Líquen plano oral/);assert.doesNotMatch(selected,/Reação liquenoide|REFLEXAO_PRIVADA|PROCEDIMENTO_INTERNO/);
});
test('edited referral text and local identity are escaped before rendering',()=>{
 const {ctx,$}=documentSetup();$('referralBody').value='<script>danger()</script>';$('patient').value='<img src=x onerror=danger()>';
 const html=ctx.referralDocument();assert.doesNotMatch(html,/<script>|<img/);assert.match(html,/&lt;script&gt;/);assert.match(html,/&lt;img/);
});
test('referral distinguishes an unassessed examination from an absent finding',()=>{
 const {ctx}=documentSetup();
 const body=ctx.buildReferralBody({active_fields:['complaint','intraoral'],fact_meta:{complaint:{state:'reported',origin:'professional'},intraoral:{state:'not_assessed'}}},{complaint:'Dor',intraoral:'Não avaliado'});
 assert.match(body,/Queixa: Dor/);assert.match(body,/Exame intraoral \(not_assessed\)/);assert.doesNotMatch(body,/absent/);
});
