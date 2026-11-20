# -*- coding: utf-8 -*-
"""组合层回测：在明确资金三要素下，把逐笔明细撮合成账户净值曲线与组合指标。
逐笔层面规则完全沿用既有 backtest_strategy.py（不改成交/止盈/止损/持有/排序/连池），
本脚本只在"资金与仓位约束"层增加：槽位竞争、开仓投入、逐日 mark-to-market。
组合层所有输入均来自逐笔明细 CSV + research_matrix 交易日历，可唯一推导。
"""
from __future__ import annotations
import json, time, os
from pathlib import Path
import duckdb, numpy as np, pandas as pd

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM = (WS/"research_matrix.parquet").as_posix()
SUFFIX = os.environ.get("BT_SUFFIX", "")

# ============ 资金与仓位三要素（显式定义，禁止隐含假设）============
CONFIG = dict(
    initial_capital=20000.0,      # 初始资金
    alloc_mode="equal_fixed",     # 资金分配：等权固定金额
    alloc_per_trade=4000.0,       # 每笔投入 = 初始资金 × 20% = 4000元，固定不复利
    max_position_pct=20.0,        # 单票仓位上限：占初始资金 20%
    max_concurrent_positions=5,   # 最大同时持仓数
    exit_release="next_day",      # 当日退出释放的槽位次日才可用（保守，避免同日先卖后买）
    ranking="rule1.1_score_desc", # 同日多信号竞争槽位：按规则1.1综合分降序
    compounding=False,            # 不复利（固定金额线性口径）
    mark_to_market=True,          # 净值含持仓浮动盈亏
    risk_free_rate=0.0,           # 夏普无风险利率=0（披露）
    TP=15.0, SL=-8.0, HOLD=7,     # 与逐笔层一致的退出常量（用于重算退出日）
    t1_first_exit_k=2,            # T+1：买入当日(k=1)不可卖，最早 k=2(T+2)卖出
    board_mode="main" if SUFFIX=="_main" else "normal",
)
INIT = CONFIG["initial_capital"]; ALLOC = CONFIG["alloc_per_trade"]
NMAX = CONFIG["max_concurrent_positions"]; HOLD = CONFIG["HOLD"]
T1K = CONFIG["t1_first_exit_k"]

def fmt(v,n=2):
    return round(float(v),n) if v is not None and not (isinstance(v,float) and np.isnan(v)) else None

# 交易日历：di -> trade_date（全部交易日，用于逐日净值对齐）
con = duckdb.connect(); con.execute("SET threads=8")
cal = con.execute(f"SELECT DISTINCT di, trade_date FROM read_parquet('{RM}') ORDER BY di").df()
con.close()
di2date = dict(zip(cal.di.astype(int), cal.trade_date))
all_di = cal.di.astype(int).values

POOLS = [("C7单池",f"backtest_detail_c7{SUFFIX}.csv"),("C6+C7双池",f"backtest_detail_dual{SUFFIX}.csv")]

def recompute_exit_di(row):
    """复现回测退出循环：T+1 买入当日(k=1)不可卖，从 k=2 起；同日先止损后止盈，第7日收盘平仓。"""
    di = int(row["di"]); fp = float(row["fill_px"])
    tp_thr = fp*(1+CONFIG["TP"]/100); sl_thr = fp*(1+CONFIG["SL"]/100)
    for k in range(T1K, HOLD+1):
        if row[f"l{k}"] <= sl_thr:   # 同日先止损
            return di+k, k, "SL"
        if row[f"h{k}"] >= tp_thr:
            return di+k, k, "TP"
    return di+HOLD, HOLD, "TIME"

results = {"config": CONFIG, "pools": {}}

