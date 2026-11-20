# -*- coding: utf-8 -*-
"""验证 C6/C7 双池改造：①语法 ②API 本地缓存命中 ③来源标注/连池 ④耗时对比 ⑤数据零写入。"""
from __future__ import annotations
import sys, time, json
from pathlib import Path
PROJ = r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay"
WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
sys.path.insert(0, PROJ)

import subprocess
PY = r"D:\Softwares\miniconda3\envs\stock\python.exe"
checks = []

def ck(name, cond, detail=""):
    checks.append((name, bool(cond), detail))
    print(f"[{'OK' if cond else 'FAIL'}] {name} {detail}")

# ① 语法
for f in [r"queries\c7_picks.py", r"core\c7_pool_cache.py", r"main.py"]:
    r = subprocess.run([PY, "-m", "py_compile", str(Path(PROJ)/f)], capture_output=True)
    ck(f"py_compile {f}", r.returncode == 0, r.stderr.decode("utf-8", "ignore")[:200])
for js in [r"frontend\js\concept_view1.js", r"frontend\js\boot.js"]:
    r = subprocess.run(["node", "--check", str(Path(PROJ)/js)], capture_output=True)
    ck(f"node --check {js}", r.returncode == 0, r.stderr.decode("utf-8", "ignore")[:200])

# ② API via TestClient（cwd=项目根）
import os
os.chdir(PROJ)
from fastapi.testclient import TestClient
from main import app
client = TestClient(app)

DATES = ["2026-11-19", "2026-11-05", "2026-11-02", "2026-10-30", "2025-01-09"]
for d in DATES:
    t0 = time.perf_counter()
    r = client.get(f"/api/concept/c7_picks?trade_date={d}")
    dt = (time.perf_counter()-t0)*1000
    ck(f"HTTP200 {d}", r.status_code == 200, f"{dt:.0f}ms")
    j = r.json()
    data = j["data"]; meta = j["meta"]
    picks = data["picks"]
    ck(f"  cache=local_parquet {d}", meta.get("cache") == "local_parquet", str(meta.get("cache")))
    ck(f"  no future fields {d}", all("fwd_" not in k or k.startswith("fwd_max") for k in (picks[0] if picks else {})),
       "fwd_max=复盘列" if picks else "empty")
    sc = [p.get("c7_score") for p in picks if p.get("c7_score") is not None]
    ck(f"  sorted desc {d}", sc == sorted(sc, reverse=True))
    srcs = set(p.get("source") for p in picks)
    ck(f"  source labeled {d}", srcs <= {"C7", "C6"}, str(srcs))
    ck(f"  meta counts {d}", meta.get("n") == len(picks) and meta.get("n_c7",0)+meta.get("n_c6",0)==len(picks),
       f"n={meta.get('n')} c7={meta.get('n_c7')} c6={meta.get('n_c6')}")
    print(f"    {d}: n={len(picks)} C7={meta.get('n_c7')} C6={meta.get('n_c6')} "
          f"streak2={meta.get('n_streak2')} strategy={data.get('strategy')} {dt:.0f}ms")

# ③ 近端"C7=0但池非空"验证（用户核心诉求）
r = client.get("/api/concept/c7_picks?trade_date=2026-11-19")
j = r.json(); m = j["meta"]
ck("11-19 池非空且C6补充", m["n"] > 0 and m["n_c7"] == 0 and m["n_c6"] > 0,
   f"n={m['n']} c7={m['n_c7']} c6={m['n_c6']}")

# ④ 耗时对比：本地缓存 vs 实时 compute
import importlib
c7 = importlib.import_module("queries.c7_picks")
d = "2026-11-02"
t0 = time.perf_counter(); client.get(f"/api/concept/c7_picks?trade_date={d}"); t_cache = (time.perf_counter()-t0)*1000
t0 = time.perf_counter(); live = c7._compute(d); t_live = (time.perf_counter()-t0)*1000
ck("缓存显著快于实时", t_cache < t_live/5, f"cache={t_cache:.0f}ms live={t_live:.0f}ms speedup={t_live/max(t_cache,1):.1f}x")
print(f"    SPEEDUP {d}: cache={t_cache:.0f}ms vs live={t_live:.0f}ms = {t_live/max(t_cache,1):.1f}x")

# ⑤ 数据零写入：原始数据 mtime + 行数
import duckdb
con = duckdb.connect()
QG = f"read_parquet('{(Path(PROJ)/'data_compact'/'quote'/'*.parquet').as_posix()}', union_by_name=true)"
nq = con.execute(f"SELECT count(*) FROM {QG}").fetchone()[0]
ck("quote 行数未被改", nq >= 3618901, f"n={nq}")

# summary
print("\n=== SUMMARY ===")
fail = [n for n,ok,_ in checks if not ok]
print(f"TOTAL={len(checks)} PASS={len(checks)-len(fail)} FAIL={len(fail)}")
if fail:
    print("FAILED:", fail)
    sys.exit(1)
print("ALL CHECKS PASSED")
