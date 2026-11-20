# -*- coding: utf-8 -*-
"""对齐线上日志场景：buffer=81 日 / 1036行 / 44.4s，复测修复前后。"""
import sys, time
from pathlib import Path
PROJ=Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
sys.path.insert(0,str(PROJ))
import duckdb
import core.c7_pool_rebuild as R

all_td=R._list_quote_dates(); idx=all_td.index(all_td[-1])
for bd in [81]:
    buffered=all_td[max(0,idx-bd):]
    win="("+",".join(f"'{d}'" for d in buffered)+")"
    tgt="('"+all_td[-1]+"')"
    for label, ts in [("修复前(全窗口concepts)",win),("修复后(concepts裁目标日)",tgt)]:
        con=duckdb.connect(); con.execute("SET threads=8")
        R._TMP.mkdir(parents=True,exist_ok=True)
        con.execute(f"SET temp_directory='{R._TMP.as_posix()}'")
        t0=time.time(); df=con.execute(R._pool_sql(win,ts)).df(); dt=time.time()-t0
        con.close()
        print("buffer=%d %-24s : %6.2fs rows=%d"%(bd,label,dt,len(df)),flush=True)
