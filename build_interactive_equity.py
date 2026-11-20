# -*- coding: utf-8 -*-
"""忠实重放复利撮合引擎，逐日捕获持仓/新增/卖出快照，产出交互页节点JSON。
关键约束：重放的逐日净值必须与 portfolio_compound_equity_*.csv 逐日 max_abs_diff==0；
逐笔层四指标与 backtest_out.json 逐项一致；所有持仓/盈亏字段来自逐笔明细，零手工填写。
"""
from __future__ import annotations
import json, os
from pathlib import Path
import duckdb, numpy as np, pandas as pd

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM = (WS/"research_matrix.parquet").as_posix()
SUFFIX = os.environ.get("BT_SUFFIX", "")
CC = json.loads((WS/f"portfolio_compound_out{SUFFIX}.json").read_text(encoding="utf-8"))
BT = json.loads((WS/f"backtest_out{SUFFIX}.json").read_text(encoding="utf-8"))
CFG = CC["config"]; INIT=CFG["initial_capital"]; FRAC=CFG["reinvest_frac"]/100.0
HOLD=CFG["HOLD"]; NMAX=CFG["max_concurrent_positions"]
T1K=CFG.get("t1_first_exit_k", 2)   # T+1：买入当日(k=1)不可卖，最早 k=2

con=duckdb.connect(); con.execute("SET threads=8")
cal=con.execute(f"SELECT DISTINCT di, trade_date FROM read_parquet('{RM}') ORDER BY di").df()
con.close()
di2date=dict(zip(cal.di.astype(int),cal.trade_date)); all_di=cal.di.astype(int).values
cut=int(cal[cal.trade_date=="2025-12-31"].di.values[0])

REASON_CN={"TP":"止盈(+15%)","SL":"止损(-8%)","TIME":"持有7日到期"}

def exit_k(row):
    """复现回测退出循环：T+1 买入当日(k=1)不可卖，从 k=2 起；同日先止损后止盈，第7日收盘平仓。"""
    di=int(row["di"]); fp=float(row["fill_px"])
    tp=fp*(1+CFG["TP"]/100); sl=fp*(1+CFG["SL"]/100)
    for k in range(T1K,HOLD+1):
        if row[f"l{k}"]<=sl: return di+k,k,"SL"
        if row[f"h{k}"]>=tp: return di+k,k,"TP"
    return di+HOLD,HOLD,"TIME"

def buy_reason(row):
    """买入原因全由逐笔明细字段推导，不手工填写。"""
    src = "C7" if (int(row["is_c7"])==1) else "C6"
    parts=[f"{src}信号"]
    if int(row["is_c6"])==1 and int(row["is_c7"])==1: parts.append("C6∩C7双命中")
    st=int(row["streak7"]) if int(row["is_c7"])==1 else int(row["streak6"])
    if st>=2: parts.append(f"连池{st}日(规则5.1优先)")
    parts.append(f"综合分{float(row['score']):.3f}排序入选")
    parts.append("T收盘×0.95限价成交(规则2.1)")
    return "；".join(parts)

POOLS=[("c7","C7单池",f"backtest_detail_c7{SUFFIX}.csv"),
       ("dual","C6+C7双池",f"backtest_detail_dual{SUFFIX}.csv")]
OUT={"config":dict(CC["config"]),"split":{"train_last":"2025-12-31","oos_first":"2026-01-05","cut_di":cut},
     "board_mode":CFG.get("board_mode","normal"),"pools":{}}

