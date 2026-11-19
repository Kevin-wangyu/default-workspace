# -*- coding: utf-8 -*-
"""
TPE 风格贝叶斯优化搜索选股条件组合（零写入投研项目）。
口径（用户 m00079 + m00106 + m00151 + m00171）：
- 候选池 = 全市场（非概念交集池）
- 日期 = 复盘横轴 / 牛熊标注，不作筛选条件、不作市场状态指标
- 条件 = 纯"当日可知"个股指标阈值组合
- 内层切分：inner_train 2024-02~2025-06 / inner_val 2025-07~2025-12；OOS 2026-01~2026-10 仅最终验收
- 双口径：y10 (未来10日 max high 涨幅>=20%) / y5 (未来5日)，分别独立评估
- 最小选中数：每日>=20 只，合并池>=500 只
输出：search_results.json
"""
from __future__ import annotations
import json, time, math, random
from pathlib import Path
import duckdb, numpy as np
from scipy.stats import gaussian_kde

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
MAT = (WS / "matrix.parquet").as_posix()
OUT = WS / "search_results.json"
rng = np.random.default_rng(20261112)
random.seed(20261112)

# ---------------- 维度定义（全部 T 日收盘可知；剔除 hot_rank / max_concept_score） ----------------
DIMS = {
    "turnover_rate":   ("换手率%", "有量才有价"),
    "tor_ratio":       ("换手率/5日均", "有量才有价"),
    "amt_ratio":       ("成交额/20日均", "有量才有价"),
    "amt_ma20":        ("20日均成交额", "有量才有价"),
    "huge_norm":       ("超大单净额/成交额", "主力参与"),
    "main_net_norm":   ("主力净额/成交额", "主力参与"),
    "small_norm":      ("小单净额/成交额", "收益与风险并存"),
    "scrplus_90":      ("90%筹码获利比例", "指标滞后/筹码"),
    "scrplus_70":      ("70%筹码获利比例", "指标滞后/筹码"),
    "vol20":           ("20日波动率", "收益大与风险大"),
    "lu_cnt_10d":      ("近10日涨停次数", "资金聚集/情绪"),
    "lu_cnt_20d":      ("近20日涨停次数", "资金聚集/情绪"),
    "n_hot_concepts":  ("命中当日热榜概念数", "资金聚集/概念"),
    "n_leader_concepts": ("命中龙头概念数", "资金聚集/龙头"),
    "in_strong_concept": ("属强概念", "资金聚集"),
    "n_concepts":      ("概念总数", "资金聚集"),
    "pct_change":      ("当日涨跌幅%", "趋势/动量"),
    "bias5":           ("收盘/MA5-1", "趋势"),
    "bias20":          ("收盘/MA20-1", "趋势"),
    "close_hh20_ratio": ("收盘/20日最高", "涨跌平衡"),
    "ret_5d":          ("近5日涨幅%", "趋势"),
    "ret_10d":         ("近10日涨幅%", "趋势"),
    "ret_20d":         ("近20日涨幅%", "趋势"),
    "lu_gap":          ("涨幅-涨停阈值", "涨跌平衡"),
    "is_limit_up":     ("当日涨停", "资金聚集/情绪"),
    "ma5_gt_ma20":     ("MA5>MA20", "趋势"),
    "ma20_gt_ma60":    ("MA20>MA60", "趋势"),
}
DIM_LIST = list(DIMS)

# ---------------- 载入矩阵到 numpy ----------------
t0 = time.time()
con = duckdb.connect()
con.execute("SET threads=8")
M = f"read_parquet('{MAT}')"

def load(sp_where, tag):
    cols = ["di", "trade_date", "y10", "y5", "mkt_hit10", "mkt_hit5"] + DIM_LIST
    sql = f"SELECT {', '.join(cols)} FROM {M} WHERE {sp_where}"
    arr = con.execute(sql).fetchnumpy()
    X = {c: np.asarray(arr[c], dtype=np.float64) for c in DIM_LIST}
    di = np.asarray(arr["di"], dtype=np.int64)
    y10 = np.asarray(arr["y10"], dtype=np.float64)
    y5 = np.asarray(arr["y5"], dtype=np.float64)
    finite = np.ones(len(di), dtype=bool)
    for c in DIM_LIST:
        x = X[c]
        x = np.where(np.isfinite(x), x, np.nan)
        finite &= np.isfinite(x)
        # NaN 填 0（配合 finite mask，不会被选中）
        X[c] = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    lab10 = np.isfinite(y10)
    lab5 = np.isfinite(y5)
    y10 = np.nan_to_num(y10, nan=0.0)
    y5 = np.nan_to_num(y5, nan=0.0)
    return {"X": X, "di": di, "y10": y10, "y5": y5, "finite": finite,
            "lab10": lab10, "lab5": lab5, "tag": tag,
            "n_days": int(di.max()) if len(di) else 0}

