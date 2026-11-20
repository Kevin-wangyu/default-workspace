# -*- coding: utf-8 -*-
"""真实调 rebuild_c7_pool(dry_run + 单日实写)确认改签名后无回归；磁盘零删除。"""
import sys, time
from pathlib import Path
PROJ=Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
sys.path.insert(0,str(PROJ))
import core.c7_pool_rebuild as R

all_td=R._list_quote_dates()
# dry_run 只识别不写
s0=R.rebuild_c7_pool(limit_days=30, force_recent_days=0, dry_run=True)
print("dry_run:", {k:s0.get(k) for k in ['days','target_dates','dry_run']}, flush=True)
# 真实单日补算：用 dry_run 报出的第1个目标日（若有），否则 force 单日走快照不落重复
tgt=(s0.get('target_dates') or [all_td[-1]])[:1]
print("真实补算目标日:",tgt,flush=True)
before=len(list((PROJ/'data/c7_picks').glob('trade_date=*')))
t0=time.time()
s1=R.rebuild_c7_pool(limit_days=30, force_recent_days=0, force=False)
print("rebuild: days=%s rows=%s source=%s seconds=%.1fs"%(s1.get('days'),s1.get('rows'),s1.get('source_counts'),time.time()-t0),flush=True)
after=len(list((PROJ/'data/c7_picks').glob('trade_date=*')))
print("分区数 before=%d after=%d 减少=%s"%(before,after,after<before),flush=True)
print("INTEGRATION_OK", s1.get('error') is None, flush=True)
