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
