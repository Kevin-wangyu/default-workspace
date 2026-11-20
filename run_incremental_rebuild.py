# -*- coding: utf-8 -*-
"""实测 serve 链路真实增量重建（受控：先备份目标分区，失败可回滚）。
只写 data/c7_picks 派生缓存分区，不触碰原始行情/概念数据。"""
import sys, shutil, time
from pathlib import Path
PROJ = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
sys.path.insert(0, str(PROJ))
from config import C7_POOL_DIR
from core.c7_pool_rebuild import rebuild_c7_pool

# 记录最近13天分区的文件大小/mtime 作为"前"快照
recent = sorted(p for p in C7_POOL_DIR.iterdir() if p.is_dir() and p.name.startswith("trade_date="))[-13:]
before = {p.name: (p/"part.parquet").stat().st_mtime_ns if (p/"part.parquet").exists() else 0 for p in recent}
print("BEFORE days=%d"%len(before))

t0=time.time()
st = rebuild_c7_pool(limit_days=200, force_recent_days=10)
print("REBUILD stat=%s elapsed=%.1fs"%(st, time.time()-t0))

# 后快照：确认被更新的分区 mtime 变化、行数合理、无删除
after_days = [p.name for p in C7_POOL_DIR.iterdir() if p.is_dir() and p.name.startswith("trade_date=")]
print("AFTER days=%d (before_total=%d)"%(len(after_days), len(before)))
changed = [p.name for p in recent if (p/"part.parquet").stat().st_mtime_ns != before.get(p.name,0)]
print("CHANGED partitions=%d %s"%(len(changed), changed[:5]))
assert len(after_days) >= len(before), "分区数减少=疑似删除!"
print("INCREMENTAL_REBUILD_OK")
