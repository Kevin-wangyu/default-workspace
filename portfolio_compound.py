# -*- coding: utf-8 -*-
"""复利组合层回测：显式定义"盈利再投入"规则后重算账户账本。

【T+1 修正】退出检查起点 k=1 -> k=2（买入当日 T+1 不可卖，最早 T+2 卖出）。
  与 backtest_strategy.py 的 T1_FIRST_EXIT_D=1 完全对齐；重算后 assert 与明细 reason/k_exit 一致。
【两套口径】环境变量 BT_SUFFIX=""（正常/全市场）或 "_main"（仅主板 board=='main'）。
"""
from __future__ import annotations
import json, time, os
from pathlib import Path
import duckdb, numpy as np, pandas as pd

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM = (WS/"research_matrix.parquet").as_posix()
SUFFIX = os.environ.get("BT_SUFFIX", "")

CONFIG = dict(
    initial_capital=20000.0,
    reinvest_rule="fixed_fraction_of_equity_at_signal_close",
    reinvest_frac=20.0,
    trigger="per_buy_signal_day",
    max_position_pct=20.0,
    max_concurrent_positions=5,
    exit_release="next_day",
    ranking="rule1.1_score_desc",
    compounding=True,
    mark_to_market=True,
    risk_free_rate=0.0,
    TP=15.0, SL=-8.0, HOLD=7,
    t1_first_exit_k=2,   # T+1：买入当日(k=1)不可卖，最早 k=2(T+2)卖出
    board_mode="main" if SUFFIX=="_main" else "normal",
    alloc_mode_note="每笔投入额随账户净值按比例放大/缩小；固定4000不复利作为对照",
)
INIT=CONFIG["initial_capital"]; FRAC=CONFIG["reinvest_frac"]/100.0
NMAX=CONFIG["max_concurrent_positions"]; HOLD=CONFIG["HOLD"]
T1K=CONFIG["t1_first_exit_k"]

def fmt(v,n=2):
    return round(float(v),n) if v is not None and not (isinstance(v,float) and np.isnan(v)) else None

con=duckdb.connect(); con.execute("SET threads=8")
cal=con.execute(f"SELECT DISTINCT di, trade_date FROM read_parquet('{RM}') ORDER BY di").df()
con.close()
di2date=dict(zip(cal.di.astype(int),cal.trade_date)); all_di=cal.di.astype(int).values

POOLS=[("C7单池","c7"),("C6+C7双池","dual")]

def recompute_exit_di(row):
    """复现回测退出循环（T+1：k=1 买入当日不可卖，从 k=2 起；同日先止损后止盈）。"""
    di=int(row["di"]); fp=float(row["fill_px"])
    tp=fp*(1+CONFIG["TP"]/100); sl=fp*(1+CONFIG["SL"]/100)
    for k in range(T1K,HOLD+1):
        if row[f"l{k}"]<=sl: return di+k,k,"SL"
        if row[f"h{k}"]>=tp: return di+k,k,"TP"
    return di+HOLD,HOLD,"TIME"

results={"config":CONFIG,"pools":{}}

