# -*- coding: utf-8 -*-
"""端到端验证：①concept_picks 更新已移除 ②c7_pool concepts 裁剪提速+口径一致 ③零删除。"""
import sys, re, time
from pathlib import Path
PROJ = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
sys.path.insert(0, str(PROJ))
import duckdb, pandas as pd, py_compile

results = []
def ck(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print("[%s] %s %s" % ("PASS" if ok else "FAIL", name, detail), flush=True)

# 1) py_compile 三改动模块
for mod in ["serve.py", "startup/archive.py", "core/c7_pool_rebuild.py"]:
    try:
        py_compile.compile(str(PROJ/mod), doraise=True); ck("py_compile "+mod, True)
    except Exception as e:
        ck("py_compile "+mod, False, str(e)[:120])

# 2) serve.py 不再含交集计算调用 / concept_picks 补最新日
serve_src = (PROJ/"serve.py").read_text(encoding="utf-8")
ck("serve 无 _build_intersection_picks 调用",
   "_build_intersection_picks(" not in serve_src)
ck("serve 无 picks 生成日志",
   "picks 已生成" not in serve_src)
ck("serve 保留 c7_pool 更新",
   "rebuild_c7_pool" in serve_src and "force_recent_days=0" in serve_src)

# 3) startup/archive.py 跳过 concept_picks
arch_src = (PROJ/"startup/archive.py").read_text(encoding="utf-8")
ck("archive 跳过 concept_picks", "skip_kinds" in arch_src and '"concept_picks"' in arch_src)

# 4) c7_pool_rebuild._pool_sql 已按 target_dates 裁剪 concepts
import core.c7_pool_rebuild as R
import inspect
sig = inspect.signature(R._pool_sql)
ck("_pool_sql 支持 target_dates_sql", "target_dates_sql" in str(sig))

# 5) 口径一致 + 提速：真实调 rebuild（dry_run=False 会写盘，用 target=最新日但先备份目录清单）
def run_pool_sql(win, tgt):
    con=duckdb.connect(); con.execute("SET threads=8")
    R._TMP.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory='{R._TMP.as_posix()}'")
    t0=time.time(); df=con.execute(R._pool_sql(win, tgt)).df(); dt=time.time()-t0
    con.close(); return df, dt

all_td = R._list_quote_dates()
idx=all_td.index(all_td[-1]); buffered=all_td[max(0,idx-30):]
win="("+",".join(f"'{d}'" for d in buffered)+")"
tgt="('"+all_td[-1]+"')"
# 基线：target=win（旧行为）  vs  修复：target=tgt
a,ta=run_pool_sql(win, win)
b,tb=run_pool_sql(win, tgt)
print("  耗时: 基线 %.2fs / 修复 %.2fs (加速 %.1fx)"%(ta,tb,ta/max(tb,0.01)),flush=True)
ck("提速≥3x", ta/max(tb,0.01)>=3, "%.1fx"%(ta/max(tb,0.01)))
t=all_td[-1]
aa=a[a.trade_date==t].sort_values('code').reset_index(drop=True)
bb=b[b.trade_date==t].sort_values('code').reset_index(drop=True)
ck("目标日行数一致", len(aa)==len(bb), "%d vs %d"%(len(aa),len(bb)))
num=[c for c in aa.columns if aa[c].dtype.kind in 'fi']
bad=[]
for col in num:
    x=pd.to_numeric(aa[col],errors='coerce'); y=pd.to_numeric(bb[col],errors='coerce')
    mx=(x-y).abs().max()
    if pd.notna(mx) and mx>1e-6: bad.append((col,float(mx)))
for col in ['code','name','matched_concepts','source']:
    if col in aa and col in bb:
        neq=(aa[col].fillna('').astype(str)!=bb[col].fillna('').astype(str)).sum()
        if neq: bad.append((col,int(neq)))
ck("24字段口径零差异", len(bad)==0, str(bad[:5]))

# 6) 零删除：c7_picks 分区数 / concept_picks 分区数（与已知基线比，只增不减）
c7 = list((PROJ/"data/c7_picks").glob("trade_date=*"))
cp = list((PROJ/"data/concept_picks").glob("trade_date=*"))
ck("c7_picks 分区≥647", len(c7)>=647, str(len(c7)))
ck("concept_picks 历史分区保留(>0)", len(cp)>0, str(len(cp)))

npass=sum(1 for _,ok,_ in results if ok)
print("\nTOTAL %d/%d %s"%(npass,len(results),"ALL PASSED" if npass==len(results) else "HAS FAIL"),flush=True)