for tag,gname,fn in POOLS:
    d=pd.read_csv(WS/fn,encoding="utf-8-sig",dtype={"code":str})
    d["code"]=d["code"].str.zfill(6)  # 股票代码补前导零（002902 等）
    fl=d[d["filled"].astype(bool)].copy(); fl["ret"]=fl["ret"].astype(float)
    # 逐笔四指标校验（与backtest_out.json一致）
    b=BT["groups"][gname]["全区间"]
    assert len(d)==b["n_signals"] and len(fl)==b["n_filled"]
    assert abs(fl.ret.mean()-b["avg_ret"])<1e-4
    assert abs((fl.ret>0).mean()*100-b["win_rate"])<0.01
    ex=fl.apply(exit_k,axis=1,result_type="expand")
    fl["di_exit"]=ex[0].astype(int).values; fl["k_exit"]=ex[1].astype(int).values
    fl["reason_recalc"]=ex[2].values; fl["di_buy"]=fl["di"].astype(int)+1
    assert (fl["reason_recalc"]!=fl["reason"]).sum()==0
    assert (fl["k_exit"]>=T1K).all(), "存在违反T+1的当日回转"
    if "k_exit" in d.columns:
        assert (fl["k_exit"]!=d.loc[fl.index,"k_exit"]).sum()==0, "k_exit与明细不一致"

    by_buy={}; by_exit={}
    for idx,row in fl.iterrows():
        by_buy.setdefault(int(row.di_buy),[]).append(idx)
        by_exit.setdefault(int(row.di_exit),[]).append(idx)
    for k in by_buy: by_buy[k].sort(key=lambda i:-fl.loc[i,"score"])

    # 与引擎一致的净值重放 + 逐日持仓快照（修复：同标的聚合为唯一行 + 当日回转可追溯）
    # 注意：净值计算(realized/float_pnl)完全沿用引擎逐笔求和，聚合只改变 holdings 呈现结构，
    #       不改净值、不改逐笔、不改引擎输出。
    active=[]; realized=0.0; equity={}; nodes=[]
    for di in all_di:
        di=int(di); eq_prev=equity.get(di-1,INIT)
        new_buys=[]; sells=[]; intraday=[]
        # 1) 开新仓（投入=信号日收盘净值×20%）
        for idx in by_buy.get(di,[]):
            if len(active)<NMAX:
                alloc=eq_prev*FRAC; row=fl.loc[idx]
                pos=dict(idx=idx,di=int(row.di),di_buy=int(row.di_buy),
                         di_exit=int(row.di_exit),fp=float(row.fill_px),
                         ret=float(row.ret),alloc=alloc,code=str(row["code"]),
                         name=str(row["name"]),reason_buy=buy_reason(row))
                active.append(pos); new_buys.append(idx)
        # 2) 收盘结算退出
        open_idx={p["idx"] for p in active}
        for idx in by_exit.get(di,[]):
            if idx not in open_idx: continue
            pos=next(p for p in active if p["idx"]==idx)
            realized+=pos["alloc"]*pos["ret"]/100.0
            reason=fl.loc[idx,"reason"]
            same_day=(pos["di_buy"]==di)
            sells.append(dict(code=pos["code"],name=pos["name"],
                              pnl_amount=round(pos["alloc"]*pos["ret"]/100.0,2),
                              pnl_pct=round(float(pos["ret"]),2),
                              reason=REASON_CN.get(str(reason),str(reason)),
                              held_days=int(pos["di_exit"]-pos["di"]),
                              is_same_day=same_day,
                              entry_date=di2date[pos["di_buy"]],
                              buy_reason=pos["reason_buy"]))
            if same_day:
                # 当日买当日卖：引擎真实行为，单独记录使卖出可追溯到当日建仓
                intraday.append(dict(code=pos["code"],name=pos["name"],
                                     cost=round(pos["alloc"],2),
                                     market_value=round(pos["alloc"]*(1+pos["ret"]/100),2),
                                     pnl_amount=round(pos["alloc"]*pos["ret"]/100,2),
                                     pnl_pct=round(float(pos["ret"]),2),
                                     reason=REASON_CN.get(str(reason),str(reason)),
                                     buy_reason=pos["reason_buy"]))
            active.remove(pos); open_idx.discard(idx)
        # 3) mark-to-market + 持仓快照（同 code 聚合为唯一行，附笔数与各笔idx）
        agg={}; float_pnl=0.0
        for p in active:
            jrel=di-p["di"]
            if 1<=jrel<=10:
                px=float(fl.loc[p["idx"],f"c{jrel}"]); chg=px/p["fp"]-1.0
                float_pnl+=p["alloc"]*chg
                c=p["code"]
                if c not in agg:
                    agg[c]=dict(code=c,name=p["name"],cost=0.0,market_value=0.0,
                                pnl_amount=0.0,n_lots=0,lots=[],is_new=False,
                                buy_reason="",held_days=jrel)
                a=agg[c]
                a["cost"]+=p["alloc"]; a["market_value"]+=p["alloc"]*(1+chg)
                a["pnl_amount"]+=p["alloc"]*chg
                a["n_lots"]+=1; a["lots"].append(int(p["idx"]))
                if p["idx"] in new_buys:
                    a["is_new"]=True; a["buy_reason"]=p["reason_buy"]
        holdings=[]
        for a in agg.values():
            a["cost"]=round(a["cost"],2); a["market_value"]=round(a["market_value"],2)
            a["pnl_amount"]=round(a["pnl_amount"],2)
            a["pnl_pct"]=round(a["pnl_amount"]/a["cost"]*100,2) if a["cost"] else 0.0
            holdings.append(a)
        eq=INIT+realized+float_pnl; equity[di]=eq
        nodes.append(dict(di=di,date=di2date[di],split="train" if di<=cut else "oos",
                          equity=round(eq,2),
                          ret_pct=round((eq/INIT-1)*100,4),
                          holdings=holdings,sells=sells,intraday_closed=intraday,
                          n_hold=len(holdings)))

    # 与引擎净值CSV逐日比对：max_abs_diff 必须 == 0
    ref=pd.read_csv(WS/f"portfolio_compound_equity_{tag}{SUFFIX}.csv",encoding="utf-8-sig")
    got=pd.DataFrame([{"di":n["di"],"equity":n["equity"]} for n in nodes])
    mg=got.merge(ref[["di","equity"]],on="di",suffixes=("_replay","_engine"))
    maxdiff=float((mg.equity_replay-mg.equity_engine).abs().max())
    ndiff=int((mg.equity_replay.round(2)!=mg.equity_engine.round(2)).sum())
    print(f"[{gname}] 逐日净值对齐: n={len(mg)} max_abs_diff={maxdiff:.6f} n_diff(2位)={ndiff}",flush=True)
    assert maxdiff<0.011 and ndiff==0, f"重放与引擎净值不一致 {maxdiff}"

    OUT["pools"][tag]=dict(name=gname,n_nodes=len(nodes),
                           final=round(nodes[-1]["equity"],2),
                           max_equity_diff_vs_engine=round(maxdiff,6),
                           n_holdings_max=max(n["n_hold"] for n in nodes),
                           nodes=nodes)

outname=f"interactive_equity_data{SUFFIX}.json"
(WS/outname).write_text(json.dumps(OUT,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
sz=(WS/outname).stat().st_size
print(f"DONE -> interactive_equity_data.json ({sz:,} bytes)",flush=True)
print("NODES c7=%d dual=%d"%(OUT["pools"]["c7"]["n_nodes"],OUT["pools"]["dual"]["n_nodes"]),flush=True)
