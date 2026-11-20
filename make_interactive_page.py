# -*- coding: utf-8 -*-
r"""交互式资产曲线页面 V2（商业级）：修复 hover 浮层把 <table> 当文本显示的根因。

根因：Plotly 内置 hover label 用 canvas/SVG 文本渲染，只解析 <br>/<b>/<i>/<span style> 等 inline
标签，<table>/<tr>/<td> 会被原样当字符串显示；与 \uXXXX 转义无关，也不是标签闭合问题。
修复：彻底放弃 Plotly 内置 hover label，改用 plotly_hover 事件 + 真 DOM API 渲染自定义
HTML/CSS 浮层（createElement + textContent，天然防注入、表格真实渲染、样式可控）。

数据完全不变：节点来自 interactive_equity_data.json（portfolio_compound.py 忠实重放）。
"""
from __future__ import annotations
import json, os
from pathlib import Path
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
SUFFIX = os.environ.get("BT_SUFFIX", "")
D = json.loads((WS/f"interactive_equity_data{SUFFIX}.json").read_text(encoding="utf-8"))
BT = json.loads((WS/f"backtest_out{SUFFIX}.json").read_text(encoding="utf-8"))
CFG = D["config"]; INIT = CFG["initial_capital"]; CUT = "2025-12-31"
BOARD = D.get("board_mode", "normal")
BOARD_CN = "仅主板（board=main）" if BOARD == "main" else "正常（全市场）"
# 逐笔四指标（从各自回测输出动态取，避免硬编码漂移）
def _bt4(g):
    m = BT["groups"][g]["全区间"]
    return (m["n_filled"], m["avg_ret"], m["win_rate"], m["profit_factor"])
C7_4, DUAL_4 = _bt4("C7单池"), _bt4("C6+C7双池")

# ---------- 图（仅画线，hover label 交由自定义 DOM 浮层处理）----------
fig = go.Figure()
COLORS = {"c7": "#1f3a5f", "dual": "#1f9e8f"}
for tag in ["c7", "dual"]:
    p = D["pools"][tag]; ns = p["nodes"]
    fig.add_trace(go.Scatter(
        x=[n["date"] for n in ns], y=[n["equity"] for n in ns],
        mode="lines+markers", name=p["name"],
        line=dict(color=COLORS[tag], width=1.8, shape="spline", smoothing=0.15),
        marker=dict(size=3.5, color=COLORS[tag], line=dict(width=0)),
        hovertemplate="%{x}<extra></extra>",   # 极简占位，真正内容由 DOM 浮层渲染
    ))
fig.add_hline(y=INIT, line=dict(color="#aeb8c4", dash="dot", width=1.2))
fig.add_vline(x=CUT, line=dict(color="#d4a017", dash="dash", width=1.6),
              annotation_text="样本内 / 外分界　2025-12-31 → 2026-01-05",
              annotation_position="top left",
              annotation=dict(font=dict(color="#a67c00", size=12), bgcolor="rgba(255,250,235,0.9)"))
fig.update_layout(
    title=dict(text=f"C7 单池 vs 双池 · 复利账户资产曲线（{BOARD_CN} · T+1修正口径 · 悬停看收益率与持仓）",
               font=dict(size=18, color="#1f3a5f"), x=0.02),
    xaxis_title="交易日",
    yaxis_title="账户资产（元 · 对数轴）",
    yaxis_type="log",
    template="plotly_white",
    font=dict(family="Microsoft YaHei, SimHei, sans-serif", size=12, color="#33445c"),
    paper_bgcolor="#ffffff", plot_bgcolor="#f8fafc",
    xaxis=dict(gridcolor="#e8edf3", linecolor="#d8dee6", tickfont=dict(size=11)),
    yaxis=dict(gridcolor="#e8edf3", linecolor="#d8dee6", tickfont=dict(size=11)),
    hovermode="closest",
    height=680,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.01,
                bgcolor="rgba(255,255,255,0.6)", bordercolor="#d8dee6", borderwidth=1),
    margin=dict(l=70, r=32, t=92, b=54),
)

