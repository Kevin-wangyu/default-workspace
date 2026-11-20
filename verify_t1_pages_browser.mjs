// T+1 两张交互页浏览器验证：无"当日回转"标识、hover 真表格、无裸标签。
// 基于已验证的 verify_hover_browser.mjs CDP 模板。
import { spawn } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const WS = 'D:\\Users\\KFish\\Documents\\deepseek-harness\\default-workspace';
const PAGES = [
  ['normal', WS + '\\复利资产曲线_交互复盘.html'],
  ['main',   WS + '\\复利资产曲线_交互复盘_main.html'],
];
const PORT = 9241;
const USERDIR = WS + '\\.chrome-cdp-t1';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const proc = spawn(CHROME, ['--headless=new','--disable-gpu','--no-first-run',
  `--remote-debugging-port=${PORT}`,`--user-data-dir=${USERDIR}`,'--window-size=1400,1600','about:blank'],
  {detached:true,stdio:'ignore'});
proc.stdout?.on('error',()=>{});
async function cleanup(){ try{spawn('taskkill',['/pid',String(proc.pid),'/T','/F'],{stdio:'ignore'});}catch(e){} }
let ws, msgId=0; const pending=new Map();
function send(method,params={}){return new Promise((res,rej)=>{const id=++msgId;
  pending.set(id,{res,rej}); ws.send(JSON.stringify({id,method,params}));});}
async function waitReady(){for(let i=0;i<100;i++){try{const r=await fetch(`http://127.0.0.1:${PORT}/json/version`);
  if(r.ok)return await r.json();}catch(e){}await sleep(400);}throw new Error('CDP not ready');}

const results=[];
function chk(c,label,detail=''){results.push([!!c,label,detail]);}

try{
  await waitReady();
  const targets=await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const page=targets.find(t=>t.type==='page');
  ws=new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
  ws.onmessage=ev=>{const m=JSON.parse(ev.data);
    if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);
      m.error?p.rej(new Error(JSON.stringify(m.error))):p.res(m.result);}};
  await send('Page.enable'); await send('Runtime.enable');

  for(const [mode, PAGE] of PAGES){
    await send('Page.navigate',{url:pathToFileURL(PAGE).href});
    async function ev(expr){const r=await send('Runtime.evaluate',{expression:expr,returnByValue:true,awaitPromise:true});
      if(r.exceptionDetails)throw new Error('JSERR '+(r.exceptionDetails.exception?.description||''));return r.result.value;}
    let ready=false;
    for(let i=0;i<120;i++){try{ready=await ev("!!(window.Plotly&&document.getElementById('chart')?.data?.length>=2&&document.getElementById('tt'))");}catch(e){}
      if(ready)break; await sleep(500);}
    chk(ready, `[${mode}] 页面加载+Plotly渲染`);
    if(!ready) continue;
    await sleep(1000);
    chk(await ev('!!window.__handlersBound'), `[${mode}] hover事件绑定`);

    // T+1后当日回转恒为0：浮层内不应出现"当日回转"徽标（页面口径说明里如实提及属合法文字）
    const intradayBadge=await ev(`(function(){const el=document.getElementById('tt');
      return !!(el && el.querySelector && el.querySelector('.badge.intraday'));})()`);
    chk(!intradayBadge, `[${mode}] 浮层无当日回转徽标`);

    // 计数器包裹 renderTooltip
    await ev(`(function(){window.__hc=0;const o=window.renderTooltip;
      window.renderTooltip=function(){window.__hc++;return o.apply(this,arguments);};return true;})()`);

    // 找首个有持仓的节点并 hover
    const probe=await ev(`(function(){
      const gd=document.getElementById('chart');
      const D=JSON.parse(document.getElementById('node-data').textContent);
      const tag=Object.keys(D.pools)[0];
      const ns=D.pools[tag].nodes;
      let idx=ns.findIndex(n=>n.holdings&&n.holdings.length>=1);
      const n=ns[idx];
      const traces=gd.querySelectorAll('.scatterlayer .trace');
      const tr=traces[0];
      const paths=tr.querySelectorAll('path.point');
      const p=paths[idx];
      if(!p)return {err:'no path point',idx,total:paths.length,traces:traces.length};
      const r=p.getBoundingClientRect();
      return {idx,date:n.date,nHold:n.holdings.length,x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)};
    })()`);
    if(probe.err){chk(false,`[${mode}] 定位hover节点`,JSON.stringify(probe));continue;}

    await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:5,y:5}); await sleep(120);
    await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:probe.x,y:probe.y,buttons:0}); await sleep(700);

    const hv=await ev(`(function(){const el=document.getElementById('tt');const t=el?el.innerText:'';
      return {calls:window.__hc,disp:el?getComputedStyle(el).display:'none',
              tables:el?el.querySelectorAll('table').length:0,
              rows:el?el.querySelectorAll('tbody tr').length:0,
              naked:/<table|<tr|<td|<th|<thead|<tbody|<br|<span|<div|style=/.test(t),txt:t.slice(0,150)};})()`);
    chk(hv.calls>0 && hv.disp!=='none', `[${mode}] 真实hover触发浮层`, JSON.stringify(hv).slice(0,140));
    chk(hv.tables>=1 && hv.rows>=1, `[${mode}] 浮层真表格渲染`, `tables=${hv.tables} rows=${hv.rows}`);
    chk(!hv.naked, `[${mode}] 浮层无裸HTML标签`, hv.txt.slice(0,80));
  }
  ws.close();
}catch(e){
  console.log('CDP_ERROR', String(e));
  chk(false,'CDP流程',String(e));
}finally{
  await cleanup();
}
const passed=results.filter(x=>x[0]).length;
console.log(`T1_PAGES_BROWSER ${passed}/${results.length}`);
for(const [ok,label,d] of results) if(!ok) console.log('  FAIL:',label,d);
console.log(passed===results.length?'ALL_OK':'HAS_FAILURE');