SPLITS = {
    "tr":  load("split='train' AND trade_date <= '2025-06-30'", "inner_train 2024-02~2025-06"),
    "iv":  load("split='train' AND trade_date >  '2025-06-30'", "inner_val   2025-07~2025-12"),
    "train": load("split='train'", "train_all   2024-02~2025-12"),
    "oos": load("split='oos'", "oos         2026-01~2026-10"),
}
for k, v in SPLITS.items():
    print(f"loaded {k}: {len(v['di']):,} rows", flush=True)

# 分位表（用 train_all 建立，q 网格 0.01..0.99）
QGRID = np.round(np.arange(0.01, 1.00, 0.01), 2)
QMAP = {}
for c in DIM_LIST:
    x = SPLITS["train"]["X"][c][SPLITS["train"]["finite"]]
    QMAP[c] = {float(q): float(np.quantile(x, q)) for q in QGRID}
BASE = {"10": 0.1154, "5": 0.0524}
MIN_N_DAY = 20
MIN_POOL = 500

def thr(dim, q):
    """统一分位→阈值查找，避免浮点 key 漂移 / 越界。"""
    q = float(np.clip(round(float(q), 2), 0.01, 0.99))
    return QMAP[dim][q]

# ---------------- 评估器 ----------------
def evaluate(rule, sp):
    S = SPLITS[sp]
    m = S["finite"].copy()
    for dim, op, q in rule:
        t = thr(dim, q)
        x = S["X"][dim]
        if op == ">=":
            m &= (x >= t)
        else:
            m &= (x <= t)
    out = {}
    for tag, lab, y in [("10", S["lab10"], S["y10"]), ("5", S["lab5"], S["y5"])]:
        sel = m & lab
        n = int(sel.sum())
        if n == 0:
            out[tag] = {"pool_n": 0, "merge": 0.0, "daily75": 0.0, "daily50": 0.0,
                        "hit_days": 0, "valid_days": 0, "total_days": 0,
                        "min_day_n": 0, "daily_mean": 0.0, "daily_median": 0.0,
                        "lift": 0.0, "coverage": 0.0}
            continue
        cnt = np.bincount(S["di"][sel], minlength=700)
        wins = np.bincount(S["di"][sel], weights=y[sel], minlength=700)
        valid = cnt >= MIN_N_DAY
        vd = int(valid.sum())
        daily = wins[valid] / cnt[valid] if vd else np.array([])
        hit75 = int((daily >= 0.75).sum()) if vd else 0
        hit50 = int((daily >= 0.50).sum()) if vd else 0
        merge = float(wins.sum() / n)
        out[tag] = {
            "pool_n": n, "merge": round(merge, 4),
            "daily75": round(hit75 / vd, 4) if vd else 0.0,
            "daily50": round(hit50 / vd, 4) if vd else 0.0,
            "hit_days": hit75, "valid_days": vd,
            "total_days": int((cnt > 0).sum()),
            "min_day_n": int(cnt[cnt > 0].min()) if n else 0,
            "daily_mean": round(float(daily.mean()), 4) if vd else 0.0,
            "daily_median": round(float(np.median(daily)), 4) if vd else 0.0,
            "lift": round(merge / BASE[tag], 3),
            "coverage": round(vd / max(int((cnt > 0).sum()), 1), 4),
        }
    out["n_cond"] = len(rule)
    return out

def score_of(r, tag="10"):
    a = r[tag]
    if a["pool_n"] < MIN_POOL:
        return -0.5 + 0.5 * a["pool_n"] / MIN_POOL
    return (0.40 * a["merge"]
            + 0.12 * r["5"]["merge"]
            + 0.26 * a["daily75"]
            + 0.08 * r["5"]["daily75"]
            + 0.09 * min(a["lift"], 3.0) / 3.0
            + 0.05 * a["coverage"])

