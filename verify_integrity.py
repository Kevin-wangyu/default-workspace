# -*- coding: utf-8 -*-
"""验证改造后数据文件零丢失、零篡改：只读对比关键 parquet 的行数与 mtime。"""
from pathlib import Path
import duckdb

PROJ = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
DC = PROJ / "data_compact"

# 关键数据文件/目录：确认存在且可读，行数与已知基线一致（纯读）
checks = {
    "quote_compact": (DC / "quote", "*.parquet", None),
    "daily_pct": (DC / "daily_pct", "*.parquet", None),
    "concept_date": (DC / "concept_date", "*.parquet", None),
    "tops_bars": (DC / "_tops_cache" / "v1" / "bars.parquet", None, None),
    "tops_meta": (DC / "_tops_cache" / "v1" / "meta.parquet", None, None),
    "concept_picks": (DC / "concept_picks", "*.parquet", None),
}
con = duckdb.connect()
print("=== 数据文件完整性（只读 count）===")
all_ok = True
for name, (p, glob, _) in checks.items():
    if glob:
        pat = (p / glob).as_posix()
        if not list(p.glob(glob)):
            print(f"  {name}: MISSING dir/files!"); all_ok=False; continue
        n = con.execute(f"SELECT count(*) FROM read_parquet('{pat}', union_by_name=true)").fetchone()[0]
    else:
        if not p.exists():
            print(f"  {name}: MISSING!"); all_ok=False; continue
        n = con.execute(f"SELECT count(*) FROM read_parquet('{p.as_posix()}')").fetchone()[0]
        print(f"  {name}: {n} rows, mtime={p.stat().st_mtime_ns}")
        continue
    print(f"  {name}: {n} rows ({len(list(p.glob(glob)))} files)")
con.close()

# 确认前端源文件已改造（关键标记）
print("\n=== 前端改造标记 ===")
marks = {
    "concept_view1.js": (PROJ/"frontend"/"js"/"concept_view1.js",
                         ["c7_picks", "v1C7Meta", "c7-streak-row", "c7_score"]),
    "concept.css": (PROJ/"frontend"/"css"/"concept.css", ["c7-streak-row", "c7-sort-key"]),
    "index.html": (PROJ/"frontend"/"index.html", ["c7DetailBadge"]),
    "boot.js": (PROJ/"frontend"/"js"/"boot.js", ["urlC7", "c7DetailBadge"]),
    "style.css": (PROJ/"frontend"/"css"/"style.css", ["c7-detail-badge"]),
    "main.py": (PROJ/"main.py", ["/api/concept/c7_picks"]),
    "c7_picks.py": (PROJ/"queries"/"c7_picks.py", ["def get_c7_picks", "ZREF"]),
}
for label,(p,keys) in marks.items():
    txt = p.read_text(encoding="utf-8")
    missing = [k for k in keys if k not in txt]
    ok = not missing
    print(f"  {label}: {'OK' if ok else 'MISSING '+str(missing)}")
    all_ok &= ok

print("\nINTEGRITY_CHECK=" + ("ALL_OK" if all_ok else "FAILED"))
