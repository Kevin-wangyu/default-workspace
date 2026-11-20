# -*- coding: utf-8 -*-
"""持仓一致性修复自检：
1) 全量扫描两类问题（同日重复标的 / 卖出日无前日持仓）→修复后应为0；
2) 页面内嵌节点 JSON 与交互式重放输出逐项核对；
3) 逐笔四指标与 backtest_out.json 一致；
4) 页面无未渲染裸标签（hover 模板不含HTML表格标签）；
5) 净值与引擎CSV逐日对齐；成本不可得声明存在。
"""
from __future__ import annotations
import json, re, sys
from collections import Counter
from pathlib import Path
import pandas as pd

WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
D=json.loads((WS/"interactive_equity_data.json").read_text(encoding="utf-8"))
BT=json.loads((WS/"backtest_out.json").read_text(encoding="utf-8"))
HTML=(WS/"复利资产曲线_交互复盘.html").read_text(encoding="utf-8")
CHK=[]
def ck(name, cond, detail=""):
    CHK.append((name, bool(cond), detail))

# ---- 1) 全量扫描两类问题（对页面实际节点数据）----
tot_days=0; dup_bad=0; sell_bad=0; sell_same_day=0
for tag,p in D["pools"].items():
    nodes=p["nodes"]; tot_days+=len(nodes)
    prev_codes=set()
    for n in nodes:
        codes=[h["code"] for h in n["holdings"]]
        if len(codes)!=len(set(codes)): dup_bad+=1
        for s in n["sells"]:
            # 卖出标的：要么在前一日持仓中，要么标注为当日回转
            if s["code"] not in prev_codes:
                if s.get("is_same_day") or s.get("entry_date")==n["date"]:
                    sell_same_day+=1
                else:
                    sell_bad+=1
        prev_codes=set(codes)
ck("全量扫描-扫描日期总数=1338(669x2)", tot_days==1338, f"tot_days={tot_days}")
ck("A类同日重复标的-修复后=0", dup_bad==0, f"dup_bad={dup_bad}")
ck("B类卖出无前日持仓且非当日回转-修复后=0", sell_bad==0, f"sell_bad={sell_bad}")
ck("B类当日回转已正确标注(可追溯)", sell_same_day>0, f"same_day_tagged={sell_same_day}")

# ---- 2) 页面内嵌数据 vs 重放JSON ----
m=re.search(r'<script type="application/json" id="node-data">(.*?)</script>', HTML, re.S)
ck("页面内嵌node-data存在", bool(m))
if m:
    page=json.loads(m.group(1))
    for tag in ["c7","dual"]:
        pn=page["pools"][tag]["nodes"]; jn=D["pools"][tag]["nodes"]
        ck(f"[{tag}]节点数一致", len(pn)==len(jn)==669, f"{len(pn)}/{len(jn)}")
        eq_ok=all(abs(a["equity"]-b["equity"])<0.005 for a,b in zip(pn,jn))
        ck(f"[{tag}]逐日equity逐项一致", eq_ok)
        hold_ok=all(a["holdings"]==b["holdings"] for a,b in zip(pn,jn))
        ck(f"[{tag}]逐日holdings逐项一致", hold_ok)
        sell_ok=all(a["sells"]==b["sells"] for a,b in zip(pn,jn))
        ck(f"[{tag}]逐日sells逐项一致", sell_ok)
        na_ok=all(len(a["holdings"])==len(set(h["code"] for h in a["holdings"])) for a in pn)
        ck(f"[{tag}]页面持仓code唯一", na_ok)

# ---- 3) 逐笔四指标 vs backtest_out.json ----
for tag,gname in [("c7","C7单池"),("dual","C6+C7双池")]:
    d=pd.read_csv(WS/f"backtest_detail_{tag}.csv",encoding="utf-8-sig")
    fl=d[d["filled"].astype(bool)]
    b=BT["groups"][gname]["全区间"]
    ck(f"[{tag}]成交笔数={b['n_filled']}", len(fl)==b["n_filled"], f"{len(fl)}")
    ck(f"[{tag}]期望={b['avg_ret']}%", abs(fl.ret.mean()-b["avg_ret"])<1e-4)
    ck(f"[{tag}]胜率={b['win_rate']}%", abs((fl.ret>0).mean()*100-b["win_rate"])<0.01)
    pf=fl.ret[fl.ret>0].sum()/abs(fl.ret[fl.ret<0].sum())
    ck(f"[{tag}]PF={b['profit_factor']}", abs(pf-b["profit_factor"])<1e-3)

# ---- 4) 无裸标签：解析 FIG 配置本身（不能全 HTML 搜，Plotly.js 库代码含大量同名字符串）----
SRC=(WS/"make_interactive_page.py").read_text(encoding="utf-8")
mfig=re.search(r'const FIG=(\{.*?\});</script>', HTML, re.S)
ck("FIG配置可解析", bool(mfig))
if mfig:
    figj=json.loads(mfig.group(1))
    hts=[tr.get("hovertemplate") for tr in figj["data"]]
    ck("FIG trace hovertemplate极简(无表格标签)",
       all(h and len(h)<60 and not any(t in h for t in ("<table","<tr","<td","<th")) for h in hts),
       str(hts))
    ck("FIG trace无customdata表格拼接",
       all("customdata" not in tr for tr in figj["data"]))
ck("无旧hover_html表格拼接", "hover_html" not in HTML and "hover_html" not in SRC)
ck("DOM建表(el helper内部createElement)",
   "el('th'" in SRC and "el('td'" in SRC and "document.createElement(tag)" in SRC)
ck("textContent写文本(防裸标签)", "e.textContent=String(text)" in HTML)
ck("当日回转徽标存在", "badge intraday" in HTML and "当日回转" in HTML)
ck("多笔合并徽标存在", "badge lots" in HTML and "笔合并" in HTML)

# ---- 5) 净值与引擎CSV逐日对齐 ----
for tag in ["c7","dual"]:
    p=D["pools"][tag]
    ck(f"[{tag}]重放净值maxdiff<=0.005", p["max_equity_diff_vs_engine"]<=0.005,
       f"diff={p['max_equity_diff_vs_engine']}")

# ---- 6) 成本不可得声明 ----
ck("成本不可得声明存在", "不可得" in HTML and "不以替代值填充" in HTML)

npass=sum(1 for _,ok,_ in CHK if ok)
print("="*72)
for name,ok,det in CHK:
    print(("  PASS " if ok else "  FAIL ")+name+("  ["+det+"]" if det else ""))
print("="*72)
print(f"HOLDING_FIX_CHECK {npass}/{len(CHK)} " + ("ALL PASSED" if npass==len(CHK) else "FAILED"))
sys.exit(0 if npass==len(CHK) else 1)