def objective(rule):
    a = evaluate(rule, "tr")
    b = evaluate(rule, "iv")
    sa, sb = score_of(a), score_of(b)
    # 惩罚 inner_train / inner_val 不一致（抑制过拟合）
    gap = abs(sa - sb)
    return float(0.60 * sa + 0.40 * sb - 0.15 * gap)

# ---------------- 模板（理论驱动） ----------------
TEMPLATES = {
    "T1_资金聚集_量价趋势": [
        ("turnover_rate", ">="), ("amt_ratio", ">="), ("n_hot_concepts", ">="),
        ("ret_20d", ">="), ("huge_norm", ">="), ("vol20", ">="),
    ],
    "T2_情绪涨停_波动筹码": [
        ("pct_change", ">="), ("lu_cnt_20d", ">="), ("vol20", ">="),
        ("scrplus_90", ">="), ("bias5", ">="), ("small_norm", "<="),
    ],
    "T3_涨跌平衡_超跌反转": [
        ("close_hh20_ratio", "<="), ("bias5", "<="), ("lu_cnt_20d", ">="),
        ("turnover_rate", ">="), ("amt_ratio", ">="), ("scrplus_70", "<="),
    ],
    "T4_探索A": [
        ("vol20", ">="), ("lu_cnt_10d", ">="), ("n_leader_concepts", ">="),
        ("main_net_norm", ">="), ("ret_10d", ">="),
    ],
    "T5_探索B": [
        ("scrplus_90", "<="), ("turnover_rate", ">="), ("bias20", ">="),
        ("n_concepts", ">="), ("amt_ratio", ">="), ("small_norm", ">="),
    ],
}
# 每个模板补 1~2 个随机维度作为探索模板（保持结构清晰，另跑一次自由组合）
FREEDOM_DIMS = ["vol20", "lu_cnt_20d", "scrplus_90", "turnover_rate", "amt_ratio",
                "pct_change", "bias5", "ret_20d", "huge_norm", "main_net_norm",
                "n_hot_concepts", "n_leader_concepts", "close_hh20_ratio", "lu_gap",
                "small_norm", "ret_5d", "bias20", "amt_ma20", "tor_ratio", "scrplus_70"]

TEMPLATES["T6_自由组合"] = [(d, ">=") for d in FREEDOM_DIMS[:6]]
TEMPLATES["T7_自由组合"] = [(d, rng.choice([">=", "<="])) for d in rng.choice(FREEDOM_DIMS, 6, replace=False)]

# ---------------- TPE 风格贝叶斯优化（scipy gaussian_kde） ----------------
def tpe_search(spec, n_iter=190, n_startup=28, gamma=0.18, n_cand=24):
    """spec: list of (dim, op)；搜索每个条件的分位 q∈[0.03,0.97]。"""
    d = len(spec)
    trials = []  # (qvec, score)
    best = (-9, None, None)

    def suggest(hist):
        if len(hist) < n_startup:
            return np.round(rng.uniform(0.03, 0.97, d), 2)
        arr = np.array([h[0] for h in hist])
        sc = np.array([h[1] for h in hist])
        cut = np.quantile(sc, 1 - gamma)
        good, bad = arr[sc >= cut], arr[sc < cut]
        if len(good) < 3 or len(bad) < 3:
            return np.round(rng.uniform(0.03, 0.97, d), 2)
        cands = np.round(rng.uniform(0.03, 0.97, (n_cand, d)), 2)
        logratio = np.zeros(n_cand)
        for j in range(d):
            try:
                kg = gaussian_kde(good[:, j] + rng.normal(0, 1e-4, len(good)))
                kb = gaussian_kde(bad[:, j] + rng.normal(0, 1e-4, len(bad)))
                lg = np.log(np.clip(kg(cands[:, j]), 1e-12, None))
                lb = np.log(np.clip(kb(cands[:, j]), 1e-12, None))
                logratio += lg - lb
            except Exception:
                pass
        return cands[int(np.argmax(logratio))]

    curve = []
    for it in range(n_iter):
        qv = suggest(trials)
        rule = [(spec[i][0], spec[i][1], float(qv[i])) for i in range(d)]
        try:
            s = objective(rule)
        except Exception:
            s = -1.0
        trials.append((qv, s))
        if s > best[0]:
            best = (s, rule, qv.copy())
        curve.append(round(float(s), 4))
    hist_sorted = sorted(trials, key=lambda x: -x[1])
    top = []
    for qv, s in hist_sorted[:8]:
        r = [(spec[i][0], spec[i][1], float(qv[i])) for i in range(d)]
        top.append({"score": round(float(s), 4), "rule": r})
    return {"best_score": round(float(best[0]), 4), "best_rule": best[1],
            "n_iter": n_iter, "curve": curve, "top": top,
            "trial_scores": [round(float(s), 4) for _, s in trials]}