for gname,tag in POOLS:
    t0=time.time()
    fn=f"backtest_detail_{tag}{SUFFIX}.csv"
    d=pd.read_csv(WS/fn,encoding="utf-8-sig")
    fl=d[d["filled"].astype(bool)].copy(); fl["ret"]=fl["ret"].astype(float)
    base=dict(n_signals=len(d),n_filled=len(fl),
              fill_rate=fmt(len(fl)/len(d)*100,2),avg_ret=fmt(fl.ret.mean(),4),
              win_rate=fmt((fl.ret>0).mean()*100,2),
              profit_factor=fmt(fl.ret[fl.ret>0].sum()/abs(fl.ret[fl.ret<0].sum()),3))
    ex=fl.apply(recompute_exit_di,axis=1,result_type="expand")
    fl["di_exit"]=ex[0].astype(int).values; fl["k_exit"]=ex[1].astype(int).values
    fl["reason_recalc"]=ex[2].values; fl["di_buy"]=fl["di"].astype(int)+1
    assert (fl["reason_recalc"]!=fl["reason"]).sum()==0, "退出原因重算不一致"
    if "k_exit" in d.columns:
        assert (fl["k_exit"]!=d.loc[fl.index,"k_exit"]).sum()==0, "k_exit 与明细不一致"
    assert (fl.di_exit>fl.di).all() and (fl.di_exit<=fl.di+HOLD).all()
    assert (fl.k_exit>=T1K).all(), "存在违反T+1的当日回转"

    by_buy={}; by_exit={}
    for idx,row in fl.iterrows():
        by_buy.setdefault(int(row.di_buy),[]).append(idx)
        by_exit.setdefault(int(row.di_exit),[]).append(idx)
    for k in by_buy: by_buy[k].sort(key=lambda i:-fl.loc[i,"score"])

    active=[]; realized=0.0; equity={}; rejected=0; opened=[]; alloc_list=[]
    for di in all_di:
        di=int(di)
        eq_prev=equity[di-1] if (di-1) in equity else INIT
        for idx in by_buy.get(di,[]):
            if len(active)<NMAX:
                alloc=eq_prev*FRAC; row=fl.loc[idx]
                active.append(dict(idx=idx,di=int(row.di),di_buy=int(row.di_buy),
                                   di_exit=int(row.di_exit),k=int(row.k_exit),
                                   fp=float(row.fill_px),ret=float(row.ret),alloc=alloc))
                alloc_list.append((idx,alloc)); opened.append(idx)
            else:
                rejected+=1
        open_idx={p["idx"] for p in active}
        for idx in by_exit.get(di,[]):
            if idx not in open_idx: continue
            pos=next(p for p in active if p["idx"]==idx)
            realized+=pos["alloc"]*pos["ret"]/100.0
            active.remove(pos); open_idx.discard(idx)
        fp_pnl=sum(p["alloc"]*(float(fl.loc[p["idx"],f"c{di-p['di']}"])/p["fp"]-1.0)
                   for p in active if 1<=di-p["di"]<=10)
        equity[di]=INIT+realized+fp_pnl

    eq=pd.Series(equity).sort_index()
    eq_dates=pd.Series([di2date[x] for x in eq.index],index=eq.index)
    dr=eq.pct_change().dropna()
    final=float(eq.iloc[-1]); cum=(final-INIT)/INIT*100
    years=(pd.Timestamp(eq_dates.iloc[-1])-pd.Timestamp(eq_dates.iloc[0])).days/365.25
    cagr=((final/INIT)**(1/years)-1)*100 if years>0 and final>0 else None
    mdd=((eq.cummax()-eq)/eq.cummax()).max()*100
    sharpe=(dr.mean()/dr.std(ddof=1))*np.sqrt(252) if dr.std()>0 else None
    cut=int(cal[cal.trade_date=="2025-12-31"].di.values[0])

    al=pd.DataFrame(alloc_list,columns=["idx","alloc"]).set_index("idx")["alloc"]
    op=fl.loc[opened]
    port_base=dict(n_opened=len(opened),n_rejected_slot=rejected,
                   avg_ret_opened=fmt(op.ret.mean(),4),
                   win_rate_opened=fmt((op.ret>0).mean()*100,2),
                   alloc_min=fmt(al.min(),2),alloc_max=fmt(al.max(),2),
                   alloc_mean=fmt(al.mean(),2),
                   capital_deployed_sum=fmt(al.sum(),2),pnl_total=fmt(realized,2))
    results["pools"][gname]=dict(
        trade_base=base,port_base=port_base,
        portfolio=dict(initial=INIT,final=fmt(final,2),cum_return_pct=fmt(cum,4),
                       cagr_pct=fmt(cagr,4),max_drawdown_pct=fmt(mdd,4),
                       sharpe=fmt(sharpe,4),years=fmt(years,2),n_days=len(eq),
                       date_start=str(eq_dates.iloc[0]),date_end=str(eq_dates.iloc[-1]),
                       split_date="2025-12-31 -> 2026-01-05",cut_di=cut,
                       equity_train_end=fmt(float(eq[eq.index<=cut].iloc[-1]),2),
                       equity_full_end=fmt(final,2)),
        unavailable=dict(items=["组合层真实交易成本(方案仅给0.1~0.15%费率区间上限，无逐笔计费明细)"],
                         reason="成本为区间上限非精确费率，无法由逐笔收益%唯一推导，不以替代值填充"))
    pd.DataFrame(dict(di=eq.index,trade_date=[di2date[x] for x in eq.index],
                      equity=eq.values,split=["train" if x<=cut else "oos" for x in eq.index])
        ).to_csv(WS/f"portfolio_compound_equity_{tag}{SUFFIX}.csv",index=False,encoding="utf-8-sig")
    print(f"=== {gname} [{CONFIG['board_mode']}] (复利) ===",flush=True)
    print(f" 逐笔层: 信号{base['n_signals']} 成交{base['n_filled']} 期望{base['avg_ret']}% "
          f"胜率{base['win_rate']}% PF{base['profit_factor']}",flush=True)
    print(f" 投入额 min{port_base['alloc_min']} max{port_base['alloc_max']} "
          f"mean{port_base['alloc_mean']} 开仓{port_base['n_opened']} 拒绝{port_base['n_rejected_slot']}",flush=True)
    print(f" 复利组合: 终值{final:.2f} 累计{cum:.4f}% 年化{cagr:.4f}% "
          f"回撤{mdd:.4f}% 夏普{sharpe:.4f} sec={time.time()-t0:.1f}",flush=True)

(WS/f"portfolio_compound_out{SUFFIX}.json").write_text(
    json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
print(f"\nDONE -> portfolio_compound_out{SUFFIX}.json",flush=True)
