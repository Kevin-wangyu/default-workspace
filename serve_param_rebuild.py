# -*- coding: utf-8 -*-
"""按 serve 真实默认参数实测增量重建耗时（dry_run + 真实），unbuffered 输出。"""
import sys, time
from pathlib import Path
PROJ = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
sys.path.insert(0, str(PROJ))
from core.c7_pool_rebuild import rebuild_c7_pool

# serve.py: force_days=max(3, default check_missing_days=5)=5
#   limit_days=max(30,5)=30 ; force_recent_days=max(10,5)=10
print("=== serve default params: limit_days=30, force_recent_days=10 ===", flush=True)
dry = rebuild_c7_pool(limit_days=30, force_recent_days=10, dry_run=True)
print("DRY stat=%s" % dry, flush=True)
t0 = time.time()
st = rebuild_c7_pool(limit_days=30, force_recent_days=10)
print("REBUILD stat=%s elapsed=%.1fs" % (st, time.time() - t0), flush=True)
print("SERVE_PARAM_REBUILD_OK", flush=True)