def rule_label(rule):
    parts = []
    for dim, op, q in rule:
        t = thr(dim, q)
        cn = DIMS[dim][0]
        parts.append(f"{cn} {op} {t:.4g} (q{q:.2f})")
    return " AND ".join(parts)

def full_report(rule):
    out = {"rule": rule, "label": rule_label(rule)}
    for sp in ["tr", "iv", "train", "oos"]:
        out[sp] = evaluate(rule, sp)
        out[sp]["tag"] = SPLITS[sp]["tag"]
    # 达标日期清单（可复盘）：train + oos 上逐日 hit10>=0.75 且 n>=20 的日期
    S = SPLITS["train"]
    m = S["finite"].copy()
    for dim, op, q in rule:
        t = thr(dim, q)
        x = S["X"][dim]
        m &= (x >= t) if op == ">=" else (x <= t)
    sel = m & S["lab10"]
    cnt = np.bincount(S["di"][sel], minlength=700)
    wins = np.bincount(S["di"][sel], weights=S["y10"][sel], minlength=700)
    valid = cnt >= MIN_N_DAY
    daily = np.where(valid, wins / np.maximum(cnt, 1), np.nan)
    sql = f"SELECT DISTINCT di, trade_date FROM {M} ORDER BY di"
    dd = con.execute(sql).df()
    di2date = dict(zip(dd.di.astype(int), dd.trade_date.astype(str)))
    hit_dates = [di2date[int(i)] for i in np.where(valid & (daily >= 0.75))[0] if int(i) in di2date]
    out["train_hit75_dates"] = hit_dates
    out["train_daily10"] = {"di": [int(i) for i in np.where(valid)[0]],
                            "date": [di2date.get(int(i), "") for i in np.where(valid)[0]],
                            "n": [int(cnt[i]) for i in np.where(valid)[0]],
                            "hit": [round(float(daily[i]), 4) for i in np.where(valid)[0]]}
    return out

# ---------------- 执行搜索 ----------------
results = {"config": {
    "method": "TPE 风格贝叶斯优化 (scipy gaussian_kde) + 内层时间切分 + 样本外验收",
    "train_period": "2024-02-01~2025-12-31",
    "inner_train": "2024-02-01~2025-06-30",
    "inner_val": "2025-07-01~2025-12-31",
    "oos": "2026-01-01~2026-10-31",
    "base_rate": BASE, "min_n_day": MIN_N_DAY, "min_pool": MIN_POOL,
    "n_rows": {k: len(v["di"]) for k, v in SPLITS.items()},
    "label_def": "y10=1 iff max(high[T+1..T+10])/close[T]-1 >= 20%; y5 同理 5 日",
    "date_role": "横轴/牛熊标注，不作筛选条件（用户 m00171）",
    "excluded_fields": ["hot_rank (picks 全 null / quote 缺 26.36%)", "max_concept_score (缺 44.6%)"],
}, "templates": {}}

all_reports = []
for name, spec in TEMPLATES.items():
    t1 = time.time()
    r = tpe_search(spec, n_iter=190)
    rep = full_report(r["best_rule"])
    r["report"] = rep
    results["templates"][name] = {"spec": spec, "search": {k: v for k, v in r.items() if k != "report"},
                                  "report": rep, "seconds": round(time.time() - t1, 1)}
    all_reports.append(rep)
    print(f"{name}: best={r['best_score']} train10={rep['train']['10']['merge']} "
          f"oos10={rep['oos']['10']['merge']} daily75={rep['train']['10']['daily75']} "
          f"pool={rep['train']['10']['pool_n']} ({time.time()-t1:.1f}s)", flush=True)

