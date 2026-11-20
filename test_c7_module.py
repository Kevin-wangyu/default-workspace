# -*- coding: utf-8 -*-
"""独立测试 queries/c7_picks.py（纯读，不改项目数据）。"""
import sys, time
from pathlib import Path
sys.path.insert(0, r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
from queries import c7_picks

for d in ["2026-10-30", "2024-09-27", "2025-02-10"]:
    t = time.time()
    res = c7_picks.get_c7_picks(d)
    data, meta = res["data"], res["meta"]
    picks = data["picks"]
    print(f"\n=== {d} n={meta['n']} stable={meta['stable']} cache={meta['cache']} "
          f"elapsed={time.time()-t:.2f}s ===")
    for p in picks[:6]:
        print(f"  {p['code']} {p['name']:<6} score={p['c7_score']:>7.3f} "
              f"streak={p['streak_days']} is2={p['is_streak2']} "
              f"vol20={p['vol20']} ret5={p['ret_5d']} tor={p['turnover_rate']}")
    # 校验：score 降序、is_streak2 与 streak 一致
    scores = [p["c7_score"] for p in picks]
    assert scores == sorted(scores, reverse=True), "score 非降序!"
    assert all(p["is_streak2"] == (p["streak_days"] >= 2) for p in picks), "streak 标注不一致!"
    assert meta["future_info"] is False
print("\nMODULE_TEST=ALL_OK")