for gname, fn in POOLS:
    t0=time.time()
    d = pd.read_csv(WS/fn, encoding="utf-8-sig")
    # 逐笔层统计（全部成交信号，与既有口径一致，作为"信号质量"基准）
    fl = d[d["filled"].astype(bool)].copy()
    fl["ret"] = fl["ret"].astype(float)
    base = dict(
        n_signals=len(d), n_filled=len(fl),
        fill_rate=fmt(len(fl)/len(d)*100,2),
        avg_ret=fmt(fl.ret.mean(),4),
        win_rate=fmt((fl.ret>0).mean()*100,2),
        profit_factor=fmt(fl.ret[fl.ret>0].sum()/abs(fl.ret[fl.ret<0].sum()),3),
    )
    # 重算退出日
    ex = fl.apply(recompute_exit_di, axis=1, result_type="expand")
    fl["di_exit"] = ex[0].astype(int).values; fl["k_exit"] = ex[1].astype(int).values
    fl["reason_recalc"] = ex[2].values
    fl["di_buy"] = fl["di"].astype(int)+1
    # 校验：重算退出原因与逐笔明细一致（组合层时间锚点可信的根基）
    mismatch = int((fl["reason_recalc"]!=fl["reason"]).sum())
    assert mismatch==0, f"退出原因重算不一致 {mismatch} 笔"
    assert (fl.di_exit>fl.di).all() and (fl.di_exit<=fl.di+HOLD).all(), "退出日越界"
    assert (fl.ret[fl.reason=="TP"]==CONFIG["TP"]).all(), "TP收益不符"
    assert (np.isclose(fl.ret[fl.reason=="SL"],CONFIG["SL"])).all(), "SL收益不符"

    # 逐日撮合：按 di 推进
    active = []          # 当前持仓：[dict(p=头寸行, alloc, realized_flag)]
    by_buy = {}          # di_buy -> [行索引]（按score降序）
    by_exit = {}         # di_exit -> [行索引]
    for idx,row in fl.iterrows():
        by_buy.setdefault(int(row.di_buy),[]).append(idx)
        by_exit.setdefault(int(row.di_exit),[]).append(idx)
    for k in by_buy: by_buy[k].sort(key=lambda i: -fl.loc[i,"score"])  # 规则1.1综合分降序

    equity = {}; realized = 0.0; rejected_slot=0; opened=[]
    for di in all_di:
        di = int(di)
        # 1) 先开新仓（基于当前 active 槽位；当日退出尚未释放 -> 次日可用）
        for idx in by_buy.get(di,[]):
            if len(active) < NMAX:
                row = fl.loc[idx]
                active.append(dict(idx=idx, di=int(row.di), di_buy=int(row.di_buy),
                                   di_exit=int(row.di_exit), k=int(row.k_exit),
                                   fp=float(row.fill_px), ret=float(row.ret),
                                   alloc=ALLOC))
                opened.append(idx)
            else:
                rejected_slot += 1
        # 2) 收盘结算当日退出（实现盈亏，释放槽位）
        #    只结算实际已开仓的头寸；被槽位拒绝的信号从未开仓，跳过
        open_idx = {p["idx"] for p in active}
        for idx in by_exit.get(di,[]):
            if idx not in open_idx:
                continue
            pos = next(p for p in active if p["idx"]==idx)
            realized += pos["alloc"]*pos["ret"]/100.0
            active.remove(pos)
            open_idx.discard(idx)
        # 3) mark-to-market 净值：初始 + 已实现 + 持仓浮盈
        float_pnl = 0.0
        for p in active:
            jrel = di - p["di"]
            if 1 <= jrel <= 10:
                px = float(fl.loc[p["idx"], f"c{jrel}"])
                float_pnl += p["alloc"]*(px/p["fp"]-1.0)
        equity[di] = INIT + realized + float_pnl

    # 净值序列
    eq = pd.Series(equity).sort_index()
    eq_dates = pd.Series([di2date[d] for d in eq.index], index=eq.index)
    daily_ret = eq.pct_change().dropna()
    final = float(eq.iloc[-1]); cum = (final-INIT)/INIT*100
    years = (pd.Timestamp(eq_dates.iloc[-1])-pd.Timestamp(eq_dates.iloc[0])).days/365.25
    cagr = ((final/INIT)**(1/years)-1)*100 if years>0 and final>0 else None
    peak = eq.cummax(); mdd = ((peak-eq)/peak).max()*100
    sharpe = (daily_ret.mean()/daily_ret.std(ddof=1))*np.sqrt(252) if daily_ret.std()>0 else None
    # 分段净值（用已实现+浮动在同一曲线上按日期切分）
    split_di = cal[(cal.trade_date=="2025-12-31")].di.values
    cut = int(split_di[0]) if len(split_di) else 464

    # 组合层实际开仓子集统计（槽位约束下的逐笔期望，可能与全样本不同 -> 明确披露）
    op = fl.loc[opened]
    port_base = dict(
        n_opened=len(opened), n_rejected_slot=rejected_slot,
        avg_ret_opened=fmt(op.ret.mean(),4),
        win_rate_opened=fmt((op.ret>0).mean()*100,2),
        capital_deployed=ALLOC*len(opened),
        pnl_total=fmt(realized,2),
    )
    seg_idx = np.array([d for d in eq.index])
    results["pools"][gname] = dict(
        trade_base=base, port_base=port_base,
        portfolio=dict(
            initial=INIT, final=fmt(final,2), cum_return_pct=fmt(cum,4),
            cagr_pct=fmt(cagr,4), max_drawdown_pct=fmt(mdd,4),
            sharpe=fmt(sharpe,4), years=fmt(years,2),
            n_days=len(eq), date_start=str(eq_dates.iloc[0]), date_end=str(eq_dates.iloc[-1]),
            split_date="2025-12-31 -> 2026-01-05", cut_di=cut,
            equity_train_end=fmt(float(eq[eq.index<=cut].iloc[-1]),2),
            equity_full_end=fmt(final,2),
        ),
        unavailable=dict(
            items=["组合层真实交易成本(需逐笔成交价×数量×费率明细，方案仅给0.1~0.15%上限)"],
            reason="成本上限是费率区间非精确费率；组合层净利润须按每笔实际成交额计，无法由逐笔收益%唯一推导"
        ),
    )
    # 保存逐日净值序列（两条曲线按 di 对齐）
    out = pd.DataFrame(dict(di=eq.index, trade_date=[di2date[d] for d in eq.index],
                            equity=eq.values,
                            split=["train" if d<=cut else "oos" for d in eq.index]))
    out.to_csv(WS/f"portfolio_equity_{'c7' if gname=='C7单池' else 'dual'}{SUFFIX}.csv",index=False,encoding="utf-8-sig")
    print(f"=== {gname} ===", flush=True)
    print(f" 逐笔层(不变): 信号{base['n_signals']} 成交{base['n_filled']} 期望{base['avg_ret']}% "
          f"胜率{base['win_rate']}% PF{base['profit_factor']}", flush=True)
    print(f" 组合层开仓{port_base['n_opened']} 槽位拒绝{port_base['n_rejected_slot']} "
          f"开仓子集期望{port_base['avg_ret_opened']}%", flush=True)
    cagr_s = f"{cagr:.4f}%" if cagr is not None else "不可得(终值≤0)"
    sharpe_s = f"{sharpe:.4f}" if sharpe is not None else "不可得"
    print(f" 组合指标: 终值{final:.2f} 累计{cum:.4f}% 年化{cagr_s} "
          f"最大回撤{mdd:.4f}% 夏普{sharpe_s} years={years:.2f} sec={time.time()-t0:.1f}", flush=True)

(WS/f"portfolio_out{SUFFIX}.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
print(f"\nDONE -> portfolio_out{SUFFIX}.json", flush=True)