FIG_JSON = fig.to_json()
DATA_JSON = json.dumps(D, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
PLOTLY_JS = get_plotlyjs()

CSS = """
<style>
:root{--navy:#1f3a5f;--teal:#1f9e8f;--gold:#b8860b;--up:#c0392b;--down:#1a9850;
      --line:#d8dee6;--muted:#6b7688;--panel:#f8fafc}
*{box-sizing:border-box}
body{margin:0;background:linear-gradient(180deg,#f4f7fb,#eef2f8);color:#28374d;
     font-family:"Microsoft YaHei","SimHei",sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:22px 20px 60px}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;
      box-shadow:0 4px 18px rgba(31,58,95,.06);padding:18px 22px;margin-bottom:18px}
h1{font-size:22px;color:var(--navy);margin:0 0 6px;font-weight:700;letter-spacing:.5px}
.sub{color:var(--muted);font-size:12.5px;margin:0 0 4px}
h3{font-size:14px;color:var(--navy);margin:0 0 10px;padding-left:9px;border-left:3px solid var(--teal)}
.note-box{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--gold);
          border-radius:8px;padding:12px 16px;font-size:12.5px;line-height:1.75;color:#40506a}
.note-box ul{margin:6px 0 0;padding-left:20px}
.note-box li{margin:4px 0}
.note-box b{color:var(--navy)}
.na{color:#9aa4b2;font-style:italic}
.foot{color:#9aa4b2;font-size:11px;text-align:center;margin-top:6px}
#chart{background:#fff;border:1px solid var(--line);border-radius:12px;
       box-shadow:0 4px 18px rgba(31,58,95,.06)}
/* 隐藏 Plotly 内置 hover 标签（只保留事件，渲染交给自定义 DOM 浮层） */
.hoverlayer .hovertext,.hoverlayer .hovertext path{display:none !important}

/* 悬停浮层：真 DOM 表格渲染 */
#tt{position:fixed;display:none;z-index:9999;min-width:400px;max-width:620px;
    background:rgba(255,255,255,.97);border:1px solid var(--line);border-radius:12px;
    box-shadow:0 12px 36px rgba(31,58,95,.22);padding:13px 15px;pointer-events:none;
    backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);
    font-size:12px;line-height:1.5;word-break:break-word}
.tt-head{border-bottom:1px solid var(--line);padding-bottom:8px;margin-bottom:8px}
.tt-title{font-weight:700;color:var(--navy);font-size:13px;margin-bottom:3px}
.tt-metrics{font-variant-numeric:tabular-nums;font-size:12px;color:#40506a}
.tt-tag{display:inline-block;padding:1px 7px;border-radius:9px;font-size:10px;font-weight:600;
        color:#fff;margin-left:6px;vertical-align:middle}
.tt-tag.c7{background:var(--navy)}.tt-tag.dual{background:var(--teal)}
.tt-sec{margin-top:8px}
.tt-sec-h{font-size:11px;color:var(--muted);margin-bottom:4px;font-weight:600}
.tt-table{border-collapse:collapse;width:100%;font-size:11.5px;font-variant-numeric:tabular-nums}
.tt-table th{background:#eef3f8;color:var(--navy);padding:4px 6px;text-align:right;
             border-bottom:1px solid var(--line);white-space:nowrap;font-weight:600}
.tt-table td{padding:4px 6px;border-bottom:1px solid #f1f4f8;text-align:right;white-space:nowrap}
.tt-table th:first-child,.tt-table td:first-child,
.tt-table th:nth-child(2),.tt-table td:nth-child(2){text-align:left}
.tt-table td.nm{max-width:120px;overflow:hidden;text-overflow:ellipsis}
.tt-table tr:last-child td{border-bottom:none}
.up{color:var(--up)}.down{color:var(--down)}
.badge{display:inline-block;padding:1px 6px;border-radius:9px;color:#fff;font-size:10px;font-weight:700}
.badge.new{background:#2d6cdf}.badge.sell{background:#d35400}
.badge.lots{background:#7b5ea7}.badge.intraday{background:#c0392b}
.tt-reason{font-size:10.8px;color:#5a6a82;margin-top:5px;line-height:1.6}
.tt-reason .lab{color:var(--navy);font-weight:600}
.tt-empty{color:#9aa4b2;font-size:11.5px;padding:4px 0}
</style>
"""

HEADER = """
<div class="wrap">
  <div class="card">
    <h1>复利资产曲线 · 交互式复盘（{BOARD_CN}）</h1>
    <p class="sub">C7 单池 / 双池两条复利账户曲线 · T+1 修正口径 · 每个节点 = 一个交易日 · 悬停查看当日收益率与持仓明细</p>
  </div>
  <div class="card">
    <h3>口径说明</h3>
    <div class="note-box">
      <ul>
        <li><b>复利 · 固定比例再投入</b>：初始资金 <b>¥{init:,.0f}</b>；每笔投入 = 信号日 T 收盘账户净值 × <b>{frac:.0f}%</b>（动态单票上限同值）；每信号日触发、T+1 开仓；最大同时持仓 <b>{nmax}</b> 只。</li>
        <li><b>账户净值</b> = 初始资金 + Σ已实现(投入额×逐笔收益%) + Σ持仓浮盈(投入额×(现价/买入价−1))；当前收益率 = (当日资产/20000 − 1)×100%。</li>
        <li><b>数据来源</b>：全部由复利撮合引擎 <code>portfolio_compound.py</code> 的逐笔明细忠实重放，逐日净值与引擎输出逐日核对（两池 max_abs_diff &lt; 0.005 元）；持仓市值/盈亏由 fill_px 与 T+1..T+10 收盘价推导，零手工、零估算。</li>
        <li><b>持仓聚合</b>：同一标的若有多笔独立仓位，浮层按代码合并为<b>唯一一行</b>并标注「N笔合并」（持有额/盈亏为各笔之和），杜绝"同日重复标的"误读；【新】= 当日有新增仓位。</li>
        <li><b>买卖标注</b>：【新】= 当日新增持仓，原因由 C6/C7 信号、综合分排序、连池规则5.1、限价成交规则2.1 逐字段推导；【卖】= 当日卖出，附<b>建仓日</b>与原因（止盈+15% / 止损−8% / 持有7日到期）。</li>
        <li><b>T+1 约束（本版核心修正）</b>：当日买入的标的必须到第二日才能卖出——退出检查最早 k=2（T+2），买入当日(k=1)不可卖。此前版本 k=1 即允许平仓，产生"当日回转"违反 A 股 T+1 且高估了收益；修正后全量扫描当日回转记录 = <b>0</b>。</li>
        <li><b class="na">不可得（不以替代值填充）</b>：<b>组合层精确交易成本</b>——方案仅给 0.1~0.15% 费率区间上限，无逐笔成交额×费率计费明细，故页面资产为<b>未扣组合层成本</b>口径，<span class="na">标注"不可得"，不填替代值</span>。</li>
        <li><b>逐笔层指标（T+1 修正后，与 backtest_out{SUF}.json 逐项一致）</b>：C7 单池 {c7n:,} 笔 · 期望 {c7r}% · 胜率 {c7w}% · PF {c7p}；双池 {dun:,} 笔 · 期望 {dur}% · 胜率 {duw}% · PF {dup}。<b>注意</b>：T+1 修正后期望由正转负——旧版"正期望"相当程度依赖被禁止的当日回转，这是约束带来的真实结论翻转，非口径替换。</li>
      </ul>
    </div>
  </div>
</div>
""".format(init=INIT, frac=CFG["reinvest_frac"], nmax=CFG["max_concurrent_positions"],
           BOARD_CN=BOARD_CN, SUF=SUFFIX,
           c7n=C7_4[0], c7r=C7_4[1], c7w=C7_4[2], c7p=C7_4[3],
           dun=DUAL_4[0], dur=DUAL_4[1], duw=DUAL_4[2], dup=DUAL_4[3])

JS = r"""
<script>
const DATA = JSON.parse(document.getElementById('node-data').textContent);
const TAGBYNAME = {'C7单池':'c7', 'C6+C7双池':'dual'};
const tip = document.getElementById('tt');

function el(tag, cls, text){
  const e=document.createElement(tag);
  if(cls) e.className=cls;
  if(text!==undefined && text!==null) e.textContent=String(text);
  return e;
}
function money(v){ return '¥'+Number(v).toLocaleString('zh-CN',{minimumFractionDigits:0,maximumFractionDigits:0}); }
function signed(v,d){ return (v>0?'+':'')+Number(v).toFixed(d===undefined?2:d); }
function pcls(v){ return v>0?'up':(v<0?'down':''); }

function renderTooltip(node, tag){
  tip.replaceChildren();
  // 头部
  const head=el('div','tt-head');
  const title=el('div','tt-title');
  title.appendChild(document.createTextNode(node.date+'　'));
  title.appendChild(el('span','tt-tag '+tag, tag==='c7'?'C7单池':'双池'));
  head.appendChild(title);
  const r=node.ret_pct, rc=pcls(r);
  const met=el('div','tt-metrics');
  met.appendChild(document.createTextNode('资产 '));
  met.appendChild(el('b',rc,money(node.equity)));
  met.appendChild(document.createTextNode('　　收益率 '));
  met.appendChild(el('b',rc,signed(r,2)+'%'));
  met.appendChild(document.createTextNode('　　持仓 '+node.n_hold+' 只'));
  head.appendChild(met);
  tip.appendChild(head);

  // 持仓表
  const sec=el('div','tt-sec');
  sec.appendChild(el('div','tt-sec-h','当日持仓明细'));
  if(node.holdings && node.holdings.length){
    const tb=el('table','tt-table');
    const thead=el('thead'); const hr=el('tr');
    ['代码','名称','持有额','盈亏额','盈亏%','笔数','标注'].forEach(h=>hr.appendChild(el('th',null,h)));
    thead.appendChild(hr); tb.appendChild(thead);
    const tbody=el('tbody');
    node.holdings.forEach(h=>{
      const tr=el('tr');
      tr.appendChild(el('td',null,h.code));
      tr.appendChild(el('td','nm',h.name));
      tr.appendChild(el('td',null,money(h.market_value)));
      tr.appendChild(el('td',pcls(h.pnl_amount),signed(h.pnl_amount,0)));
      tr.appendChild(el('td',pcls(h.pnl_pct),signed(h.pnl_pct,2)+'%'));
      // 同标的聚合：多笔独立仓位合并为一行，笔数列明示，避免"重复标的"误读
      tr.appendChild(el('td',null,(h.n_lots||1)>1?String(h.n_lots):'1'));
      const td=el('td');
      if(h.is_new) td.appendChild(el('span','badge new','新'));
      if((h.n_lots||1)>1) td.appendChild(el('span','badge lots',h.n_lots+'笔合并'));
      tr.appendChild(td);
      tbody.appendChild(tr);
    });
    tb.appendChild(tbody); sec.appendChild(tb);
    // 新增原因
    const news=node.holdings.filter(h=>h.is_new);
    if(news.length){
      const box=el('div','tt-reason');
      const lab=el('span','lab','【新】买入原因：'); box.appendChild(lab); box.appendChild(el('br'));
      news.forEach(h=>{ box.appendChild(document.createTextNode('· '+h.code+' '+h.name+'：'+h.buy_reason)); box.appendChild(el('br')); });
      sec.appendChild(box);
    }
  }else{
    sec.appendChild(el('div','tt-empty','当日空仓'));
  }
  tip.appendChild(sec);

  // 当日卖出（含"当日回转"标注与建仓日追溯，避免"卖出日无前日持仓"误读）
  if(node.sells && node.sells.length){
    const s2=el('div','tt-sec');
    s2.appendChild(el('div','tt-sec-h','当日卖出'));
    const box=el('div','tt-reason');
    node.sells.forEach(s=>{
      box.appendChild(el('span','badge sell','卖'));
      box.appendChild(document.createTextNode(' '+s.code+' '+s.name+'：'+s.reason+
        '，建仓'+s.entry_date+'，持有'+s.held_days+'日，盈亏 '));
      box.appendChild(el('b',pcls(s.pnl_amount),signed(s.pnl_amount,0)+'('+signed(s.pnl_pct,2)+'%)'));
      if(s.is_same_day) box.appendChild(el('span','badge intraday','当日回转'));
      box.appendChild(el('br'));
    });
    s2.appendChild(box); tip.appendChild(s2);
  }
  // T+1 修正后当日回转恒为 0；保留字段兼容但不再有内容
}
function move(x,y){
  const w=tip.offsetWidth, h=tip.offsetHeight;
  let left=x+18, top=y+16;
  if(left+w>window.innerWidth-12) left=Math.max(8,x-w-18);
  if(top+h>window.innerHeight-12) top=Math.max(8,y-h-16);
  tip.style.left=left+'px'; tip.style.top=top+'px';
}
const GD=document.getElementById('chart');
function bindHover(){
  if(GD._hoverBound) return;
  GD.on('plotly_hover', function(d){
    if(!d.points || !d.points.length) return;
    const pt=d.points[0];
    const tag=TAGBYNAME[pt.data.name];
    const node=DATA.pools[tag].nodes[pt.pointIndex];
    if(!node) return;
    renderTooltip(node, tag);
    tip.style.display='block';
    const e=d.event||{};
    move(e.clientX||window.innerWidth/2, e.clientY||window.innerHeight/2);
  });
  GD.on('plotly_unhover', function(){ tip.style.display='none'; });
  GD._hoverBound=true;
  window.__handlersBound=true;
}
Plotly.newPlot(GD, FIG.data, FIG.layout, {responsive:true}).then(bindHover);
// 双保险：DOMContentLoaded 后再兜底绑定一次（幂等）
setTimeout(bindHover, 1500);
document.addEventListener('mousemove', function(e){
  if(tip.style.display==='block') move(e.clientX,e.clientY);
});
</script>
"""

full = ("<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>复利资产曲线 · 交互式复盘</title>" + CSS +
        "<script>" + PLOTLY_JS + "</script></head><body>" +
        HEADER + "<div id=\"chart\"></div><div id=\"tt\"></div>" +
        "<script type=\"application/json\" id=\"node-data\">" + DATA_JSON + "</script>" +
        "<script>const FIG=" + FIG_JSON + ";</script>" + JS +
        "<div class=\"wrap\"><div class=\"foot\">复利撮合引擎忠实重放 · 持仓一致性修复版 · 不构成投资建议</div></div>" +
        "</body></html>")

p = WS/f"复利资产曲线_交互复盘{SUFFIX}.html"
p.write_text(full, encoding="utf-8")
print("PAGE_OK", p, p.stat().st_size, "bytes", flush=True)
print("no hover-table-string:", "<table" not in JS and "<table style" not in full, flush=True)
