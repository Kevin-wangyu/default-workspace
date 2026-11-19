# -*- coding: utf-8 -*-
"""Phase1 数据探查：只读、对投研项目零写入。
把探查结果写到工作目录下的 explore_phase1_out.json。
"""
from __future__ import annotations
import sys, json, time, math
from pathlib import Path
from datetime import date, timedelta

PROJ = r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay"
sys.path.insert(0, PROJ)

import pandas as pd

# ── 零写入防护：封掉 tops_cache 的落盘函数 ──
import core.tops_cache as tc
tc._append_tops_cache = lambda *a, **k: None   # no-op，杜绝写 parquet

from queries import list_available_indicators
from queries.concept import _build_intersection_picks
from core.tops_cache import get_tops_and_scores_cached
from trading_calendar import trading_days

OUT = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace\explore_phase1_out.json")

def num(x):
    try:
        f = float(x)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None

result = {}

# 1) 指标清单
inds = list_available_indicators()
result["n_indicators"] = len(inds)
result["indicator_types"] = {}
for it in inds:
    result["indicator_types"][it.get("type")] = result["indicator_types"].get(it.get("type"), 0) + 1
result["indicator_sample"] = [i["name"] for i in inds[:40]]
result["indicator_all_names"] = [i["name"] for i in inds]

# 2) 交易日范围
cal = trading_days(date(2020, 1, 1), date(2027, 12, 31))
result["calendar_n"] = len(cal)
result["calendar_first"] = cal[0].isoformat() if cal else None
result["calendar_last"] = cal[-1].isoformat() if cal else None
cal_s = [d.isoformat() for d in cal]

# 3) 单日全量池探查（取一个已知牛市日 + 一个普通日 + 一个近期日）
test_dates = ["2024-09-30", "2024-10-09", "2024-12-03", "2025-03-14", "2025-08-15", "2026-10-30"]
per_day = {}
fields_seen = set()
for d in test_dates:
    if d not in cal_s:
        per_day[d] = {"error": "not a trading day"}
        continue
    t0 = time.time()
    try:
        mt, ta, tp, tl, cs = get_tops_and_scores_cached(d)
        picks = _build_intersection_picks(ta, tp, tl, d, mt, cs, topn=None)
        dt = time.time() - t0
        if not picks:
            per_day[d] = {"n": 0, "elapsed_s": round(dt, 2)}
            continue
        fields_seen |= set(picks[0].keys())
        n = len(picks)
        # 字段覆盖率
        cov = {}
        for f in picks[0].keys():
            nn = sum(1 for p in picks if p.get(f) is not None and not (isinstance(p.get(f), float) and math.isnan(p.get(f))))
            cov[f] = round(nn / n, 3)
        # fwd 标签分布
        f5 = [num(p.get("fwd_max_5d")) for p in picks]
        f10 = [num(p.get("fwd_max_10d")) for p in picks]
        f5v = [x for x in f5 if x is not None]
        f10v = [x for x in f10 if x is not None]
        def rate(arr, th=20.0):
            return round(sum(1 for x in arr if x > th) / len(arr), 3) if arr else None
        per_day[d] = {
            "n": n,
            "elapsed_s": round(dt, 2),
            "n_strong_concepts": sum(1 for x in ta if x.get("is_strong")),
            "market_total_amount": mt,
            "cov": cov,
            "fwd_max_5d": {"n_valid": len(f5v), "mean": round(sum(f5v)/len(f5v),2) if f5v else None,
                           "p50": round(sorted(f5v)[len(f5v)//2],2) if f5v else None,
                           "hit20": rate(f5v)},
            "fwd_max_10d": {"n_valid": len(f10v), "mean": round(sum(f10v)/len(f10v),2) if f10v else None,
                            "p50": round(sorted(f10v)[len(f10v)//2],2) if f10v else None,
                            "hit20": rate(f10v)},
            "picks_field_keys": sorted(picks[0].keys()),
        }
    except Exception as e:
        per_day[d] = {"error": f"{type(e).__name__}: {e}"}

result["per_day"] = per_day
result["picks_fields_union"] = sorted(fields_seen)

OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print("DONE")
print("calendar:", result["calendar_first"], "~", result["calendar_last"], "n=", result["calendar_n"])
print("n_indicators:", result["n_indicators"], "types:", result["indicator_types"])
for d, v in per_day.items():
    if "error" in v:
        print(d, "ERR", v["error"])
    else:
        print(d, "n=", v["n"], "elapsed=", v["elapsed_s"], "hit20_5d=", v.get("fwd_max_5d",{}).get("hit20"),
              "hit20_10d=", v.get("fwd_max_10d",{}).get("hit20"), "strong=", v.get("n_strong_concepts"))
print("picks_fields:", result["picks_fields_union"])
