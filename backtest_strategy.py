# -*- coding: utf-8 -*-
"""严格按《C7操盘策略落地方案.html》执行回测：C7单池 vs C6+C7双池，同口径。

【T+1 修正 · 本版】
  问题：旧版退出循环 for d in range(HOLD) 从 d=0 开始，d=0 即 T+1 买入当日——
        当日触及止盈/止损即当日卖出，违反 A 股 T+1（产生 400 笔当日回转）。
  修复：退出检查起点 d=0 -> d=1，即买入当日不可卖，卖出最早发生在买入后第二日(T+2)。
        TIME 平仓仍用第7日收盘 CC[HOLD-1]，持有上限不变。
  口径：两套独立输出——正常(全市场) 与 仅主板(board='main')。

规则常量逐字来自方案（T+1 为 A 股硬约束，属规则正确性修正，非调参）：
   规则2.1 买入：T收盘×0.95 限价挂单；T+1最低触及则以限价成交，开盘低于挂单按开盘成交，未触及放弃。
   规则2.2 滞后：不追已启动票，取当日成交（保守）。
   规则3.1 退出：止盈+15%、止损-8%、持有上限7日；同日先止损后止盈；T+1 当日不可卖(T+1约束)。
   规则1.1 排序：vol20↑+ret_5d↑+turnover_rate↑ 综合分（top50%辅助分析）。
   规则5.1 连续在池≥2日优先（分组辅助分析）。
   规则5.3 成本0.1~0.15%（主表未扣，另列扣0.15%参考）。
"""
from __future__ import annotations
import json, time
from pathlib import Path
import duckdb, numpy as np, pandas as pd

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RM = (WS / "research_matrix.parquet").as_posix()
D0, D1 = "2024-03-13", "2026-11-01"

ENTRY_PCT = -5; TP = 15; SL = -8; HOLD = 7; COST = 0.15
ZREF = dict(vol_m=3.010096, vol_s=1.639706, ret_m=0.848288,
            ret_s=7.840214, tor_m=4.794629, tor_s=5.705012)
T1_FIRST_EXIT_D = 1   # T+1 约束：退出检查最早 d=1（买入后第二日 T+2），d=0 为买入当日不可卖

t0 = time.time()
con = duckdb.connect(); con.execute("SET threads=8")
leadcols = ",\n    ".join(
    f"lead({c},{k}) OVER (PARTITION BY code ORDER BY di) AS {a}{k}"
    for k in range(1, 11) for c, a in [("open", "o"), ("high", "h"), ("low", "l"), ("close", "c")]
)
sql = f"""
WITH allx AS (
  SELECT trade_date, di, split, code, name, board, close AS c0,
    {leadcols},
    lead(di,10) OVER (PARTITION BY code ORDER BY di) AS di10,
    vol20, ret_5d, turnover_rate, n_leader_concepts,
    CAST((lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7
          AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679
          AND ma5>ma20 AND ma20>ma60) AS INT) AS is_c6,
    CAST((lu_cnt_20d>=1 AND main_net_norm>0 AND vol20>=3.5238 AND turnover_rate>=3.7
          AND lu_gap>=-3 AND close_hh20_ratio>=0.95 AND ret_5d>=4.8679
          AND ma5>ma20 AND ma20>ma60 AND n_leader_concepts>=1) AS INT) AS is_c7
  FROM read_parquet('{RM}')
),
g6 AS (SELECT di,code,row_number() OVER (PARTITION BY code ORDER BY di) rn FROM allx WHERE is_c6=1),
r6 AS (SELECT di,code,di-rn grp FROM g6),
s6 AS (SELECT di,code,count(*) OVER (PARTITION BY code,grp ORDER BY di) streak6 FROM r6),
g7 AS (SELECT di,code,row_number() OVER (PARTITION BY code ORDER BY di) rn FROM allx WHERE is_c7=1),
r7 AS (SELECT di,code,di-rn grp FROM g7),
s7 AS (SELECT di,code,count(*) OVER (PARTITION BY code,grp ORDER BY di) streak7 FROM r7)
SELECT f.*, coalesce(x6.streak6,1) AS streak6, coalesce(x7.streak7,1) AS streak7
FROM allx f
LEFT JOIN s6 x6 ON f.di=x6.di AND f.code=x6.code
LEFT JOIN s7 x7 ON f.di=x7.di AND f.code=x7.code
WHERE f.is_c6=1 AND f.trade_date>='{D0}' AND f.trade_date<='{D1}' AND f.di10=f.di+10
"""
raw = con.execute(sql).df(); con.close()
print("区间C6候选(前向完整):", len(raw), " C7:", int(raw.is_c7.sum()),
      " 主板:", int((raw.board=='main').sum()), " sec=%.1f" % (time.time()-t0), flush=True)


