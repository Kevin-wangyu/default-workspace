// 真实浏览器验证：CDP 驱动 headless Chrome，用【真实鼠标移动】触发 plotly hover，
// 读取自定义浮层 #tt 的真实 DOM，验证：①浮层显示 ②真<table>渲染 ③innerText 无裸标签文本。
import { spawn } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PAGE = 'D:\\Users\\KFish\\Documents\\deepseek-harness\\default-workspace\\复利资产曲线_交互复盘.html';
const PORT = 9233;
const USERDIR = 'D:\\Users\\KFish\\Documents\\deepseek-harness\\default-workspace\\.chrome-cdp-tmp2';
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
try{
  const ver=await waitReady();console.log('CDP_BROWSER',ver.Browser);
  const targets=await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const page=targets.find(t=>t.type==='page');
  ws=new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
  ws.onmessage=ev=>{const m=JSON.parse(ev.data);
    if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);
      m.error?p.rej(new Error(JSON.stringify(m.error))):p.res(m.result);}};
  await send('Page.enable');await send('Runtime.enable');
  await send('Page.navigate',{url:pathToFileURL(PAGE).href});
  async function ev(expr){const r=await send('Runtime.evaluate',{expression:expr,returnByValue:true,awaitPromise:true});
    if(r.exceptionDetails)throw new Error('JSERR '+(r.exceptionDetails.exception?.description||''));return r.result.value;}
  let ready=false;
  for(let i=0;i<120;i++){try{ready=await ev("!!(window.Plotly&&document.getElementById('chart')?.data?.length>=2&&document.getElementById('tt'))");}catch(e){}
    if(ready)break;await sleep(500);}
  console.log('PAGE_READY',ready);if(!ready)throw new Error('page not ready');
  await sleep(1200);
  console.log('HANDLERS_BOUND',await ev('!!window.__handlersBound'));

  // 计数器：真实 hover 是否调用 renderTooltip
  await ev(`(function(){window.__hc=0;const o=window.renderTooltip;
    window.renderTooltip=function(){window.__hc++;return o.apply(this,arguments);};return true;})()`);

  // 定位 2024-09-13 双池节点：原本出现"两条跨境通"+阳普医疗当日回转，修复后应聚合为唯一行+当日回转标注
  const probe=await ev(`(function(){
    const gd=document.getElementById('chart');
    const D=JSON.parse(document.getElementById('node-data').textContent);
    const ns=D.pools.dual.nodes;
    let idx=ns.findIndex(n=>n.date==='2024-09-13');
    if(idx<0)idx=ns.findIndex(n=>n.intraday_closed&&n.intraday_closed.length&&n.holdings.length>=1);
    const n=ns[idx];
    const traces=gd.querySelectorAll('.scatterlayer .trace');
    const tr=traces[1]; // 双池
    const paths=tr.querySelectorAll('path.point');
    const p=paths[idx];
    if(!p)return {err:'no path point',idx,total:paths.length,traces:traces.length};
    const r=p.getBoundingClientRect();
    return {idx,date:n.date,nHold:n.holdings.length,nSell:n.sells.length,
      codes:n.holdings.map(h=>h.code),nLots:n.holdings.map(h=>h.n_lots||1),
      nIntraday:(n.intraday_closed||[]).length,
      x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)};
  })()`);
  console.log('PROBE',JSON.stringify(probe));
  if(probe.err)throw new Error('probe failed: '+JSON.stringify(probe));

  // CDP 真实鼠标移动到该点（先移开再移入，确保触发 hover）
  await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:5,y:5});
  await sleep(150);
  await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:probe.x,y:probe.y,buttons:0});
  await sleep(600);

  const dom=await ev(`(function(){const t=document.getElementById('tt');return {
    display:t.style.display,renderCalls:window.__hc,tables:t.querySelectorAll('table').length,
    rows:t.querySelectorAll('tbody tr').length,newB:t.querySelectorAll('.badge.new').length,
    sellB:t.querySelectorAll('.badge.sell').length,
    lotsB:t.querySelectorAll('.badge.lots').length,intradayB:t.querySelectorAll('.badge.intraday').length,
    codes:[...t.querySelectorAll('tbody tr td:first-child')].map(x=>x.textContent),
    innerText:t.innerText.slice(0,2000)};})()`);
  console.log('REAL_HOVER display='+dom.display+' renderCalls='+dom.renderCalls+
    ' tables='+dom.tables+' rows='+dom.rows+' new='+dom.newB+' sell='+dom.sellB+
    ' lots='+dom.lotsB+' intraday='+dom.intradayB);
  console.log('HOVER_CODES',JSON.stringify(dom.codes));
  console.log('TT_INNERTEXT_BEGIN');console.log(dom.innerText);console.log('TT_INNERTEXT_END');

  const txt=dom.innerText||'';
  const hasRaw=/<(table|tr|td|th|br|span|div|style|thead|tbody)\b/i.test(txt);
  // 修复验收：同一标的在浮层持仓表中只出现一次；当日回转有标注
  const codes=dom.codes||[];
  const noDup=codes.length===new Set(codes).size;
  const intradayOK=dom.intradayB>=1;  // 09-13 有阳普医疗当日回转
  const ok=dom.display==='block'&&dom.renderCalls>=1&&dom.tables>=1&&dom.rows>=1&&!hasRaw&&noDup&&intradayOK;
  console.log('NO_DUP_CODES_IN_HOVER',noDup,'INTRaday_BADGE_OK',intradayOK);
  console.log('RAW_TAG_IN_INNERTEXT',hasRaw);
  console.log('HOVER_BROWSER_OK',ok?'TRUE':'FALSE');
}catch(e){console.log('BROWSER_VERIFY_ERROR',e.message);process.exitCode=1;}
finally{if(ws)try{ws.close();}catch(e){}await cleanup();}
