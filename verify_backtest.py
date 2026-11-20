# -*- coding: utf-8 -*-
"""独立核验回测结果：从逐笔明细CSV重算全部指标，与backtest_out.json逐项比对。
不调用 backtest_strategy 的任何函数——独立实现，证明数字可追溯。"""
from __future__ import annotations
import json, math
from pathlib import Path
import pandas as pd, numpy as np

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
OUT = json.loads((WS / "backtest_out.json").read_text(encoding="utf-8"))
COST = OUT["config"]["cost"]
DETAILS = {
    "C7单池": WS / "backtest_detail_c7.csv",
    "C6+C7双池": WS / "backtest_detail_dual.csv",
}

checks = []
def ck(name, got, exp, tol=1e-4):
    ok = (got is not None and exp is not None and abs(float(got) - float(exp)) <= tol) \
         or (got is None and exp is None)
    checks.append((name, got, exp, ok))

def recalc(d: pd.DataFrame) -> dict:
    """独立指标实现（与引擎 metrics 无共用代码）。
    mfe 从最原始 OHLC(h1..hN, fill_px) 重算，不用CSV里存好的mfe7/mfe10列——
    绕开浮点序列化在20.0边界的±1样本翻转，做到真正溯源。"""
    sig = len(d)
    fl = d[d["filled"] == True]
    r = fl["ret"].dropna().astype(float)
    nf = len(fl)
    gp = float(r[r > 0].sum()); gl = float(abs(r[r < 0].sum()))
    def R(x, n=4): return round(float(x), n) if x is not None and not (isinstance(x,float) and math.isnan(x)) else None
    # 从原始高价/成交价独立重算 MFE
    if nf:
        fp = fl["fill_px"].values.astype(float)
        H7 = np.array([fl[f"h{k}"].values.astype(float) for k in range(1, 8)])
        H10 = np.array([fl[f"h{k}"].values.astype(float) for k in range(1, 11)])
        mfe7 = (np.max(H7, axis=0) / fp - 1) * 100
        mfe10 = (np.max(H10, axis=0) / fp - 1) * 100
    else:
        mfe7 = mfe10 = np.array([])
    return dict(
        n_signals=sig, n_filled=nf,
        fill_rate=R(nf/sig*100,2) if sig else None,
        avg_ret=R(r.mean()) if nf else None,
        avg_ret_net=R(r.mean()-COST) if nf else None,
        win_rate=R((r>0).mean()*100,2) if nf else None,
        profit_factor=R(gp/gl,3) if gl>0 else None,
        avg_win=R(r[r>0].mean(),3) if (r>0).any() else None,
        avg_loss=R(r[r<0].mean(),3) if (r<0).any() else None,
        mfe20_hold7=R((mfe7>=20).mean()*100,2) if nf else None,
        mfe20_10d=R((mfe10>=20).mean()*100,2) if nf else None,
        mae_mean=R(fl["mae7"].mean(),3) if nf else None,
        exit_TP=R((fl["reason"]=="TP").mean()*100,2) if nf else None,
        exit_SL=R((fl["reason"]=="SL").mean()*100,2) if nf else None,
        exit_TIME=R((fl["reason"]=="TIME").mean()*100,2) if nf else None,
        n_streak2=R((fl["streak6"]>=2).mean()*100,2) if nf else None,
    )

NUM_KEYS = ["n_signals","n_filled","fill_rate","avg_ret","avg_ret_net","win_rate",
            "profit_factor","avg_win","avg_loss","mfe20_hold7","mfe20_10d","mae_mean",
            "exit_TP","exit_SL","exit_TIME","n_streak2"]

for gname, path in DETAILS.items():
    d = pd.read_csv(path, encoding="utf-8-sig")
    segs = {"全区间": d, "train": d[d["split"]=="train"], "oos": d[d["split"]=="oos"]}
    for seg, dd in segs.items():
        got = recalc(dd)
        exp = OUT["groups"][gname][seg]
        for k in NUM_KEYS:
            ck(f"{gname}/{seg}/{k}", got[k], exp[k],
               tol=0 if k in ("n_signals","n_filled") else 1e-3)
    # aux
    base = d[d["filled"].astype(bool)]
    parts = []
    for di, g in base.groupby("di"):
        k = max(1, int(len(g)*0.5))
        parts.append(g.nlargest(k, "score"))
    top = pd.concat(parts) if parts else base.iloc[0:0]
    a = OUT["aux"][gname]
    ck(f"{gname}/aux/top50_n", len(top), a["top50_n"], 0)
    ck(f"{gname}/aux/top50_avg_ret", round(float(top["ret"].mean()),4), a["top50_avg_ret"], 1e-3)
    ck(f"{gname}/aux/all_avg_ret", round(float(base["ret"].mean()),4), a["all_avg_ret"], 1e-3)
    for sname, sub in [("streak2", base[base["streak6"]>=2]), ("streak1", base[base["streak6"]==1])]:
        rr = recalc(sub)
        for k in ["n_signals","n_filled","avg_ret","avg_ret_net","win_rate","profit_factor"]:
            ck(f"{gname}/aux/{sname}/{k}", rr[k], a[sname][k],
               0 if k in ("n_signals","n_filled") else 1e-3)

# 方案原文吻合（C7单池 train/oos 期望/胜率/PF）
PLAN = [("C7单池/train/avg_ret",1.07,0.01), ("C7单池/train/win_rate",42.0,0.05),
        ("C7单池/train/profit_factor",1.249,0.001),
        ("C7单池/oos/avg_ret",0.32,0.01), ("C7单池/oos/win_rate",37.5,0.05),
        ("C7单池/oos/profit_factor",1.068,0.001)]
for key, exp, tol in PLAN:
    g,s,k = key.split("/")
    ck(f"方案吻合/{key}", OUT["groups"][g][s][k], exp, tol)

npass = sum(1 for *_, ok in checks if ok); ntot = len(checks)
print(f"独立重算核验: {npass}/{ntot} PASSED")
for name, got, exp, ok in checks:
    if not ok:
        print(f"  FAIL {name}: got={got} exp={exp}")
print("VERIFY_BACKTEST=" + ("ALL_OK" if npass==ntot else "HAS_FAIL"))
