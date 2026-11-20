# -*- coding: utf-8 -*-
"""复利组合层回测：显式定义"盈利再投入"规则后重算账户账本。
再投入规则（fixed-fraction compounding，逐条写进 CONFIG）：
  - 每笔投入额 = 信号日 T 收盘账户净值 × REINVEST_FRAC(20%)  -> 动态单票上限
  - 触发时点 = 每个买入信号日（信号日 T 收盘定比，T+1 实际开仓）
  - 账户净值 = 初始资金 + Σ已实现(投入额×ret%) + Σ持仓浮盈(投入额×(现价/买入价-1))
  - 不复利对照 = portfolio_backtest.py（固定4000/笔）保留为对照，不覆盖
逐笔层规则（买入-5%/止盈+15%/止损-8%/持有7日/排序/连池）完全沿用 backtest_strategy.py，
本脚本只在资金撮合层把"固定金额"换成"净值定比"，逐笔成交/收益%不重算、不调参。
"""
from __future__ import annotations
import json, time
from pathlib import Path
import duckdb, numpy as np, pandas as pd

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM = (WS/"research_matrix.parquet").as_posix()

# ============ 资金与再投入规则（显式定义，禁止隐含假设）============
CONFIG = dict(
    initial_capital=20000.0,          # 初始资金
    reinvest_rule="fixed_fraction_of_equity_at_signal_close",  # 再投入规则：按信号日收盘净值定比
    reinvest_frac=20.0,               # 每笔投入 = 信号日T收盘净值 × 20%（=动态单票上限）
    trigger="per_buy_signal_day",     # 触发：每个买入信号日（不做定期再平衡）
    max_position_pct=20.0,            # 单票上限 = 净值20%（与每笔投入同口径）
    max_concurrent_positions=5,       # 最大同时持仓5只（名义满仓≈100%净值）
    exit_release="next_day",          # 当日退出槽位次日可用
    ranking="rule1.1_score_desc",     # 同日多信号综合分降序竞争槽位
    compounding=True,                 # 复利（对比上一轮 False）
    mark_to_market=True,
    risk_free_rate=0.0,
    TP=15.0, SL=-8.0, HOLD=7,
    alloc_mode_note="每笔投入额随账户净值按比例放大/缩小；上一轮固定4000不复利作为对照",
)
INIT=CONFIG["initial_capital"]; FRAC=CONFIG["reinvest_frac"]/100.0
NMAX=CONFIG["max_concurrent_positions"]; HOLD=CONFIG["HOLD"]

def fmt(v,n=2):
    return round(float(v),n) if v is not None and not (isinstance(v,float) and np.isnan(v)) else None

con=duckdb.connect(); con.execute("SET threads=8")
cal=con.execute(f"SELECT DISTINCT di, trade_date FROM read_parquet('{RM}') ORDER BY di").df()
con.close()
di2date=dict(zip(cal.di.astype(int),cal.trade_date)); all_di=cal.di.astype(int).values

POOLS=[("C7单池","backtest_detail_c7.csv"),("C6+C7双池","backtest_detail_dual.csv")]

def recompute_exit_di(row):
    """完整复现原回测退出循环（同日先止损后止盈，第7日收盘平仓）。"""
    di=int(row["di"]); fp=float(row["fill_px"])
    tp=fp*(1+CONFIG["TP"]/100); sl=fp*(1+CONFIG["SL"]/100)
    for k in range(1,HOLD+1):
        if row[f"l{k}"]<=sl: return di+k,k,"SL"
        if row[f"h{k}"]>=tp: return di+k,k,"TP"
    return di+HOLD,HOLD,"TIME"

results={"config":CONFIG,"pools":{}}

for gname,fn in POOLS:
    t0=time.time()
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
    assert (fl.di_exit>fl.di).all() and (fl.di_exit<=fl.di+HOLD).all()

    by_buy={}; by_exit={}
    for idx,row in fl.iterrows():
        by_buy.setdefault(int(row.di_buy),[]).append(idx)
        by_exit.setdefault(int(row.di_exit),[]).append(idx)
    for k in by_buy: by_buy[k].sort(key=lambda i:-fl.loc[i,"score"])

    active=[]; realized=0.0; equity={}; rejected=0; opened=[]
    alloc_list=[]   # 每笔实际投入额（复利下逐笔不同）
    for di in all_di:
        di=int(di)
        eq_prev=equity[di-1] if (di-1) in equity else INIT   # 信号日T收盘净值（=日前一交易收盘）
        # 1) 开新仓：投入 = 信号日收盘净值 × 20%（动态单票上限）
        for idx in by_buy.get(di,[]):
            if len(active)<NMAX:
                alloc=eq_prev*FRAC
                row=fl.loc[idx]
                active.append(dict(idx=idx,di=int(row.di),di_buy=int(row.di_buy),
                                   di_exit=int(row.di_exit),k=int(row.k_exit),
                                   fp=float(row.fill_px),ret=float(row.ret),alloc=alloc))
                alloc_list.append((idx,alloc)); opened.append(idx)
            else:
                rejected+=1
        # 2) 收盘结算退出
        open_idx={p["idx"] for p in active}
        for idx in by_exit.get(di,[]):
            if idx not in open_idx: continue
            pos=next(p for p in active if p["idx"]==idx)
            realized+=pos["alloc"]*pos["ret"]/100.0
            active.remove(pos); open_idx.discard(idx)
        # 3) mark-to-market
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
                   capital_deployed_sum=fmt(al.sum(),2),
                   pnl_total=fmt(realized,2))
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
    tag="c7" if gname=="C7单池" else "dual"
    pd.DataFrame(dict(di=eq.index,trade_date=[di2date[x] for x in eq.index],
                      equity=eq.values,split=["train" if x<=cut else "oos" for x in eq.index])
        ).to_csv(WS/f"portfolio_compound_equity_{tag}.csv",index=False,encoding="utf-8-sig")
    print(f"=== {gname} (复利) ===",flush=True)
    print(f" 逐笔层(不变): 信号{base['n_signals']} 成交{base['n_filled']} 期望{base['avg_ret']}% "
          f"胜率{base['win_rate']}% PF{base['profit_factor']}",flush=True)
    print(f" 投入额 min{port_base['alloc_min']} max{port_base['alloc_max']} "
          f"mean{port_base['alloc_mean']} 开仓{port_base['n_opened']} 拒绝{port_base['n_rejected_slot']}",flush=True)
    print(f" 复利组合: 终值{final:.2f} 累计{cum:.4f}% 等效年化{cagr:.4f}% "
          f"回撤{mdd:.4f}% 夏普{sharpe:.4f} sec={time.time()-t0:.1f}",flush=True)

(WS/"portfolio_compound_out.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
print("\nDONE -> portfolio_compound_out.json",flush=True)
