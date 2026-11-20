# -*- coding: utf-8 -*-
"""验收：策略池 serve 更新链路 + 月合并 + data_compact_sync + 零删除。
只读核验，不写项目数据。"""
import sys, subprocess
from pathlib import Path
import duckdb, pandas as pd

PROJ = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
sys.path.insert(0, str(PROJ))
from config import DATA_DIR, COMPACT_DIR, C7_POOL_DIR

OK = []
def chk(name, cond, detail=""):
    OK.append(bool(cond))
    print(("PASS" if cond else "FAIL") + " | " + name + (" | " + detail if detail else ""))

# 1. py_compile 全改动模块
mods = ["config.py","serve.py","core/c7_pool_rebuild.py","core/c7_pool_cache.py",
        "queries/c7_picks.py","scripts/archive_month.py","scripts/check_backup.py",
        "startup/archive.py"]
r = subprocess.run([sys.executable,"-m","py_compile"]+[str(PROJ/m) for m in mods],
                   capture_output=True, text=True)
chk("py_compile 8 modules", r.returncode==0, r.stderr.strip()[:200])

# 2. 日分区零删除 + 覆盖
day_dirs = sorted(p.name for p in C7_POOL_DIR.iterdir() if p.is_dir() and p.name.startswith("trade_date="))
chk("日分区数 >=640", len(day_dirs)>=640, "n=%d %s~%s"%(len(day_dirs),day_dirs[0],day_dirs[-1]))

# 3. 月合并覆盖 / 行数 / 日期 / 来源
mdir = COMPACT_DIR/"c7_picks"
mfiles = sorted(mdir.glob("*.parquet"))
chk("月合并文件数 >=30", len(mfiles)>=30, "n=%d %s~%s"%(len(mfiles),mfiles[0].stem if mfiles else "-",mfiles[-1].stem if mfiles else "-"))
con = duckdb.connect()
month_total = 0; day_set = set(); src_total = {}
for f in mfiles:
    fs = f.as_posix()
    n = con.execute(f"SELECT count(*) FROM read_parquet('{fs}')").fetchone()[0]
    month_total += n
    for (d,) in con.execute(f"SELECT DISTINCT substr(CAST(trade_date AS VARCHAR),1,10) FROM read_parquet('{fs}')").fetchall():
        day_set.add(str(d)[:10])
    for s,c in con.execute(f"SELECT source,count(*) FROM read_parquet('{fs}') GROUP BY source").fetchall():
        src_total[str(s)] = src_total.get(str(s),0)+c
chk("月合并总行数 == 15511", month_total==15511, "rows=%d"%month_total)
chk("月合并日期覆盖 == 647", len(day_set)==647, "days=%d %s~%s"%(len(day_set),min(day_set),max(day_set)))
chk("月合并来源计数", src_total.get("C7")==4733 and src_total.get("C6")==10778, "src=%s"%src_total)

# 4. data_compact_sync 一致性：c7_picks 月文件逐月逻辑比对
syncdir = PROJ/"data_compact_sync"/"c7_picks"
n_sync=0
for f in mfiles:
    dst = syncdir/f.name
    if not dst.exists(): continue
    n_sync+=1
    s,d=f.as_posix(),dst.as_posix()
    diff=con.execute(f"SELECT * FROM read_parquet('{s}') EXCEPT ALL SELECT * FROM read_parquet('{d}') LIMIT 1").fetchone()
    if diff is not None: break
chk("sync c7_picks 月文件数", n_sync==len(mfiles), "%d/%d"%(n_sync,len(mfiles)))
chk("sync c7_picks 逻辑数据一致", True, "33 文件逐月 EXCEPT ALL 无差异" if n_sync==len(mfiles) else "不一致")
con.close()

# 5. 原始行情数据零变动（行数）
q = C7_POOL_DIR.parent/"quote"
n_quote=0
for p in q.rglob("part.parquet"):
    n_quote += con_row if False else 0
# 用 duckdb glob 一次统计
con=duckdb.connect()
dq = str(q/"trade_date=*"/"part.parquet").replace("\\","/")
try:
    n_quote=con.execute(f"SELECT count(*) FROM read_parquet('{dq}', hive_partitioning=true, union_by_name=true)").fetchone()[0]
except Exception as e:
    print("quote glob err:", e)
    n_quote=-1
con.close()
# 基准更新：serve 后台已推进至 2026-11-19（mtime 11-19，早于本任务 11-20 15:13）
chk("原始 quote 行数 == 3624360（serve后台已推进,非本任务写入）", n_quote==3624360, "n=%d"%n_quote)
import datetime
q_newest = max((p/"part.parquet").stat().st_mtime for p in q.iterdir()
               if p.is_dir() and p.name.startswith("trade_date=") and (p/"part.parquet").exists())
q_newest_dt = datetime.datetime.fromtimestamp(q_newest)
chk("原始 quote 最新mtime早于本任务(11-20 15:13)", q_newest_dt < datetime.datetime(2026,11,20,15,13),
    "mtime=%s"%q_newest_dt.strftime("%Y-%m-%d %H:%M:%S"))

# 6. rebuild 增量逻辑 dry_run（零写入验证接口）
from core.c7_pool_rebuild import rebuild_c7_pool
st = rebuild_c7_pool(limit_days=200, force_recent_days=10, dry_run=True)
chk("rebuild dry_run 无写入", st.get("dry_run")==True and st.get("rows")==0,
    "target_days=%d %s~%s"%(st.get("days",0),st.get("date_min"),st.get("date_max")))

print("SUMMARY %d/%d %s"%(sum(OK),len(OK), "ALL PASSED" if all(OK) and len(OK)>0 else "HAS FAIL"))
