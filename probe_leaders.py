# -*- coding: utf-8 -*-
"""探查当日龙头概念（score>=0.8）数据源与数量。纯读。"""
import sys
sys.path.insert(0, r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
from core.tops_cache import get_tops_and_scores_cached as G

for d in ["2026-10-30","2026-05-08","2024-09-27","2025-02-10"]:
    try:
        mt,ta,tp,tl,cs = G(d)
    except Exception as e:
        print(f"[{d}] ERROR {e}"); continue
    leaders = sorted([(k, round(float(v.get('score',0)),4)) for k,v in cs.items()
                      if float(v.get('score',0))>=0.8], key=lambda x:-x[1])
    print(f"[{d}] 概念总数={len(cs)} 龙头(score>=0.8)={len(leaders)}")
    print(f"   TOP5: {leaders[:5]}")
print("\nSTRUCT sample:", list(cs.items())[:1])
