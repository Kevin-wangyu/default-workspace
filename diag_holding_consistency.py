# -*- coding: utf-8 -*-
"""全量诊断：从逐笔明细按引擎逻辑重放，扫描两类持仓一致性问题并追踪具体案例。
A类：同日持仓快照中同一 code 出现>=2次（疑似重复标的）
B类：卖出标的在上一交易日持仓快照中不存在（疑似日期错位）
分别判定是"引擎真实行为"还是"重放/渲染错误"，给出可核验证据。
"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb, pandas as pd

WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM=(WS/"research_matrix.parquet").as_posix()
CC=json.loads((WS/"portfolio_compound_out.json").read_text(encoding="utf-8"))
CFG=CC["config"]; INIT=CFG["initial_capital"]; FRAC=CFG["reinvest_frac"]/100.0
NMAX=CFG["max_concurrent_positions"]; HOLD=CFG["HOLD"]

con=duckdb.connect(); con.execute("SET threads=8")
cal=con.execute(f"SELECT DISTINCT di, trade_date FROM read_parquet('{RM}') ORDER BY di").df()
con.close()
di2date=dict(zip(cal.di.astype(int),cal.trade_date)); all_di=cal.di.astype(int).values

def exit_k(row):
    di=int(row["di"]); fp=float(row["fill_px"])
    tp=fp*(1+CFG["TP"]/100); sl=fp*(1+CFG["SL"]/100)
    for k in range(1,HOLD+1):
        if row[f"l{k}"]<=sl: return di+k,k,"SL"
        if row[f"h{k}"]>=tp: return di+k,k,"TP"
    return di+HOLD,HOLD,"TIME"

REPORT={"config":dict(CC["config"]),"pools":{}}
for tag,gname,fn in [("c7","C7单池","backtest_detail_c7.csv"),("dual","C6+C7双池","backtest_detail_dual.csv")]:
    d=pd.read_csv(WS/fn,encoding="utf-8-sig",dtype={"code":str})
    d["code"]=d["code"].str.zfill(6)
    fl=d[d["filled"].astype(bool)].copy(); fl["ret"]=fl["ret"].astype(float)
    ex=fl.apply(exit_k,axis=1,result_type="expand")
    fl["di_exit"]=ex[0].astype(int).values; fl["k_exit"]=ex[1].astype(int).values
    fl["reason"]=ex[2].values; fl["di_buy"]=fl["di"].astype(int)+1

    by_buy={}; by_exit={}
    for idx,row in fl.iterrows():
        by_buy.setdefault(int(row.di_buy),[]).append(idx)
        by_exit.setdefault(int(row.di_exit),[]).append(idx)
    for k in by_buy: by_buy[k].sort(key=lambda i:-fl.loc[i,"score"])

    active=[]; snap={}   # snap[di] = 日终持仓code列表 + 卖出code列表
    for di in all_di:
        di=int(di)
        for idx in by_buy.get(di,[]):
            if len(active)<NMAX:
                r=fl.loc[idx]
                active.append(dict(idx=idx,code=str(r["code"]),di_buy=int(r.di_buy),
                                   di_exit=int(r.di_exit),k=int(r.k_exit),reason=str(r.reason)))
        sells=[]
        open_idx={p["idx"] for p in active}
        for idx in by_exit.get(di,[]):
            if idx not in open_idx: continue
            pos=next(p for p in active if p["idx"]==idx)
            sells.append(dict(code=pos["code"],idx=idx,k=pos["k"],reason=pos["reason"],
                              di_buy=pos["di_buy"],di_exit=pos["di_exit"]))
            active.remove(pos); open_idx.discard(idx)
        snap[di]=dict(hold_codes=[p["code"] for p in active],
                      holds=[dict(p) for p in active], sells=sells)

    dias=[int(x) for x in all_di]
    # A类扫描：同日同code多次
    A=[]; A_days=0
    for di in dias:
        from collections import Counter
        c=Counter(snap[di]["hold_codes"])
        dup={code:n for code,n in c.items() if n>=2}
        if dup:
            A_days+=1
            A.append(dict(di=di,date=di2date[di],dup=dup,
                          holds=[h for h in snap[di]["holds"] if h["code"] in dup]))
    # B类扫描：卖出code不在前一日持仓快照
    B=[]; B1=[]; B2=[]
    for j,di in enumerate(dias):
        prev=snap[dias[j-1]]["hold_codes"] if j>0 else []
        for s in snap[di]["sells"]:
            if s["code"] not in prev:
                rec=dict(di=di,date=di2date[di],code=s["code"],reason=s["reason"],
                         k=s["k"],di_buy=s["di_buy"],di_exit=s["di_exit"])
                if s["k"]==1: B1.append(rec)   # 当日买当日卖（引擎真实行为）
                else: B2.append(rec)          # 异常：非k=1却前日无持仓
                B.append(rec)

    # 具体案例追踪
    def trace(code):
        rows=fl[fl["code"]==code]
        return [dict(di=int(r.di),date=di2date[int(r.di)],di_buy=int(r.di_buy),
                     di_exit=int(r.di_exit),k=int(r.k_exit),reason=str(r.reason),
                     fill=float(r.fill_px),ret=float(r.ret)) for _,r in rows.iterrows()]
    cases={
        "跨境通_002640_2024-09-13": trace("002640"),
        "阳普医疗_300030_2024-09-13": trace("300030"),
    }
    REPORT["pools"][tag]=dict(name=gname,n_days=len(dias),
        A=dict(days=A_days,items=A[:8],total_items=len(A)),
        B=dict(total=len(B),B1_same_day_buy_sell=len(B1),B2_anomaly=len(B2),
               B2_items=B2[:10],B1_items=B1[:6]),
        cases=cases)
    print(f"[{gname}] 扫描日期={len(dias)}  A类重复标的天数={A_days}  "
          f"B类卖出无前日持仓={len(B)} (当日买当日卖k=1:{len(B1)}, 异常:{len(B2)})",flush=True)

(WS/"diag_holding_out.json").write_text(json.dumps(REPORT,ensure_ascii=False,indent=2),encoding="utf-8")
print("WROTE diag_holding_out.json",flush=True)