def run_pool(sub: pd.DataFrame) -> pd.DataFrame:
    """对给定池（已筛好的子表）按方案逐笔回测，含 T+1 约束。"""
    sub = sub.reset_index(drop=True)
    n = len(sub)
    if n == 0:
        return sub
    cc0 = sub.c0.values; oo1 = sub.o1.values; ll1 = sub.l1.values
    HH = np.array([sub[f"h{k}"].values for k in range(1, 11)])
    LL = np.array([sub[f"l{k}"].values for k in range(1, 11)])
    CC = np.array([sub[f"c{k}"].values for k in range(1, 11)])
    px = cc0 * (1 + ENTRY_PCT / 100)
    filled = ll1 <= px
    fill_px = np.where(oo1 <= px, oo1, px)
    tp_px = fill_px * (1 + TP / 100); sl_px = fill_px * (1 + SL / 100)
    ret = np.full(n, np.nan); reason = np.empty(n, dtype="U4"); k_exit = np.full(n, np.nan)
    mfe7 = np.full(n, np.nan); mfe10 = np.full(n, np.nan); mae7 = np.full(n, np.nan)
    for i in range(n):
        if not filled[i]:
            continue
        # T+1：d=0 为买入当日，禁止卖出；从 d=1(T+2) 起检查
        for d in range(T1_FIRST_EXIT_D, HOLD):
            if LL[d, i] <= sl_px[i]:
                ret[i] = SL; reason[i] = "SL"; k_exit[i] = d + 1; break
            if HH[d, i] >= tp_px[i]:
                ret[i] = TP; reason[i] = "TP"; k_exit[i] = d + 1; break
        if np.isnan(ret[i]):
            ret[i] = (CC[HOLD-1, i] / fill_px[i] - 1) * 100
            reason[i] = "TIME"; k_exit[i] = HOLD
        mfe7[i] = (np.max(HH[:HOLD, i]) / fill_px[i] - 1) * 100
        mfe10[i] = (np.max(HH[:10, i]) / fill_px[i] - 1) * 100
        mae7[i] = (np.min(LL[:HOLD, i]) / fill_px[i] - 1) * 100
    sub["filled"] = filled; sub["fill_px"] = fill_px
    sub["ret"] = ret; sub["reason"] = reason; sub["k_exit"] = k_exit
    sub["mfe7"] = mfe7; sub["mfe10"] = mfe10; sub["mae7"] = mae7
    z = ZREF
    sub["score"] = ((sub.vol20 - z["vol_m"]) / z["vol_s"]
                    + (sub.ret_5d - z["ret_m"]) / z["ret_s"]
                    + (sub.turnover_rate - z["tor_m"]) / z["tor_s"])
    return sub


