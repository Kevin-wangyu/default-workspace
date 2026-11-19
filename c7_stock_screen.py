# -*- coding: utf-8 -*-
"""
================================================================================
C7 最佳推荐条件 —— 可操作选股筛选代码
================================================================================
用途：给定任意交易日，筛出同时满足"情绪 + 资金/筹码集中 + 高波动 + 动量 +
      多头排列 + 龙头概念"的 C7 组合标的，并输出每只股票的指标明细。

C7 完整条件（全部 T 日收盘后可知，无任何未来数据/前视）：
  1) lu_cnt_20d       >= 1        近20日至少1次涨停（情绪/主力参与）
  2) main_net_norm    >  0        主力净额/成交额为正（资金聚集）
  3) vol20            >= 3.5238   20日波动率处于高分位（高波动，train q70）
  4) turnover_rate    >= 3.7      当日换手率（活跃度，train q60）
  5) lu_gap           >= -3       当日涨幅距涨停不大于3个点（逼近日高/强势）
  6) close_hh20_ratio >= 0.95     收盘价在近20日高点95%以上（趋势向上）
  7) ret_5d           >= 4.8679   近5日涨幅（短期动量，train q80）
  8) ma5 > ma20 > ma60            多头排列（趋势）
  9) n_leader_concepts >= 1       命中至少1个龙头概念（score>=0.8，资金聚集）

阈值来源：train(2024-02~2025-12) 分位数，详见因子增量归因研究报告。

用法（Python 3.11+，需 duckdb/pandas/pyarrow）：
  python c7_stock_screen.py --date 2026-10-30
  python c7_stock_screen.py --date 2026-10-30 --live      # 从项目原始 parquet 实时重算
  python c7_stock_screen.py --date 2026-10-30 --json out.json
  python c7_stock_screen.py --verify 2024-09-27 2025-02-10 2026-10-30   # 双模式一致性核验

说明：本脚本只读项目数据，绝不写入投研项目任何文件；输出仅落在工作目录或 stdout。
================================================================================
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import duckdb

PROJ = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
WS   = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
MATRIX = WS / "research_matrix.parquet"

# ---------------- C7 阈值（train 分位，集中在此处便于调整） ----------------
THR = dict(
    lu_cnt_20d        = 1.0,
    main_net_norm     = 0.0,
    vol20             = 3.5238,
    turnover_rate     = 3.7,
    lu_gap            = -3.0,
    close_hh20_ratio  = 0.95,
    ret_5d            = 4.8679,
    n_leader_concepts = 1.0,
)

def _p(*parts):
    return str(Path(PROJ, *parts)).replace("\\", "/")

def _where():
    """返回 SQL WHERE 片段（C7 全部条件）。"""
    t = THR
    return f"""
      lu_cnt_20d >= {t['lu_cnt_20d']}
      AND main_net_norm > {t['main_net_norm']}
      AND vol20 >= {t['vol20']}
      AND turnover_rate >= {t['turnover_rate']}
      AND lu_gap >= {t['lu_gap']}
      AND close_hh20_ratio >= {t['close_hh20_ratio']}
      AND ret_5d >= {t['ret_5d']}
      AND ma5 > ma20 AND ma20 > ma60
      AND n_leader_concepts >= {t['n_leader_concepts']}
    """

OUT_COLS = """code, name, trade_date, lu_cnt_20d, main_net_norm, vol20, turnover_rate,
              lu_gap, close_hh20_ratio, ret_5d, ma5, ma20, ma60, n_leader_concepts,
              pct_change, amount"""

# ============================================================================
# 模式 A：从已验证的特征矩阵筛选（快速，口径与报告完全一致）
# ============================================================================
def screen_matrix(con, date: str):
    sql = f"""SELECT {OUT_COLS}
              FROM read_parquet('{MATRIX.as_posix()}')
              WHERE trade_date = '{date}' AND {_where()}
              ORDER BY main_net_norm DESC"""
    return con.execute(sql).df()

# ============================================================================
# 模式 B：从项目原始 parquet 实时重算全部特征后筛选（可脱离中间文件部署）
# ============================================================================
def screen_live(con, date: str):
    QG = f"read_parquet('{_p('data_compact','quote','*.parquet')}', union_by_name=true)"
    DG = f"read_parquet('{_p('data_compact','daily_pct','*.parquet')}', union_by_name=true)"
    CG = f"read_parquet('{_p('data_compact','concept_date','*.parquet')}', union_by_name=true)"
    BARS = f"read_parquet('{_p('data_compact','_tops_cache','v1','bars.parquet')}')"
    META = f"read_parquet('{_p('data_compact','_tops_cache','v1','meta.parquet')}')"
    sql = f"""
    WITH
    qx AS (
      SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, code, name, close, high,
             amount, turnover_rate, pct_change,
             huge_order_net, big_order_net
      FROM {QG}
    ),
    dx AS (
      SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, code,
             CASE WHEN isfinite(pct_change) THEN pct_change END AS pct_change
      FROM {DG}
    ),
    cal AS (SELECT d, row_number() OVER (ORDER BY d) AS di
            FROM (SELECT DISTINCT d FROM qx)),
    base AS (
      SELECT q.*, c.di, d.pct_change AS daily_pct,
        CASE WHEN left(q.code,2) IN ('30','68') THEN 19.8
             WHEN left(q.code,1) IN ('8','4') OR left(q.code,2)='92' THEN 29.8
             ELSE 9.8 END AS lu_thr
      FROM qx q JOIN cal c USING (d)
      LEFT JOIN dx d ON q.d=d.d AND q.code=d.code
    ),
    st AS (
      SELECT b.*,
        avg(close) OVER w5  AS ma5,
        avg(close) OVER w20 AS ma20,
        avg(close) OVER w60 AS ma60,
        stddev_samp(daily_pct) OVER w20 AS vol20,
        max(high) OVER w20 AS hh20,
        lag(close,5) OVER wc AS close_5d_ago,
        sum(CASE WHEN daily_pct >= lu_thr-0.15 AND daily_pct IS NOT NULL THEN 1 ELSE 0 END)
            OVER w20 AS lu_cnt_20d
      FROM base b
      WINDOW wc AS (PARTITION BY code ORDER BY di),
             w5  AS (PARTITION BY code ORDER BY di ROWS BETWEEN 4  PRECEDING AND CURRENT ROW),
             w20 AS (PARTITION BY code ORDER BY di ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),
             w60 AS (PARTITION BY code ORDER BY di ROWS BETWEEN 59 PRECEDING AND CURRENT ROW)
    ),
    cdx AS (
      SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, code, trim(t.x) AS cname
      FROM {CG}, unnest(string_split(concepts,';')) AS t(x)
    ),
    sc AS (
      SELECT substr(CAST(trade_date AS VARCHAR),1,10) AS d, concept_name AS cname,
             max(score) AS score FROM {META} WHERE row_type='score' GROUP BY 1,2
    ),
    lead AS (
      SELECT x.d, x.code, count(DISTINCT x.cname) FILTER (WHERE s.score>=0.8) AS n_leader_concepts
      FROM cdx x LEFT JOIN sc s ON x.d=s.d AND x.cname=s.cname
      GROUP BY x.d, x.code
    ),
    feat AS (
      -- 口径对齐 PROJECT v4.md：涨跌幅/涨停缺口统一用 daily_pct（前复权自算），
      -- 禁用 quote 原始 pct_change（东财口径在除权日不一致）。
      SELECT st.d AS trade_date, st.code, st.name, st.daily_pct AS pct_change, st.amount,
        st.lu_cnt_20d,
        (coalesce(st.huge_order_net,0)+coalesce(st.big_order_net,0))/NULLIF(st.amount,0) AS main_net_norm,
        st.vol20, st.turnover_rate,
        st.daily_pct - st.lu_thr AS lu_gap,
        st.close/NULLIF(st.hh20,0) AS close_hh20_ratio,
        (st.close/NULLIF(st.close_5d_ago,0)-1)*100 AS ret_5d,
        st.ma5, st.ma20, st.ma60,
        coalesce(ld.n_leader_concepts,0) AS n_leader_concepts
      FROM st LEFT JOIN lead ld ON st.d=ld.d AND st.code=ld.code
    )
    SELECT {OUT_COLS}
    FROM feat
    WHERE trade_date = '{date}' AND {_where()}
    ORDER BY main_net_norm DESC
    """
    return con.execute(sql).df()

def _to_records(df):
    d = df.copy()
    for c in d.columns:
        if c not in ("code","name","trade_date"):
            d[c] = d[c].round(4)
    return d.to_dict("records")

def main():
    ap = argparse.ArgumentParser(description="C7 最佳条件选股筛选")
    ap.add_argument("--date", help="交易日 YYYY-MM-DD")
    ap.add_argument("--live", action="store_true", help="从项目原始 parquet 实时重算（默认读特征矩阵）")
    ap.add_argument("--json", help="结果另存 JSON 路径（工作目录）")
    ap.add_argument("--verify", nargs="+", help="对多个日期核验 matrix/live 两模式一致性")
    a = ap.parse_args()
    con = duckdb.connect(); con.execute("SET threads=8")

    if a.verify:
        print("=== 双模式一致性核验（matrix vs live）===")
        allok = True
        for d in a.verify:
            dm = screen_matrix(con, d); dl = screen_live(con, d)
            sm = set(dm["code"]); sl = set(dl["code"])
            ok = (sm == sl)
            allok &= ok
            print(f"{d}: matrix_n={len(dm)} live_n={len(dl)} codes_identical={ok} "
                  f"only_matrix={sorted(sm-sl)[:5]} only_live={sorted(sl-sm)[:5]}")
        print("VERIFY_RESULT:", "ALL_OK" if allok else "MISMATCH")
        return

    if not a.date:
        print("请提供 --date YYYY-MM-DD 或使用 --verify", file=sys.stderr); sys.exit(2)

    df = screen_live(con, a.date) if a.live else screen_matrix(con, a.date)
    res = {"date": a.date, "mode": "live" if a.live else "matrix",
           "thresholds": THR, "n_selected": len(df), "picks": _to_records(df)}
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if a.json:
        p = Path(a.json)
        if not p.is_absolute(): p = WS / p
        p.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[saved] {p}", file=sys.stderr)

if __name__ == "__main__":
    main()
