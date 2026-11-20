# -*- coding: utf-8 -*-
"""交互页 V2 自检：①数据一致性（沿用35项）②浮层不再出现未渲染标签文本的根因验证。

浮层验证方法（无浏览器自动化库时的确定性静态验证）：
- 旧 bug 根因 = hover 模板里拼接了 '<table>/<tr>/<td>' 字符串，被 Plotly 当纯文本显示。
- 修复后：所有表格结构由 document.createElement 创建，所有动态文本由 textContent 写入
  （textContent 语义上把字符串当纯文本，即便内容含 '<' 也不会渲染成标签）。
- 检查：hovertemplate 只含 %{x} 占位符无 HTML 标签；源码不存在旧的 hover_html 字符串拼接；
  createElement 创建了 table/tr/td/th；动态字段走 textContent；CSS 有浮层样式。
"""
from __future__ import annotations
import json, re
from pathlib import Path

WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
D=json.loads((WS/"interactive_equity_data.json").read_text(encoding="utf-8"))
CO=json.loads((WS/"portfolio_compound_out.json").read_text(encoding="utf-8"))
BT=json.loads((WS/"backtest_out.json").read_text(encoding="utf-8"))
CFG=D["config"]; INIT=CFG["initial_capital"]
html=(WS/"复利资产曲线_交互复盘.html").read_text(encoding="utf-8")
checks=[]
def ck(n,ok,info=""): checks.append((n,bool(ok),info))
def close(a,b,t=0.02): return abs(float(a)-float(b))<=t

# ========== A. 数据一致性（与引擎逐项核对）==========
for tag,g in [("c7","C7单池"),("dual","C6+C7双池")]:
    p=D["pools"][tag]; ns=p["nodes"]
    ck(f"{g}/节点669",len(ns)==669,f"{len(ns)}")
    ck(f"{g}/起点20000",close(ns[0]["equity"],INIT,0.01))
    ck(f"{g}/终点=引擎终值",close(ns[-1]["equity"],CO["pools"][g]["portfolio"]["final"],0.02))
    ck(f"{g}/逐日净值零差异",p["max_equity_diff_vs_engine"]<0.011,f"{p['max_equity_diff_vs_engine']}")
    bad=sum(1 for n in ns if abs(n["ret_pct"]-(n["equity"]/INIT-1)*100)>0.01)
    ck(f"{g}/收益率自洽",bad==0)
    bad=0; nnew=0; nsell=0
    for n in ns:
        for h in n["holdings"]:
            if abs(h["pnl_amount"]-(h["market_value"]-h["cost"]))>0.02: bad+=1
            if h["pnl_pct"]!=0 and (h["pnl_pct"]>0)!=(h["pnl_amount"]>0): bad+=1
            if h["is_new"]:
                nnew+=1
                if not h["buy_reason"]: bad+=1
        for s in n["sells"]:
            nsell+=1
            if s["reason"] not in ("止盈(+15%)","止损(-8%)","持有7日到期"): bad+=1
    ck(f"{g}/持仓盈亏自洽",bad==0,f"bad={bad}")
    ck(f"{g}/新增有买入原因",nnew>0,f"n={nnew}")
    ck(f"{g}/卖出有退出原因",nsell>0,f"n={nsell}")
    badc=sum(1 for n in ns for h in n["holdings"] if not re.fullmatch(r"\d{6}",h["code"]))
    ck(f"{g}/代码6位",badc==0)
    tb=CO["pools"][g]["trade_base"]; b=BT["groups"][g]["全区间"]
    for k in ["n_signals","n_filled","avg_ret","win_rate","profit_factor"]:
        ck(f"{g}/逐笔{k}一致",close(tb[k],b[k],0.001),f"{tb[k]} vs {b[k]}")

# ========== B. 浮层未渲染标签根因验证 ==========
# B1: hovertemplate 只含 %{x} 占位符，无 HTML 标签
hts=re.findall(r'hovertemplate\s*:\s*"([^"]*)"',html)
ck("hover/模板无HTML标签",all(not re.search(r'<(table|tr|td|th|br|span|div)',h,re.I) for h in hts),f"n_tpl={len(hts)} {hts[:3]}")
# B2: 源码不存在旧的 hover_html 字符串拼接（'<table style=...' 拼接进 customdata）
ck("hover/无旧字符串拼接", "hover_html" not in html and
   "customdata=[hover_html" not in html and
   "<table style='width:100%;border-collapse" not in html)
# B3: 表格结构由 createElement 创建（真 DOM，不是字符串）
for tagname in ["table","thead","tbody","tr","th","td","br"]:
    ck(f"hover/createElement({tagname})", f"createElement('{tagname}')" in html or f"el('{tagname}'" in html)
# B4: 动态文本走 textContent（把 '<' 当纯文本，天然不渲染成标签）
ck("hover/文本走textContent", "e.textContent=String(text)" in html and
   "textContent" in html and html.count("textContent")>=5,
   f"count={html.count('textContent')}")
# B5: 浮层 CSS（圆角/阴影/半透明/最大宽度/表格右对齐/胶囊徽标）
for token in ["#tt","border-radius:12px","box-shadow:0 12px 36px","rgba(255,255,255,.97)",
              "max-width:620px",".tt-table","text-align:right",".badge","backdrop-filter"]:
    ck(f"style/{token[:18]}", token in html)
# B6: A股涨跌色（盈红亏绿）
ck("style/盈红亏绿", "--up:#c0392b" in html and "--down:#1a9850" in html and
   "pcls(v)" in html)
# B7: plotly_hover 事件驱动自定义浮层
ck("hover/事件驱动", "plotly_hover" in html and "plotly_unhover" in html and
   "renderTooltip" in html and "tip.style.display='block'" in html)
# B8: 自包含离线
ck("HTML/离线自包含", "plotly.js" in html.lower() or "Plotly.newPlot" in html, f"size={len(html)}")
ck("HTML/不可得标注", "不可得" in html and "交易成本" in html)
ck("HTML/分界标注", "2025-12-31" in html and "2026-01-05" in html)

npass=sum(1 for _,ok,_ in checks if ok)
print(f"交互页V2自检: {npass}/{len(checks)} PASSED")
for n,ok,info in checks:
    if not ok: print("  FAIL",n,info)
print("VERIFY_INTERACTIVE_V2="+("ALL_OK" if npass==len(checks) else "HAS_FAIL"))