def metrics(d: pd.DataFrame, label: str) -> dict:
    sig = len(d); fl = d[d.filled]; nf = len(fl); r = fl.ret.dropna()
    gp = float(r[r > 0].sum()); gl = float(abs(r[r < 0].sum()))
    rec = dict(
        group=label, n_signals=sig, n_filled=nf,
        fill_rate=round(nf / sig * 100, 2) if sig else None,
        avg_ret=round(float(r.mean()), 4) if len(r) else None,
        avg_ret_net=round(float(r.mean()) - COST, 4) if len(r) else None,
        win_rate=round(float((r > 0).mean()) * 100, 2) if len(r) else None,
        profit_factor=round(gp / gl, 3) if gl > 0 else None,
        avg_win=round(float(r[r > 0].mean()), 3) if (r > 0).any() else None,
        avg_loss=round(float(r[r < 0].mean()), 3) if (r < 0).any() else None,
        mfe20_hold7=round(float((fl.mfe7 >= 20).mean()) * 100, 2) if nf else None,
        mfe20_10d=round(float((fl.mfe10 >= 20).mean()) * 100, 2) if nf else None,
        mae_mean=round(float(fl.mae7.mean()), 3) if nf else None,
        exit_TP=round(float((fl.reason == "TP").mean()) * 100, 2) if nf else None,
        exit_SL=round(float((fl.reason == "SL").mean()) * 100, 2) if nf else None,
        exit_TIME=round(float((fl.reason == "TIME").mean()) * 100, 2) if nf else None,
        n_sameday_roundtrip=int((fl.k_exit == 1).sum()) if nf else 0,
        n_streak2=round(float((fl.streak6 >= 2).mean()) * 100, 2) if nf else None,
    )
    return rec


ALL_RESULTS = {}
POOLS = [("C7单池", "c7"), ("C6+C7双池", "dual")]
for board_mode, board_mask in [("normal", np.ones(len(raw), dtype=bool)),
                               ("main", (raw.board == 'main').values)]:
    subraw = raw[board_mask].reset_index(drop=True)
    results = {"config": dict(D0=D0, D1=D1, entry=ENTRY_PCT, tp=TP, sl=SL, hold=HOLD,
                              cost=COST, board_mode=board_mode,
                              board_filter="" if board_mode == 'normal' else "board=='main'",
                              t1_first_exit_d=T1_FIRST_EXIT_D,
                              t1_rule="买入当日(d=0)不可卖，最早T+2(d=1)卖出",
                              c7_cond="9条件", c6_cond="8条件(C7⊂C6)"),
               "groups": {}, "aux": {}}
    for gname, tag in POOLS:
        pmask = subraw.is_c7.values.astype(bool) if tag == "c7" else np.ones(len(subraw), dtype=bool)
        d = run_pool(subraw[pmask])
        suffix = "" if board_mode == 'normal' else "_main"
        d.to_csv(WS / f"backtest_detail_{tag}{suffix}.csv", index=False, encoding="utf-8-sig")
        segs = {"全区间": d}
        for sp in ["train", "oos"]:
            segs[sp] = d[d.split == sp]
        results["groups"][gname] = {seg: metrics(dd, f"{gname}/{seg}") for seg, dd in segs.items()}
        base = d[d.filled]
        parts = []
        for di, g in base.groupby("di"):
            parts.append(g.nlargest(max(1, int(len(g) * 0.5)), "score"))
        top = pd.concat(parts) if parts else base.iloc[0:0]
        results["aux"][gname] = dict(
            top50_n=len(top),
            top50_avg_ret=round(float(top.ret.mean()), 4) if len(top) else None,
            all_avg_ret=round(float(base.ret.mean()), 4) if len(base) else None,
            streak2=metrics(base[base.streak6 >= 2], "streak>=2"),
            streak1=metrics(base[base.streak6 == 1], "streak==1"),
        )
        print(f"\n[{board_mode}] {gname}:", flush=True)
        for seg, dd in segs.items():
            m = results["groups"][gname][seg]
            print(f"  {seg}: 信号{m['n_signals']} 成交{m['n_filled']}({m['fill_rate']}%) "
                  f"期望{m['avg_ret']}% 胜率{m['win_rate']}% PF={m['profit_factor']} "
                  f"当日回转={m['n_sameday_roundtrip']}", flush=True)
    outname = "backtest_out.json" if board_mode == 'normal' else "backtest_out_main.json"
    (WS / outname).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    ALL_RESULTS[board_mode] = results
    print(f"  -> {outname}", flush=True)

print("\nDONE sec=%.1f" % (time.time()-t0), flush=True)
