# -*- coding: utf-8 -*-
"""交互页自检：页面数据 vs 引擎输出逐项核对 + HTML结构 + 不可得字段标注。"""
from __future__ import annotations
import json, re
from pathlib import Path
import numpy as np, pandas as pd

WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
D=json.loads((WS/"interactive_equity_data.json").read_text(encoding="utf-8"))
CO=json.loads((WS/"portfolio_compound_out.json").read_text(encoding="utf-8"))
BT=json.loads((WS/"backtest_out.json").read_text(encoding="utf-8"))
CFG=D["config"]; INIT=CFG["initial_capital"]
html=(WS/"复利资产曲线_交互复盘.html").read_text(encoding="utf-8")
checks=[]
def ck(n,ok,info=""): checks.append((n,bool(ok),info))
def close(a,b,t=0.02): return abs(float(a)-float(b))<=t

for tag,g in [("c7","C7单池"),("dual","C6+C7双池")]:
    p=D["pools"][tag]; ns=p["nodes"]
    # 1 节点数/起终点
    ck(f"{g}/节点数669",len(ns)==669,f"{len(ns)}")
    ck(f"{g}/起点20000",close(ns[0]["equity"],INIT,0.01),f"{ns[0]['equity']}")
    ck(f"{g}/终点=引擎复利终值",close(ns[-1]["equity"],CO["pools"][g]["portfolio"]["final"],0.02),
       f"{ns[-1]['equity']} vs {CO['pools'][g]['portfolio']['final']}")
    # 2 逐日净值与引擎CSV零差异
    ck(f"{g}/净值逐日零差异",p["max_equity_diff_vs_engine"]<0.011,f"{p['max_equity_diff_vs_engine']}")
    # 3 收益率字段=资产/20000-1
    bad=sum(1 for n in ns if abs(n["ret_pct"]-(n["equity"]/INIT-1)*100)>0.01)
    ck(f"{g}/收益率字段自洽",bad==0,f"bad={bad}")
    # 4 持仓字段自洽：market_value≈cost×(1+pnl_pct/100)，pnl_amount≈market_value-cost
    bad=0; nhold=0; nnew=0; nsell=0
    for n in ns:
        for h in n["holdings"]:
            nhold+=1
            # 精确自洽：盈亏金额 = 市值 - 成本（不受pnl_pct显示精度影响）
            if abs(h["pnl_amount"]-(h["market_value"]-h["cost"]))>0.02: bad+=1
            # pnl_pct 与盈亏方向一致（2位小数显示；pnl_pct=0 是四舍五入允许，跳过）
            if h["pnl_pct"]!=0 and (h["pnl_pct"]>0)!=(h["pnl_amount"]>0): bad+=1
            if h["is_new"]:
                nnew+=1
                if not h["buy_reason"]: bad+=1
        for s in n["sells"]:
            nsell+=1
            if s["reason"] not in ("止盈(+15%)","止损(-8%)","持有7日到期"): bad+=1
    ck(f"{g}/持仓盈亏字段自洽",bad==0,f"bad={bad} n_hold={nhold}")
    ck(f"{g}/新增持仓有买入原因",nnew>0,f"n_new={nnew}")
    ck(f"{g}/卖出有合法退出原因",nsell>0,f"n_sell={nsell}")
    # 5 股票代码6位补零
    badc=sum(1 for n in ns for h in n["holdings"] if not re.fullmatch(r"\d{6}",h["code"]))
    ck(f"{g}/代码6位格式",badc==0,f"bad={badc}")
    # 6 逐笔四指标与backtest_out.json一致（从引擎JSON的trade_base读，已由build脚本断言）
    tb=CO["pools"][g]["trade_base"]; b=BT["groups"][g]["全区间"]
    for k in ["n_signals","n_filled","avg_ret","win_rate","profit_factor"]:
        ck(f"{g}/逐笔{k}一致",close(tb[k],b[k],0.001),f"{tb[k]} vs {b[k]}")

# 7 HTML结构
ck("HTML/两条曲线", html.count("C7单池")>0 and html.count("双池")>0)
ck("HTML/分界标注","2025-12-31" in html and "2026-01-05" in html)
ck("HTML/口径说明-再投入","净值" in html and "20%" in html and "最大同时持仓" in html)
ck("HTML/不可得成本","不可得" in html and "交易成本" in html)
# hover 中文被 plotly 序列化为 \\uXXXX；用正则逐个解码合法4位hex转义后检查
import re as _re
def _dec(m):
    try: return chr(int(m.group(1),16))
    except Exception: return m.group(0)
decoded=_re.sub(r"\\u([0-9a-fA-F]{4})",_dec,html)
ck("HTML/悬停字段",("持有额" in decoded) and ("买入原因" in decoded) and
   ("当日卖出" in decoded) and ("盈亏额" in decoded),
   f"持有额={'持有额' in decoded} 买入原因={'买入原因' in decoded} 当日卖出={'当日卖出' in decoded}")
ck("HTML/内嵌plotly离线可用","plotly.js" in html and len(html)>1_000_000,f"size={len(html)}")
ck("HTML/中文字体","Microsoft YaHei" in html)

npass=sum(1 for _,ok,_ in checks if ok)
print(f"交互页自检: {npass}/{len(checks)} PASSED")
for n,ok,info in checks:
    if not ok: print("  FAIL",n,info)
print("VERIFY_INTERACTIVE="+("ALL_OK" if npass==len(checks) else "HAS_FAIL"))
