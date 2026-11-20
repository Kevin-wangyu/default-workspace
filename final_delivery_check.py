# -*- coding: utf-8 -*-
"""任务收尾闭环：核对全部落点存在 + 关键衔接行 + 数据零删除 + 文档非空。"""
import sys
from pathlib import Path
PROJ = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
ok = True
def chk(cond, msg):
    global ok
    print(("OK  " if cond else "FAIL") + " " + msg, flush=True)
    if not cond: ok = False

# 1) 新增/修改落点存在
for rel in ["core/c7_pool_rebuild.py", "core/c7_pool_cache.py", "queries/c7_picks.py",
            "config.py", "serve.py", "scripts/archive_month.py",
            "scripts/check_backup.py", "scripts/prepare_compact_sync.py",
            "PROJECT/PROJECT v5.md"]:
    chk((PROJ/rel).exists(), "落点存在: " + rel)

# 2) 关键衔接行
cfg = (PROJ/"config.py").read_text(encoding="utf-8")
chk("C7_POOL_DIR" in cfg, "config.py 含 C7_POOL_DIR")
srv = (PROJ/"serve.py").read_text(encoding="utf-8")
chk("rebuild_c7_pool" in srv and "C7_POOL_DIR" in srv, "serve.py 已接入 rebuild_c7_pool")
arc = (PROJ/"scripts/archive_month.py").read_text(encoding="utf-8")
chk('"c7_picks"' in arc and "C7_POOL_DIR" in arc, "archive_month.py KINDS 含 c7_picks")
bk = (PROJ/"scripts/check_backup.py").read_text(encoding="utf-8")
chk("c7_picks" in bk and "C7_POOL_DIR" in bk, "check_backup.py 含 c7_picks 覆盖")
rbl = (PROJ/"core/c7_pool_rebuild.py").read_text(encoding="utf-8")
chk("def rebuild_c7_pool" in rbl and "dry_run" in rbl, "rebuild 接口+dry_run 就位")

# 3) v5 文档非空、章节齐
doc = (PROJ/"PROJECT/PROJECT v5.md").read_text(encoding="utf-8")
chk(len(doc) > 6000, "v5 文档正文 %d 字符" % len(doc))
for sec in ["变更总览", "项目结构", "serve", "月合并", "data_compact_sync", "验证证据", "策略池口径", "历史文档"]:
    chk(sec in doc, "v5 含章节: " + sec)
chk("178.5s" in doc and "779.6s" in doc, "v5 如实披露两种耗时口径")

# 4) 数据零删除：日分区/月文件数量不减
import duckdb
con = duckdb.connect()
for name, glob in [("日分区", str(PROJ/"data/c7_picks/trade_date=*/part.parquet")),
                   ("月合并", str(PROJ/"data_compact/c7_picks/*.parquet")),
                   ("sync镜像", str(PROJ/"data_compact_sync/c7_picks/*.parquet"))]:
    n = con.execute("SELECT count(*) FROM read_parquet(?, hive_partitioning=true)", [glob]).fetchone()[0] if "日分区" in name else con.execute("SELECT count(*) FROM read_parquet(?)", [glob]).fetchone()[0]
    chk(n >= 33 if name != "日分区" else n >= 647, "%s 数量 %d" % (name, n))
con.close()

print("FINAL_DELIVERY_CHECK=" + ("ALL_OK" if ok else "HAS_FAILURE"), flush=True)