# ---------------- 启发式精修（局部阈值扰动，作为对照方法） ----------------
def refine(rule, n_iter=140):
    best_r, best_s = rule, objective(rule)
    cur = list(rule)
    for i in range(n_iter):
        cand = [list(x) for x in [cur]][0]
        j = rng.integers(0, len(cand))
        dim, op, q = cand[j]
        step = rng.choice([-0.08, -0.05, -0.03, 0.03, 0.05, 0.08])
        nq = float(np.clip(round(q + step, 2), 0.03, 0.97))
        cand[j] = (dim, op, nq)
        s = objective(cand)
        if s > best_s:
            best_s, best_r = s, cand
        if s > objective(cur) or rng.random() < 0.08:
            cur = cand
    return best_r, float(best_s)

refined = []
for rep in sorted(all_reports, key=lambda x: -score_of(x["train"]))[:3]:
    rr, ss = refine(rep["rule"])
    rp = full_report(rr)
    refined.append({"origin_label": rep["label"], "refined_score": round(ss, 4), "report": rp})
    all_reports.append(rp)
    print(f"refine: {rp['train']['10']['merge']} oos={rp['oos']['10']['merge']} "
          f"daily75={rp['train']['10']['daily75']} pool={rp['train']['10']['pool_n']}", flush=True)
results["refined"] = refined

# ---------------- 三档分级（以 train 合并池 hit10 为主，同时看逐日达标率与 OOS） ----------------
def grade(rep):
    v = rep["train"]["10"]["merge"]
    if v >= 0.75: return "A_>=75%"
    if v >= 0.50: return "B_50-75%"
    if v >= 0.25: return "C_25-50%"
    return "D_<25%"

graded = {}
for rep in all_reports:
    g = grade(rep)
    graded.setdefault(g, []).append({
        "label": rep["label"], "rule": rep["rule"],
        "train": rep["train"], "iv": rep["iv"], "oos": rep["oos"],
        "hit75_dates": rep["train_hit75_dates"],
    })
for g in graded:
    graded[g] = sorted(graded[g], key=lambda x: -x["train"]["10"]["merge"])[:6]
results["grades"] = graded
results["grade_summary"] = {g: len(v) for g, v in graded.items()}

# ---------------- 基线对照 ----------------
results["baseline"] = {}
for sp in ["tr", "iv", "train", "oos"]:
    S = SPLITS[sp]
    r = {"tag": S["tag"]}
    for tag, lab, y in [("10", S["lab10"], S["y10"]), ("5", S["lab5"], S["y5"])]:
        n = int(lab.sum())
        cnt = np.bincount(S["di"][lab], minlength=700)
        wins = np.bincount(S["di"][lab], weights=y[lab], minlength=700)
        valid = cnt >= MIN_N_DAY
        daily = wins[valid] / cnt[valid]
        r[tag] = {"pool_n": n, "merge": round(float(wins.sum() / n), 4),
                  "valid_days": int(valid.sum()),
                  "daily75": round(float((daily >= 0.75).mean()), 4),
                  "hit_days": int((daily >= 0.75).sum()),
                  "daily_mean": round(float(daily.mean()), 4)}
    results["baseline"][sp] = r
    print(f"baseline {sp}: hit10={r['10']['merge']} hit5={r['5']['merge']} "
          f"days>=75%={r['10']['hit_days']}/{r['10']['valid_days']}", flush=True)

# 全区间月度 base rate（制图数据）
mon = con.execute(f"""
SELECT substr(CAST(trade_date AS VARCHAR),1,7) AS ym,
       round(avg(mkt_hit10),4) AS hit10, round(avg(mkt_hit5),4) AS hit5,
       round(avg(mkt_amount)/1e12,3) AS amt
FROM (SELECT DISTINCT trade_date, mkt_hit10, mkt_hit5, mkt_amount FROM {M} WHERE mkt_hit10 IS NOT NULL)
GROUP BY 1 ORDER BY 1
""").df()
results["monthly_base"] = mon.to_dict("records")

OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("grades", results["grade_summary"])
print(f"TOTAL {time.time()-t0:.1f}s -> {OUT}")
print("DONE")
