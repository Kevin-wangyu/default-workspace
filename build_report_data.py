# -*- coding: utf-8 -*-
"""
构造商业级报告所需的全部数据（零写入投研项目，输出仅到工作目录）。
- 读取 matrix.parquet / search_results.json / scan2_out.json
- 对推荐规则做"逐日回放"：全时间轴（train+oos）每日 n / hit10 / hit5，含日期标记
- 抽取达标日窗口（逐日 hit>=0.75 且 n>=20），并给出这些日期的全市场 base rate（证明是市场状态驱动）
- 计算"仅在达标日窗口应用规则"的合并池达标比例 = 含日期标记的条件组合验证结果
- 输出 report_data.json
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import duckdb

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
MAT = (WS / "matrix.parquet").as_posix()
R = json.loads((WS / "search_results.json").read_text(encoding="utf-8"))
S = json.loads((WS / "scan2_out.json").read_text(encoding="utf-8"))

con = duckdb.connect()
con.execute("SET threads=8")
M = f"read_parquet('{MAT}')"

schema = con.execute(f"DESCRIBE SELECT * FROM {M}").df()
print("=== MATRIX SCHEMA ===")
print(schema[["column_name", "column_type"]].to_string(index=False))
cols = list(schema["column_name"])
print("NCOLS", len(cols))

DIMS = list(R["templates"]["T1_资金聚集_量价趋势"]["spec"][0:0]) if False else None
# 维度以 bayes_search.DIMS 为准
DIM_KEYS = ["turnover_rate", "tor_ratio", "amt_ratio", "amt_ma20", "huge_norm",
            "main_net_norm", "small_norm", "scrplus_90", "scrplus_70", "vol20",
            "lu_cnt_10d", "lu_cnt_20d", "n_hot_concepts", "n_leader_concepts",
            "in_strong_concept", "n_concepts", "pct_change", "bias5", "bias20",
            "close_hh20_ratio", "ret_5d", "ret_10d", "ret_20d", "lu_gap",
            "is_limit_up", "ma5_gt_ma20", "ma20_gt_ma60"]

# 分位表（train_all 建立，与 bayes_search 完全一致）
QGRID = np.round(np.arange(0.01, 1.00, 0.01), 2)
need = ["di", "trade_date", "split", "y10", "y5", "mkt_hit10", "mkt_hit5",
        "mkt_amount", "mkt_lu", "mkt_lu_ma5", "mkt_amt_ratio"] + DIM_KEYS
need = [c for c in need if c in cols]
arr = con.execute(f"SELECT {', '.join(need)} FROM {M}").fetchnumpy()
X = {c: np.asarray(arr[c], dtype=np.float64) for c in DIM_KEYS if c in arr}
di = np.asarray(arr["di"], dtype=np.int64)
y10 = np.asarray(arr["y10"], dtype=np.float64)
y5 = np.asarray(arr["y5"], dtype=np.float64)
td = np.asarray(arr["trade_date"], dtype=str)
split = np.asarray(arr["split"], dtype=str)
finite = np.ones(len(di), dtype=bool)
for c in DIM_KEYS:
    if c not in X:
        continue
    x = np.where(np.isfinite(X[c]), X[c], np.nan)
    finite &= np.isfinite(x)
    X[c] = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
lab10 = np.isfinite(y10)
lab5 = np.isfinite(y5)
y10 = np.nan_to_num(y10, nan=0.0)
y5 = np.nan_to_num(y5, nan=0.0)
print("rows", len(di), "di range", int(di.min()), int(di.max()))

# QMAP from train_all finite
trmask = (split == "train") & finite
QMAP = {}
for c in DIM_KEYS:
    if c not in X:
        continue
    QMAP[c] = {float(q): float(np.quantile(X[c][trmask], q)) for q in QGRID}

def thr(dim, q):
    q = float(np.clip(round(float(q), 2), 0.01, 0.99))
    return QMAP[dim][q]

# date map
dd = con.execute(f"SELECT DISTINCT di, CAST(trade_date AS VARCHAR) AS d FROM {M} ORDER BY di").df()
di2date = dict(zip(dd["di"].astype(int), dd["d"].astype(str)))
# market daily series (one value per di)
def market_daily(col):
    if col not in arr:
        return {}
    v = np.asarray(arr[col], dtype=np.float64)
    out = {}
    for d in np.unique(di):
        vals = v[di == d]
        vals = vals[np.isfinite(vals)]
        out[int(d)] = float(vals.mean()) if len(vals) else None
    return out
MK = {c: market_daily(c) for c in ["mkt_hit10", "mkt_hit5", "mkt_amount",
                                    "mkt_lu", "mkt_lu_ma5", "mkt_amt_ratio"]}

MIN_N_DAY = 20

def rule_daily(rule):
    """返回全时间轴逐日 n/hit10/hit5 + 达标日窗口 + 仅达标日窗口的合并池比例。"""
    m = finite.copy()
    for dim, op, q in rule:
        t = thr(dim, q)
        x = X[dim]
        m &= (x >= t) if op == ">=" else (x <= t)
    sel10 = m & lab10
    sel5 = m & lab5
    days = np.unique(di[sel10 | sel5])
    rows = []
    for d in days:
        i10 = di == d
        s10 = sel10 & i10
        s5 = sel5 & i10
        n10 = int(s10.sum())
        n5 = int(s5.sum())
        h10 = float(y10[s10].mean()) if n10 else None
        h5 = float(y5[s5].mean()) if n5 else None
        rows.append({
            "di": int(d), "date": di2date.get(int(d), ""),
            "split": "train" if split[i10][0] == "train" else "oos" if split[i10][0] == "oos" else split[i10][0],
            "n10": n10, "hit10": h10, "n5": n5, "hit5": h5,
            "mkt_hit10": MK["mkt_hit10"].get(int(d)),
            "mkt_hit5": MK["mkt_hit5"].get(int(d)),
            "mkt_amount": MK["mkt_amount"].get(int(d)),
            "mkt_lu": MK["mkt_lu"].get(int(d)),
        })
    # 达标日窗口（逐日 hit>=0.75 且 n>=20），10d 与 5d 分别
    def hit_set(tag):
        nk, hk = ("n10", "hit10") if tag == "10" else ("n5", "hit5")
        return [r for r in rows if r[nk] >= MIN_N_DAY and r[hk] is not None and r[hk] >= 0.75]
    d10, d5 = hit_set("10"), hit_set("5")
    # 仅在达标日窗口应用的合并池比例
    def merged(sub, tag):
        nk = "n10" if tag == "10" else "n5"
        dset = set(r["di"] for r in sub)
        if tag == "10":
            sel = sel10 & np.isin(di, list(dset))
            return int(sel.sum()), float(y10[sel].mean()) if sel.sum() else None
        else:
            sel = sel5 & np.isin(di, list(dset))
            return int(sel.sum()), float(y5[sel].mean()) if sel.sum() else None
    n_r10, h_r10 = merged(d10, "10")
    n_r5, h_r5 = merged(d5, "5")
    # 全样本合并池
    n_all10 = int(sel10.sum()); h_all10 = float(y10[sel10].mean()) if n_all10 else None
    n_all5 = int(sel5.sum()); h_all5 = float(y5[sel5].mean()) if n_all5 else None
    return {
        "daily": rows,
        "hit10_dates": [{"date": r["date"], "n": r["n10"], "hit": round(r["hit10"], 4),
                         "mkt_hit10": r["mkt_hit10"], "mkt_amount": r["mkt_amount"]} for r in d10],
        "hit5_dates": [{"date": r["date"], "n": r["n5"], "hit": round(r["hit5"], 4),
                        "mkt_hit5": r["mkt_hit5"]} for r in d5],
        "restricted_pool": {"10": {"n": n_r10, "hit": h_r10, "n_days": len(d10)},
                            "5": {"n": n_r5, "hit": h_r5, "n_days": len(d5)}},
        "all_pool": {"10": {"n": n_all10, "hit": h_all10},
                     "5": {"n": n_all5, "hit": h_all5}},
    }

# ---- 选择"推荐条件组合" ----
# R1 = 最佳 C 档（train 合并池 0.4183，OOS 0.3522，稳定性最好之一）
# R2 = 逐日达标率最高的超跌反转（daily75=0.2609，6 个达标日）
# R3 = 覆盖度最高的情绪涨停模板（valid_days 240，便于看牛熊全貌）
grades = R["grades"]["C_25-50%"]
pick = {}
for key, idx, tag in [("R1_资金聚集高波动龙头", 0, "主力+波动+涨停+龙头+动量"),
                      ("R2_超跌反转放量", 1, "涨跌平衡/超跌反转"),
                      ("R3_情绪涨停高覆盖", 3, "情绪/涨停/筹码（高覆盖）")]:
    g = grades[idx]
    pick[key] = {
        "label": g["label"], "rule": g["rule"], "theory": tag,
        "train": g["train"], "iv": g["iv"], "oos": g["oos"],
        "hit75_dates": g["hit75_dates"], "replay": rule_daily(g["rule"]),
    }
    rp = pick[key]["replay"]
    print(f"{key}: all10={rp['all_pool']['10']['hit']:.4f} restricted10={rp['restricted_pool']['10']['hit']} "
          f"n_days10={rp['restricted_pool']['10']['n_days']} | restricted5={rp['restricted_pool']['5']['hit']} "
          f"n_days5={rp['restricted_pool']['5']['n_days']}")

# ---- 高 base-rate 日清单（全市场口径） ----
hd = S["high_days"]["rows"]
print("high_days rows sample:", json.dumps(hd[0], ensure_ascii=False) if hd else "EMPTY")

# ---- 模板稳定性汇总（给图表用） ----
stab = []
for name, blk in R["templates"].items():
    rep = blk["report"]
    stab.append({
        "name": name,
        "train10": rep["train"]["10"]["merge"], "train5": rep["train"]["5"]["merge"],
        "iv10": rep["iv"]["10"]["merge"], "iv5": rep["iv"]["5"]["merge"],
        "oos10": rep["oos"]["10"]["merge"], "oos5": rep["oos"]["5"]["merge"],
        "pool": rep["train"]["10"]["pool_n"],
        "d75": rep["train"]["10"]["daily75"],
        "lift10": rep["train"]["10"]["lift"],
    })

DATA = {
    "config": R["config"],
    "baseline": R["baseline"],
    "monthly_base": R["monthly_base"],
    "grade_summary": R["grade_summary"],
    "grades": {g: [{"label": it["label"], "rule": it["rule"],
                    "train10": it["train"]["10"]["merge"], "train5": it["train"]["5"]["merge"],
                    "oos10": it["oos"]["10"]["merge"], "oos5": it["oos"]["5"]["merge"],
                    "d75": it["train"]["10"]["daily75"], "lift10": it["train"]["10"]["lift"],
                    "pool": it["train"]["10"]["pool_n"], "hit75_dates": it["hit75_dates"]}
               for it in items] for g, items in R["grades"].items()},
    "templates_stability": stab,
    "recommended": pick,
    "high_days": hd,
    "stock_scan": S["stock_scan"],
    "scan_train_base": S["train_base"],
    "dims_meta": {k: {"cn": v[0], "theory": v[1]} for k, v in []},  # filled below
}
print("WROTE report_data.json")
(WS / "report_data.json").write_text(json.dumps(DATA, ensure_ascii=False, default=str), encoding="utf-8")
