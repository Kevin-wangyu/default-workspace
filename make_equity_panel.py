# -*- coding: utf-8 -*-
"""收益率板面：从逐笔明细构造资产曲线（起始=1）。

口径（严格只用两份逐笔明细 + 汇总JSON，不引入任何外部数据/参数）：
  - 方案未定义资金分配/仓位/同时持仓数 => 真实账户净值曲线、年化、最大回撤、夏普
    **不可得**（无法由逐笔明细唯一确定每日仓位），不用替代值填充。
  - 可严格推导的示意口径：把总资金等分为 M 份（M=该池全区间成交笔数），
    每笔成交占 1 份，单笔收益 ret_i 线性累加、不复利；收益按信号日 T 归属（规则2.2）。
      A_t = 1 + (1/M) * Σ_{i: 信号日_i<=t} ret_i / 100
    于是终点 A_end = 1 + avg_ret/100，与 backtest_out.json 的逐笔期望收益一一对应。
  - 这是「等权分散到全部交易机会」的累积收益示意，不是账户净值；不含复利、不含资金周转。
输出 equity_curve.json + equity_series.csv（每日点位，可追溯）+ chart_equity.png。
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
OUT = json.loads((WS/"backtest_out.json").read_text(encoding="utf-8"))
CFG = OUT["config"]
D0, D1 = CFG["D0"], CFG["D1"]
POOLS = [("C7单池", "backtest_detail_c7.csv"), ("C6+C7双池", "backtest_detail_dual.csv")]

details = {}
for gname, fn in POOLS:
    d = pd.read_csv(WS/fn, encoding="utf-8-sig")
    d["trade_date"] = pd.to_datetime(d["trade_date"])
    details[gname] = d

# 交易日轴 = 两份明细日期并集（严格只用明细；两条曲线按此对齐）
CAL = pd.DatetimeIndex(sorted(set(details["C7单池"].trade_date) | set(details["C6+C7双池"].trade_date)))

curves, audit = {}, {}
for gname, fn in POOLS:
    d = details[gname]
    fl = d[d["filled"].astype(bool)].copy().sort_values("trade_date")
    M = len(fl)                                   # 资金分份数 = 成交笔数
    contrib = fl["ret"].values / 100.0 / M        # 每笔对资产的贡献
    csum = np.cumsum(contrib)
    # 按信号日聚合：到每日 t 的累计资产
    per_day_end = {}
    for dt, c in zip(fl["trade_date"], csum):
        per_day_end[dt] = c                       # 同日多笔取最后累计值
    pts = []
    running = 0.0
    for dt in CAL:
        if dt in per_day_end:
            running = per_day_end[dt]
        pts.append(1.0 + running)
    asset = np.concatenate([[1.0], pts])          # A_0=1
    curves[gname] = asset
    end = float(asset[-1])
    exp_json = OUT["groups"][gname]["全区间"]["avg_ret"]
    audit[gname] = dict(
        n_filled=M, json_n_filled=OUT["groups"][gname]["全区间"]["n_filled"],
        n_signal_days=int(fl.trade_date.nunique()),
        fund_share_M=M,
        final_asset=round(end, 6),
        cum_return_pct=round((end-1)*100, 4),
        json_avg_ret=exp_json,
        check_end_equals_1_plus_avg_ret=abs((end-1)*100 - exp_json) < 1e-3,
    )
    assert M == OUT["groups"][gname]["全区间"]["n_filled"], "成交笔数与JSON不一致"
    assert audit[gname]["check_end_equals_1_plus_avg_ret"], "曲线终点与JSON期望收益不一致"

# 分界点：直接用明细 split 字段
all_rows = pd.concat([details[g] for g,_ in POOLS])
train_last = all_rows.loc[all_rows.split=="train","trade_date"].max()
oos_first  = all_rows.loc[all_rows.split=="oos","trade_date"].min()

# 画图
plt.rcParams["font.sans-serif"]=["Microsoft YaHei","SimHei","SimSun"]
plt.rcParams["axes.unicode_minus"]=False
plt.rcParams["figure.dpi"]=140
fig, ax = plt.subplots(figsize=(11.5,5.4))
for gname, color in [("C7单池","#1f3a5f"),("C6+C7双池","#1f9e8f")]:
    y = curves[gname][1:]
    ax.plot(CAL, y, color=color, lw=2.0,
            label=f"{gname}（终值 {audit[gname]['final_asset']:.4f}，累计 {audit[gname]['cum_return_pct']:+.3f}%）")
ax.axhline(1.0, color="#8a8f98", lw=0.9, ls=":", label="起始资产=1")
ax.axvline(oos_first, color="#c0392b", ls="--", lw=1.4)
yl = ax.get_ylim()
ax.text(oos_first, yl[0]+0.03*(yl[1]-yl[0]), " 样本内 │ 样本外", color="#c0392b",
        fontsize=9, rotation=90, va="bottom")
ax.set_ylabel("资产（起始=1，等权示意）"); ax.set_xlabel("信号日 T（收益按信号日归属，规则2.2）")
ax.set_title("收益率板面：等权分散累积收益示意（非账户净值）")
ax.legend(loc="upper left", fontsize=9.5); ax.grid(alpha=0.3)
fig.autofmt_xdate()
p = WS/"chart_equity.png"; fig.savefig(p, bbox_inches="tight"); plt.close(fig)

# 每日点位导出（可追溯）
series = {"trade_date":[d.strftime("%Y-%m-%d") for d in CAL],
          "split":["train" if d<=train_last else "oos" for d in CAL]}
for gname,_ in POOLS:
    series[gname] = [round(float(v),8) for v in curves[gname][1:]]
(WS/"equity_series.csv").write_text(
    pd.DataFrame(series).to_csv(index=False, encoding="utf-8-sig"), encoding="utf-8")

res = dict(
    config=dict(D0=D0, D1=D1, base=1.0,
        formula="A_t = 1 + (1/M)*Σ_{signal_day_i<=t} ret_i/100; M=成交笔数（资金等分数）",
        axis="交易日轴=两份明细trade_date并集；两条曲线按此对齐",
        attribution="收益按信号日T归属（规则2.2），不按退出日",
        caveat="方案无仓位/资金分配/同时持仓数定义：账户净值曲线、年化收益、最大回撤、夏普均不可得"
               "（无法由逐笔明细唯一确定每日仓位），不以替代值填充。本曲线为等权分散累积收益示意，"
               "终点=1+逐笔期望收益/100，与backtest_out.json一致。"),
    split_boundary=dict(train_last=train_last.strftime("%Y-%m-%d"), oos_first=oos_first.strftime("%Y-%m-%d")),
    audit=audit, chart=str(p), series_csv=str(WS/"equity_series.csv"),
)
(WS/"equity_curve.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
print("EQUITY_OK")
for g,_ in POOLS:
    a=audit[g]
    print(f"  {g}: 成交{a['n_filled']}(json {a['json_n_filled']}) 资金分份M={a['fund_share_M']} "
          f"信号日{a['n_signal_days']} 终值{a['final_asset']} 累计{a['cum_return_pct']}% "
          f"对上json期望{a['json_avg_ret']}:{a['check_end_equals_1_plus_avg_ret']}")
print("  分界:", res["split_boundary"])
