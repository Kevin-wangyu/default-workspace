# -*- coding: utf-8 -*-
"""后台一次性预计算 C6/C7 合并池 → 按日本地化 parquet 缓存。

参照 data/concept_picks 的做法：大量运算一次性完成，页面渲染只按日查询。
输出目录：data/c7_picks/trade_date=YYYY-MM-DD/part.parquet（新增独立目录，
不触碰任何原始 parquet 数据）。

用法：
  python prebuild_c7_pool.py --from-snapshot   # 从已验证的全量快照落地（本次）
  python prebuild_c7_pool.py --full            # 全量重算（可复现，首次/数据大更新时用）
  python prebuild_c7_pool.py --recent 15       # 增量重算近 N 天（日常数据推进后）
"""
from __future__ import annotations
import argparse, sys, time
from pathlib import Path
import pandas as pd

PROJ = r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay"
WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
sys.path.insert(0, PROJ)
from config import DATA_DIR

CACHE = DATA_DIR / "c7_picks"
SNAP = WS / "_prebuild_verify.parquet"

COLS = [
    "trade_date","code","name","source","close","pct_change","turnover_rate",
    "vol20","ret_5d","lu_cnt_20d","main_net_norm","n_leader_concepts","lu_gap",
    "close_hh20_ratio","ma5","ma20","ma60","streak_days","c7_score",
    "matched_concepts","n_concepts","fwd_max_5d","fwd_max_10d","is_streak2",
]


def write_daily(df: pd.DataFrame) -> tuple[int, int]:
    """按 trade_date 分区写 parquet（每目录 part.parquet）。返回 (天数, 行数)。"""
    CACHE.mkdir(parents=True, exist_ok=True)
    cols = [c for c in COLS if c in df.columns]
    d = df[cols].copy()
    nd = d.trade_date.nunique()
    for dt, g in d.groupby("trade_date", sort=False):
        out = CACHE / f"trade_date={dt}" / "part.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        g.to_parquet(out, index=False)
    return nd, len(d)


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    if "is_streak2" not in df.columns:
        df = df.copy()
        df["is_streak2"] = df["streak_days"].fillna(1) >= 2
    if "matched_concepts" in df.columns:
        df["matched_concepts"] = df["matched_concepts"].apply(
            lambda x: x.split(";") if isinstance(x, str) else (x or []))
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-snapshot", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--recent", type=int, default=0)
    a = ap.parse_args()
    t0 = time.time()
    if a.from_snapshot:
        df = pd.read_parquet(SNAP)
        df = _enrich(df)
        nd, nr = write_daily(df)
        print(f"FROM_SNAPSHOT days={nd} rows={nr} seconds={time.time()-t0:.1f}")
    elif a.full:
        # 全量重算：直接调用验证脚本的 SQL（口径已逐股验证）
        import prebuild_c7_verify as v
        con = __import__("duckdb").connect(); con.execute("SET threads=8")
        con.execute(f"SET temp_directory='{(WS/'_duckdb_tmp').as_posix()}'")
        df = con.execute(v.SQL).df()
        df = _enrich(df)
        nd, nr = write_daily(df)
        print(f"FULL days={nd} rows={nr} seconds={time.time()-t0:.1f}")
    elif a.recent > 0:
        # 增量：对最近 N 个交易日逐日调用实时 _compute（含 fwd 补全），再补 C6
        # 用快照里的 C6-only 行 + 实时 C7 合并，简化为：重算近端日期的完整池需全量 SQL 过滤
        print("RECENT incremental: use --full for now (recent rebuild = full recompute)")
        import prebuild_c7_verify as v
        con = __import__("duckdb").connect(); con.execute("SET threads=8")
        con.execute(f"SET temp_directory='{(WS/'_duckdb_tmp').as_posix()}'")
        df = con.execute(v.SQL).df()
        df = _enrich(df)
        nd, nr = write_daily(df)
        print(f"FULL_AS_FALLBACK days={nd} rows={nr} seconds={time.time()-t0:.1f}")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
