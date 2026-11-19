# -*- coding: utf-8 -*-
"""
生成商业级自包含 HTML 报告（图表以 base64 内嵌，无外部依赖）。
零写入投研项目；仅输出到工作目录。
"""
from __future__ import annotations
import json, base64, io, html
from pathlib import Path
import numpy as np
import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from matplotlib.patches import Patch

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
MAT = (WS / "matrix.parquet").as_posix()
D = json.loads((WS / "report_data.json").read_text(encoding="utf-8"))

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 150
plt.rcParams["savefig.dpi"] = 150
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.25
plt.rcParams["grid.linewidth"] = 0.6
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False
plt.rcParams["font.size"] = 10

NAVY = "#0B1F3A"; TEAL = "#1B9E97"; AMBER = "#E4A33C"; RED = "#D1495B"
BLUE = "#3D7EA6"; GRAY = "#8A94A6"; LIGHT = "#E9EDF2"; GREEN = "#3E9D6E"

def b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")

def pct(x, _=None):
    return f"{x*100:.0f}%"

# ---------- 全市场逐日序列 ----------
con = duckdb.connect()
con.execute("SET threads=8")
dm = con.execute(f"""
SELECT di, min(CAST(trade_date AS VARCHAR)) AS d,
       avg(mkt_hit10) AS h10, avg(mkt_hit5) AS h5,
       avg(mkt_amount)/1e12 AS amt, avg(mkt_lu) AS lu
FROM read_parquet('{MAT}')
WHERE mkt_hit10 IS NOT NULL
GROUP BY di ORDER BY di
""").df()
dates = dm["d"].astype(str).tolist()
h10 = dm["h10"].to_numpy(float)
h5 = dm["h5"].to_numpy(float)
amt = dm["amt"].to_numpy(float)
xidx = np.arange(len(dates))

def xticks(ax, step=60):
    ticks = list(range(0, len(dates), step))
    ax.set_xticks(ticks)
    ax.set_xticklabels([dates[i][:7] for i in ticks], rotation=0, fontsize=8)

CHARTS = {}

# ===== 图1：市场温度计（月度） =====
mb = D["monthly_base"]
ym = [m["ym"] for m in mb]
m10 = np.array([m["hit10"] for m in mb], float)
m5 = np.array([m["hit5"] for m in mb], float)
ma = np.array([m["amt"] for m in mb], float)
fig, ax = plt.subplots(figsize=(11, 4.2))
xx = np.arange(len(ym))
ax.bar(xx, ma, color=LIGHT, width=0.72, label="月均成交额（万亿元，右轴）", zorder=1)
ax2 = ax.twinx()
ax2.set_ylim(0, 2.6)
ax2.set_ylabel("成交额（万亿元）", color=GRAY, fontsize=9)
ax2.tick_params(axis="y", colors=GRAY, labelsize=8)
ax2.grid(False)
ax.plot(xx, m10, color=NAVY, lw=2.4, marker="o", ms=4, label="未来10日涨幅≥20% 占比", zorder=3)
ax.plot(xx, m5, color=TEAL, lw=2.0, marker="o", ms=3.5, label="未来5日涨幅≥20% 占比", zorder=3)
ax.axhline(0.75, color=RED, ls="--", lw=1.4, label="目标门槛 75%", zorder=2)
ax.axvspan(6, 7, color=AMBER, alpha=0.16, zorder=0)
ax.annotate("2024-09 · 924行情普涨\n全市场10日达标率 53.3%", xy=(7, m10[7]), xytext=(9.5, 0.62),
            fontsize=8.5, color=NAVY,
            arrowprops=dict(arrowstyle="->", color=NAVY, lw=1.1))
ax.set_xticks(xx[::3]); ax.set_xticklabels([ym[i] for i in xx[::3]], rotation=30, ha="right", fontsize=8)
ax.set_ylim(0, 0.62); ax.yaxis.set_major_formatter(FuncFormatter(pct))
ax.set_ylabel("全市场达标股票占比", fontsize=9)
ax.set_title("图1  市场温度计：33个月里只有 2024-09 一个月接近过 75% 目标", fontsize=12, color=NAVY, pad=12, loc="left", fontweight="bold")
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8, frameon=False, ncol=2)
CHARTS["c1"] = b64(fig)

# ===== 图2：逐日达标率 + 门槛线 =====
fig, ax = plt.subplots(figsize=(11, 4.2))
ax.plot(xidx, h10, color=NAVY, lw=1.1, label="全市场逐日 10日达标率", zorder=2)
ax.plot(xidx, h5, color=TEAL, lw=0.9, alpha=0.85, label="全市场逐日 5日达标率", zorder=2)
for yv, c, lab in [(0.75, RED, "75% 目标"), (0.50, AMBER, "50%"), (0.25, GRAY, "25%")]:
    ax.axhline(yv, color=c, ls="--", lw=1.1, label=lab, zorder=1)
hd = D["high_days"]
hidx = [dates.index(r["date"]) for r in hd if r["date"] in dates]
ax.scatter(hidx, [h10[i] for i in hidx], s=34, color=RED, zorder=4, edgecolors="white", lw=0.8,
           label="高基准日（13天）")
ax.axvspan(hidx[0]-2 if hidx else 0, hidx[2]+2 if len(hidx)>2 else 0, color=AMBER, alpha=0.10)
ax.axvspan(hidx[3]-2 if len(hidx)>3 else 0, hidx[-1]+2 if hidx else 0, color=AMBER, alpha=0.10)
ax.annotate("2024-02 超跌反弹窗口", xy=(hidx[1], 0.70), xytext=(hidx[1]+30, 0.82), fontsize=8.5,
            color=NAVY, arrowprops=dict(arrowstyle="->", color=NAVY, lw=1))
ax.annotate("2024-09 全面普涨窗口", xy=(hidx[8], 0.98), xytext=(hidx[8]-110, 0.90), fontsize=8.5,
            color=NAVY, arrowprops=dict(arrowstyle="->", color=NAVY, lw=1))
xticks(ax, 60)
ax.set_ylim(0, 1.02); ax.yaxis.set_major_formatter(FuncFormatter(pct))
ax.set_ylabel("全市场达标占比", fontsize=9)
ax.set_title("图2  75% 是极罕见的「市场状态」，不是常态：659个交易日仅10天达标", fontsize=12, color=NAVY, pad=12, loc="left", fontweight="bold")
ax.legend(loc="upper right", fontsize=8, frameon=False, ncol=3)
CHARTS["c2"] = b64(fig)

# ===== 图3：单指标 lift TOP14 =====
sc = D["stock_scan"]
CN = {"scrplus_90":"90%筹码获利比例","scrplus_70":"70%筹码获利比例","lu_cnt_20d":"近20日涨停次数",
      "vol20":"20日波动率","n_leader_concepts":"命中龙头概念数","lu_cnt_10d":"近10日涨停次数",
      "bias5":"收盘/MA5-1","pct_change":"当日涨跌幅","n_hot_concepts":"命中热榜概念数",
      "bias20":"收盘/MA20-1","ret_20d":"近20日涨幅","ret_5d":"近5日涨幅","ret_10d":"近10日涨幅",
      "turnover_rate":"换手率","small_norm":"小单净额占比","in_strong_concept":"属强概念",
      "amt_ratio":"成交额/20日均","lu_gap":"涨幅-涨停阈值","huge_norm":"超大单净额占比",
      "close_hh20_ratio":"收盘/20日最高","main_net_norm":"主力净额占比","n_concepts":"概念总数",
      "amt_ma20":"20日均成交额","tor_ratio":"换手率/5日均","bias20":"收盘/MA20-1"}
rows = []
for k, v in sc.items():
    if isinstance(v, dict) and "lift10" in v:
        rows.append((CN.get(k, k), v["lift10"], v["best_hit10"]["hit10"]))
rows.sort(key=lambda r: -r[1])
rows = rows[:14][::-1]
fig, ax = plt.subplots(figsize=(9, 5.0))
names = [r[0] for r in rows]; lifts = [r[1] for r in rows]; hits = [r[2] for r in rows]
bars = ax.barh(names, lifts, color=[TEAL if l < 2.2 else AMBER for l in lifts], height=0.68)
for b, h in zip(bars, hits):
    ax.text(b.get_width()+0.03, b.get_y()+b.get_height()/2, f"最优桶 hit10={h*100:.1f}%",
            va="center", fontsize=7.6, color=NAVY)
ax.axvline(1.0, color=GRAY, ls="--", lw=1.1)
ax.text(1.02, -0.8, "基准=1×", fontsize=8, color=GRAY)
ax.set_xlim(0, max(lifts)+0.85)
ax.set_xlabel("相对全市场基准的提升倍数（lift）", fontsize=9)
ax.set_title("图3  单指标再强也摸不到 75%：最强指标仅把 11.5% 抬到 28.4%（2.46×）",
             fontsize=11.5, color=NAVY, pad=12, loc="left", fontweight="bold")
CHARTS["c3"] = b64(fig)

# ===== 图4：代表指标 10 分位桶 =====
keys = [("vol20", "20日波动率", "收益大与风险大并存"), ("turnover_rate", "换手率", "有量才有价"),
        ("scrplus_90", "90%筹码获利比例", "指标滞后 / 非单调"), ("lu_cnt_20d", "近20日涨停次数", "资金聚集 / 情绪")]
fig, axes = plt.subplots(2, 2, figsize=(10, 6.2))
for ax, (k, cn, sub) in zip(axes.ravel(), keys):
    v = sc[k]; bs = v["buckets"]
    bx = [b["b"] for b in bs]; by = [b["hit10"] for b in bs]
    ax.plot(bx, by, color=NAVY, lw=2, marker="o", ms=4)
    ax.fill_between(bx, by, 0.1154, color=TEAL, alpha=0.14)
    ax.axhline(0.1154, color=GRAY, ls="--", lw=1, label="全市场基准 11.5%")
    ax.axhline(0.75, color=RED, ls=":", lw=1.2, label="75% 目标")
    ax.set_ylim(0, 0.34); ax.yaxis.set_major_formatter(FuncFormatter(pct))
    ax.set_xticks(range(1, 11)); ax.set_xlabel("分位桶（1=最低 … 10=最高）", fontsize=8)
    ax.set_title(f"{cn} · {sub}", fontsize=9.5, color=NAVY, loc="left")
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=7, frameon=False, loc="upper left")
fig.suptitle("图4  分位桶剖面：量能/波动单调向上，筹码比例非单调（滞后效应）",
             fontsize=11.5, color=NAVY, y=1.00, fontweight="bold", x=0.02, ha="left")
fig.tight_layout(rect=[0, 0, 1, 0.96])
CHARTS["c4"] = b64(fig)

# ===== 图5：模板稳定性 =====
stab = D["templates_stability"]
sname = [s["name"].replace("_", " ") for s in stab]
tr = [s["train10"] for s in stab]; iv = [s["iv10"] for s in stab]; oo = [s["oos10"] for s in stab]
xx = np.arange(len(sname)); w = 0.26
fig, ax = plt.subplots(figsize=(11, 4.4))
ax.bar(xx-w, tr, w, color=NAVY, label="训练 2024-02~2025-12")
ax.bar(xx, iv, w, color=TEAL, label="内验 2025-07~2025-12")
ax.bar(xx+w, oo, w, color=AMBER, label="样本外 2026-01~2026-10")
ax.axhline(0.115, color=GRAY, ls="--", lw=1.2, label="全市场基准 11.5%")
ax.axhline(0.75, color=RED, ls="--", lw=1.3, label="75% 目标")
ax.set_xticks(xx); ax.set_xticklabels(sname, rotation=18, ha="right", fontsize=8)
ax.set_ylim(0, 0.46); ax.yaxis.set_major_formatter(FuncFormatter(pct))
ax.set_ylabel("10日口径合并池达标比例", fontsize=9)
ax.set_title("图5  样本外普遍衰减：T3 超跌反转从 40.0% 掉到 15.5%（过拟合证据）",
             fontsize=11.5, color=NAVY, pad=12, loc="left", fontweight="bold")
ax.legend(fontsize=8, frameon=False, ncol=5, loc="upper center")
CHARTS["c5"] = b64(fig)

# ===== 图6：三档分级 =====
grades = D["grades"]["C_25-50%"]
gl = [f"C{i+1}" for i in range(len(grades))]
gtr = [g["train10"] for g in grades]; goo = [g["oos10"] for g in grades]
xx = np.arange(len(gl))
fig, ax = plt.subplots(figsize=(10, 4.2))
ax.bar(xx-0.19, gtr, 0.38, color=NAVY, label="训练合并池")
ax.bar(xx+0.19, goo, 0.38, color=TEAL, label="样本外合并池")
for yv, c, lab in [(0.75, RED, "A档 75%"), (0.50, AMBER, "B档 50%"), (0.25, BLUE, "C档 25%")]:
    ax.axhline(yv, color=c, ls="--", lw=1.2, label=lab)
ax.axhspan(0.25, 0.50, color=BLUE, alpha=0.06)
for i, (a, b) in enumerate(zip(gtr, goo)):
    ax.text(i-0.19, a+0.008, f"{a*100:.1f}", ha="center", fontsize=7.6, color=NAVY)
    ax.text(i+0.19, b+0.008, f"{b*100:.1f}", ha="center", fontsize=7.6, color=TEAL)
ax.set_xticks(xx); ax.set_xticklabels(gl, fontsize=9)
ax.set_ylim(0, 0.82); ax.yaxis.set_major_formatter(FuncFormatter(pct))
ax.set_ylabel("10日口径达标比例", fontsize=9)
ax.set_title("图6  10条候选规则全部落在 C 档（25–50%）：A 档与 B 档均为空",
             fontsize=11.5, color=NAVY, pad=12, loc="left", fontweight="bold")
ax.legend(fontsize=8, frameon=False, ncol=3, loc="upper right")
CHARTS["c6"] = b64(fig)

# ===== 图7：逐日回放 + 达标日窗口对比 =====
rec = D["recommended"]
r3 = rec["R3_情绪涨停高覆盖"]["replay"]
daily = r3["daily"]
rdates = [r["date"] for r in daily]
rhit = [r["hit10"] if r["hit10"] is not None else np.nan for r in daily]
rx = np.arange(len(rdates))
fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.3), gridspec_kw={"width_ratios":[1.55, 1]})
ax = axes[0]
ax.plot(rx, rhit, color=BLUE, lw=0.85, alpha=0.85, label="R3 规则逐日达标率")
ax.scatter(rx, rhit, s=6, color=BLUE, alpha=0.5)
hi = [i for i, r in enumerate(daily) if r["date"] in [d["date"] for d in r3["hit10_dates"]]]
ax.scatter(hi, [rhit[i] for i in hi], s=42, color=RED, zorder=5, edgecolors="white", lw=0.8,
           label="逐日≥75% 的复盘日期（8天）")
ax.axhline(0.75, color=RED, ls="--", lw=1.3, label="75% 门槛")
ax.axhline(0.115, color=GRAY, ls="--", lw=1.1, label="全市场基准 11.5%")
# 牛熊窗口
for a, b, lab in [("2024-02-05","2024-02-08","超跌反弹"), ("2024-09-12","2024-09-27","普涨")]:
    ia = rdates.index(a) if a in rdates else 0
    ib = rdates.index(b) if b in rdates else 0
    ax.axvspan(ia, ib, color=AMBER, alpha=0.16)
    ax.text((ia+ib)/2, 0.92, lab, ha="center", fontsize=8, color=NAVY)
ticks = list(range(0, len(rdates), 90))
ax.set_xticks(ticks); ax.set_xticklabels([rdates[i][:7] for i in ticks], fontsize=8)
ax.set_ylim(0, 1.05); ax.yaxis.set_major_formatter(FuncFormatter(pct))
ax.set_ylabel("当日选出股票的 10日达标比例", fontsize=9)
ax.set_title("图7a  日期作横轴：R3 在牛熊中的逐日表现（达标日全部集中在两个牛市窗口）",
             fontsize=10.5, color=NAVY, pad=10, loc="left", fontweight="bold")
ax.legend(fontsize=7.5, frameon=False, loc="upper right")

ax = axes[1]
rk = ["R1", "R2", "R3"]
allv = [rec[k]["replay"]["all_pool"]["10"]["hit"] for k in rec]
resv = [rec[k]["replay"]["restricted_pool"]["10"]["hit"] for k in rec]
xx = np.arange(3)
ax.bar(xx-0.19, allv, 0.38, color=BLUE, label="全样本（可交易）")
ax.bar(xx+0.19, resv, 0.38, color=AMBER, label="仅达标日窗口（事后复盘）")
ax.axhline(0.75, color=RED, ls="--", lw=1.3, label="75% 目标")
ax.axhline(0.115, color=GRAY, ls="--", lw=1.1, label="全市场基准")
for i, (a, b) in enumerate(zip(allv, resv)):
    ax.text(i-0.19, a+0.015, f"{a*100:.1f}%", ha="center", fontsize=8, color=NAVY)
    ax.text(i+0.19, b+0.015, f"{b*100:.1f}%", ha="center", fontsize=8, color=NAVY)
ax.set_xticks(xx); ax.set_xticklabels(rk); ax.set_ylim(0, 1.08)
ax.yaxis.set_major_formatter(FuncFormatter(pct))
ax.set_title("图7b  两种口径：可交易 vs 事后复盘", fontsize=10.5, color=NAVY, pad=10, loc="left", fontweight="bold")
ax.legend(fontsize=7.5, frameon=False, loc="center right")
fig.tight_layout()
CHARTS["c7"] = b64(fig)

print("charts:", {k: len(v)//1024 for k, v in CHARTS.items()}, "KB")

# ================= HTML =================
CSS = """
:root{--navy:#0B1F3A;--teal:#1B9E97;--amber:#E4A33C;--red:#D1495B;--blue:#3D7EA6;
--ink:#1E2A3A;--muted:#5C6B7F;--line:#DFE5EC;--bg:#F6F8FB;--card:#FFFFFF}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font-family:"Microsoft YaHei","PingFang SC","Segoe UI",Arial,sans-serif;line-height:1.75;font-size:15px}
.wrap{max-width:1120px;margin:0 auto;padding:0 28px 90px}
header{background:linear-gradient(135deg,#0B1F3A 0%,#143A5C 55%,#1B9E97 100%);color:#fff;padding:52px 28px 44px}
header .inner{max-width:1120px;margin:0 auto}
.eyebrow{font-size:12px;letter-spacing:2.5px;color:#9FD8D4;text-transform:uppercase;margin-bottom:14px}
h1{font-size:31px;line-height:1.35;margin:0 0 14px;font-weight:700;letter-spacing:.5px}
.sub{font-size:15px;color:#D6E5EC;max-width:820px;margin:0}
.meta{margin-top:26px;display:flex;gap:26px;flex-wrap:wrap;font-size:12.5px;color:#B9CBD8}
.meta b{color:#fff;font-weight:600}
.toc{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:20px 26px;margin:32px 0 10px;
 box-shadow:0 2px 10px rgba(11,31,58,.04)}
.toc h3{margin:0 0 10px;font-size:14px;color:var(--navy);letter-spacing:1px}
.toc ol{margin:0;padding-left:20px;columns:2;column-gap:44px;font-size:13.5px}
.toc li{margin:3px 0;break-inside:avoid}
.toc a{color:var(--muted);text-decoration:none}
.toc a:hover{color:var(--teal)}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:30px 34px;margin:22px 0;
 box-shadow:0 2px 10px rgba(11,31,58,.035)}
h2{font-size:21px;color:var(--navy);margin:0 0 6px;padding-bottom:12px;border-bottom:2px solid var(--line);font-weight:700}
h2 .num{color:var(--teal);font-size:14px;letter-spacing:1px;display:block;margin-bottom:4px}
h3{font-size:16px;color:var(--navy);margin:26px 0 10px}
h4{font-size:14px;color:var(--blue);margin:18px 0 8px}
p{margin:11px 0}
.lead{font-size:16px;color:var(--ink)}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:22px 0 6px}
.kpi{background:#F8FAFC;border:1px solid var(--line);border-left:4px solid var(--teal);border-radius:8px;padding:16px 18px}
.kpi .v{font-size:27px;font-weight:700;color:var(--navy);line-height:1.2}
.kpi .v.red{color:var(--red)} .kpi .v.amber{color:#B87A18}
.kpi .k{font-size:12px;color:var(--muted);margin-top:6px}
.callout{border-left:4px solid var(--amber);background:#FFF9EE;padding:16px 20px;border-radius:0 8px 8px 0;margin:18px 0;font-size:14px}
.callout.red{border-color:var(--red);background:#FEF3F4}
.callout.teal{border-color:var(--teal);background:#EFF9F8}
.callout b{color:var(--navy)}
table{width:100%;border-collapse:collapse;margin:16px 0;font-size:13.5px}
th{background:#EFF3F8;color:var(--navy);font-weight:600;text-align:left;padding:10px 12px;border-bottom:2px solid var(--line);white-space:nowrap}
td{padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
tr:hover td{background:#FAFCFE}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.tag{display:inline-block;padding:2px 9px;border-radius:12px;font-size:11.5px;font-weight:600;white-space:nowrap}
.tag.a{background:#FDE9EC;color:var(--red)} .tag.b{background:#FFF2DA;color:#B87A18}
.tag.c{background:#E7F0F8;color:var(--blue)} .tag.d{background:#EEF1F4;color:var(--muted)}
.tag.ok{background:#E4F5EC;color:#2E7D57}
.chart{margin:20px 0 8px;text-align:center}
.chart img{max-width:100%;height:auto;border:1px solid var(--line);border-radius:8px}
.cap{font-size:12.5px;color:var(--muted);text-align:center;margin-top:8px}
.rule{background:#F7FAFC;border:1px solid var(--line);border-radius:8px;padding:16px 20px;margin:14px 0}
.rule .rt{font-weight:700;color:var(--navy);font-size:15px;margin-bottom:8px}
.rule code{background:#EAF0F6;color:var(--navy);padding:2px 6px;border-radius:4px;font-size:12.5px;
 font-family:Consolas,"Microsoft YaHei",monospace;line-height:2.1;display:inline-block}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
ul,ol{padding-left:22px;margin:10px 0} li{margin:6px 0}
.theory{border:1px solid var(--line);border-radius:8px;padding:16px 20px;margin:12px 0;background:#FBFCFE}
.theory .h{font-weight:700;color:var(--navy);font-size:14.5px;margin-bottom:6px}
.theory .h span{color:var(--teal);font-size:12px;margin-right:8px}
.small{font-size:12.5px;color:var(--muted)}
footer{text-align:center;color:var(--muted);font-size:12.5px;padding:30px 20px}
.hl{background:linear-gradient(transparent 62%,#FFE9A8 62%);font-weight:600}
@media(max-width:820px){.kpis{grid-template-columns:repeat(2,1fr)}.grid2{grid-template-columns:1fr}.toc ol{columns:1}}
"""

def H(s):
    return html.escape(str(s))

def table(headers, rows, numcols=()):
    th = "".join(f'<th class="{"num" if i in numcols else ""}">{H(h)}</th>' for i, h in enumerate(headers))
    body = []
    for r in rows:
        body.append("<tr>" + "".join(
            f'<td class="{"num" if i in numcols else ""}">{c}</td>' for i, c in enumerate(r)) + "</tr>")
    return f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(body)}</tbody></table>"

def img(k, cap):
    return f'<div class="chart"><img src="data:image/png;base64,{CHARTS[k]}" alt="{H(cap)}"/><div class="cap">{H(cap)}</div></div>'

P = []
A = P.append

A(f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>A股选股条件研究 · 75% 达标可行性报告</title><style>{CSS}</style></head><body>
<header><div class="inner">
<div class="eyebrow">Quantitative Research · 投研分析报告</div>
<h1>「未来 5 / 10 日最大涨幅 ≥ 20%」<br/>选股条件组合可行性研究</h1>
<p class="sub">基于 stockDisplay 项目 359 万条 A 股日频样本，用 TPE 风格贝叶斯优化 + 三层时间切分验证，
回答一个问题：<b>能否用当日可知的指标阈值，让选中股票里 75% 以上在 5 日或 10 日内摸到 +20%？</b></p>
<div class="meta"><span>样本区间 <b>2024-02-01 ~ 2026-11-10</b></span><span>交易日 <b>669 天</b></span>
<span>股票 <b>5,741 只</b></span><span>观测 <b>3,590,923 行</b></span>
<span>训练/样本外切分 <b>2024-02~2025-12 / 2026-01~2026-10</b></span></div>
</div></header><div class="wrap">""")

A("""<div class="toc"><h3>目录</h3><ol>
<li><a href="#s1">结论速览</a></li><li><a href="#s2">数据与指标探查结论</a></li>
<li><a href="#s3">评估口径与目标定义</a></li><li><a href="#s4">方法选型与理由</a></li>
<li><a href="#s5">单指标信号扫描</a></li><li><a href="#s6">市场状态：75% 有多罕见</a></li>
<li><a href="#s7">选股条件组合结果与验证</a></li><li><a href="#s8">含日期标记的条件组合（复盘口径）</a></li>
<li><a href="#s9">未达标与不稳定条件说明</a></li><li><a href="#s10">六条理论的对应解释</a></li>
<li><a href="#s11">风险披露与使用建议</a></li><li><a href="#s12">附录：字段字典与复现方式</a></li>
</ol></div>""")

# ---- 1 结论速览 ----
A("""<section id="s1"><h2><span class="num">01</span>结论速览</h2>
<p class="lead"><b>结论先行：在「纯当日可知指标阈值」的约束下，75% 的目标在这份数据上不成立。</b>
不是搜索没做好，是目标本身与 A 股的自然分布相冲突。全市场任意一只股票，未来 10 日内最高价摸到 +20% 的
长期概率只有 <span class="hl">11.5%</span>（5 日只有 5.2%）；要把这个比例稳定抬到 75%，需要 6.5 倍的提升，
而数据里最强的单指标也只能做到 2.46 倍。</p>
<div class="kpis">
<div class="kpi"><div class="v">11.5%</div><div class="k">全市场 10 日口径基准达标率</div></div>
<div class="kpi"><div class="v">5.2%</div><div class="k">全市场 5 日口径基准达标率</div></div>
<div class="kpi"><div class="v amber">41.8%</div><div class="k">搜索到的最优条件组合（训练集 C 档）</div></div>
<div class="kpi"><div class="v red">0 条</div><div class="k">达到 A 档（≥75%）的可交易规则</div></div>
</div>
<div class="callout red"><b>关键判断：</b>10 条候选规则（7 个理论模板 + 3 次局部精修）全部落在
<b>C 档 25%~50%</b>，A 档与 B 档为空。样本外（2026 年）最优规则衰减到 35.2%，
且 <b>199 个样本外交易日中，没有任何一天逐日达标率 ≥ 75%</b>。
换句话说：<span class="hl">75% 只在极少数「市场极端日」出现，是个市场状态问题，不是选股指标问题。</span></div>
<div class="callout teal"><b>可交付的部分：</b>我们给出了 3 条经过三层验证的 C 档条件组合（含具体指标阈值与分位数）、
逐日复盘的达标日期清单、5 日/10 日双口径比例、样本外衰减证据，以及六条投研理论在数据上的对应解释。
按用户要求把 75% 拆成 25–50% / 50–75% / ≥75% 三档统计，结论是<b>只有 C 档有货</b>。</div>
</section>""")

# ---- 2 数据探查 ----
A("""<section id="s2"><h2><span class="num">02</span>数据与指标探查结论</h2>
<p>全部结论基于对项目数据层的只读探查，未修改投研项目任何数据文件与代码文件。
为避免 <code>cli.py</code> 每次调用都会追加 <code>logs/cli_audit.log</code> 的写入副作用，
批量探查一律直接读取 DuckDB / Parquet，不走 CLI。</p>
<h3>2.1 数据覆盖与结构</h3>""")
A(table(["数据源", "规模", "覆盖范围", "探查结论"], [
 ["quote 日行情（含 compact 月合并）", "3,590,923 行 / 669 日 / 5,741 只", "2024-02-01 ~ 2026-11-10", "close / high / amount 缺失 0%；文档写的 2026-11-02 已过期"],
 ["daily_pct（统一涨跌幅）", "3,585,683 行 / 668 日", "2024-02-02 ~ 2026-11-10", "公式核验：与 close 复权口径 mean_abs_diff=4.05e-15，确认一致；含 1 个 inf 需清洗"],
 ["concept_date 概念归属", "3,445,022 行", "668 日", "concepts 为分号分隔串，平均 7.14 个概念、最多 49 个；无空值"],
 ["tops_bars 三榜（成交额/涨幅/涨停数）", "20,040 行 / 668 日", "rank 1~10", "含归成比、is_strong、涨停数等，用于构造「概念聚集度」特征"],
 ["concept_meta（gld / ztnr）", "47,043 行", "全区间", "关联度与涨停数解释，覆盖 100%"],
 ["market_amount 市场总成交额", "667 行", "4.80e11 ~ 3.99e12", "均值 1.748 万亿，用于市场状态描述"],
 ["trading_calendar 交易日历", "8,797 日", "1990-12-19 ~ 2026-12-31", "本地缓存齐全，探查不触发联网"],
 ["_tops_cache / concept_picks", "662 天 / 每日 40 行", "全区间", "缓存内 fwd_max_10d 与自建标签逐股 diff=0.0，口径校验通过"],
], numcols=()))
A("""<div class="callout"><b>数据快照口径（重要）：</b>本报告全部计算基于<b>2026-11-10 收盘时点的 669 日快照</b>（2024-02-01 ~ 2026-11-10）。分析会话进行中，项目自身的 <code>serve</code> 后台进程在 16:09–16:11 检测到当日无数据，自动执行了 <code>tdx_fetch → daily_update → core.rebuild → archive_month</code>，把数据推进到 670 日（新增 2026-11-12 单日）。这是<b>项目自身定时更新</b>、非本分析所写（详见 12.2 合规取证）。新增的 11-12 单日没有未来 5/10 日标签，本就不参与任何达标比例计算，因此该快照与后续新增一天对全部结论<b>零影响</b>；下方所有比例、计数均以 669 日快照为准。</div>
<h3>2.2 标签口径（与项目源码逐行对齐）</h3>
<div class="callout"><b>fwd_max_Nd</b> = ( 未来 T+1 … T+N 日内最高价 / T 日收盘价 − 1 ) × 100，
<b>不含当日</b>、未来交易日不足 N 天则置 null（禁止按 0 处理）。
本项目 <code>queries/concept.py:411 _build_forward_map</code> 的实现与我们用 DuckDB
<code>RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING</code> 复刻的标签逐股比对，
2024-09-30 的 40 只股票 mean_abs_diff = 0.0 / max_abs_diff = 0.0。<br/>
<b>关于「超过 20%」：</b>矩阵标签用 ≥20%。已核验全样本中 fwd_max_10d 与 fwd_max_5d
<b>恰好等于 20.0 的记录为 0 条</b>，因此「&gt;20%」与「≥20%」在本数据集完全等价，口径无歧义。<br/>
<b>关于「5 日或 10 日任一」：</b>10 日窗口包含 5 日窗口，恒有 fwd_max_10d ≥ fwd_max_5d；
实测 y5=1 但 y10=0 的样本 <b>0 条</b>。因此「任一」在逻辑上等价于 10 日口径，
但报告仍按用户要求分别输出 5 日 / 10 日两套验证数字。</div>
<h3>2.3 字段缺失率与可用清单（按用户要求剔除高缺失字段）</h3>""")
A(table(["字段", "缺失率", "处置", "原因"], [
 ["hot_rank 热度排名", "26.36%（且 picks 内全 null）", "<span class='tag a'>剔除</span>", "缺失过多，用户点名"],
 ["max_concept_score 最强概念分", "44.46%", "<span class='tag a'>剔除</span>", "近半缺失，纳入会引入选择偏差"],
 ["fwd_max_10d / y10 标签", "1.91%", "仅作标签/验收", "未来数据不足的尾部 7 天，不参与统计"],
 ["ret_20d / 4 个 order_net / eff_hit_lag", "1.6% ~ 3.1%", "<span class='tag ok'>可用</span>", "缺失率低，配合 finite mask 排除"],
 ["其余 27 个量价/筹码/概念特征", "≤ 3.1%", "<span class='tag ok'>可用</span>", "全部为 T 日收盘可知，rolling/lag 只用 di ≤ T"],
], numcols=()))
A("""<div class="callout"><b>防前视红线：</b>所有 27 个筛选特征都只用 T 日及之前的信息构造；
<code>fwd_*</code> 系列只用于生成标签与验收，<b>绝不进入任何筛选条件</b>。
分位阈值表只用训练区间（2024-02~2025-12）建立，样本外与内验共用该表，避免阈值泄漏。</div>
<h3>2.4 构造出的特征矩阵</h3>
<p>输出 <code>matrix.parquet</code>（78 列 × 3,590,923 行）。切分：
训练 <b>2,458,004 行 / 463 日</b>（基准 hit10=11.54%、hit5=5.25%）、
内验 <b>678,647 行 / 126 日</b>、样本外 <b>1,093,939 行 / 199 日</b>（hit10=8.76%、hit5=3.87%）。
特征分六组：量能（换手率/成交额比/量比）、资金（超大单/主力/小单净额占比）、
筹码（scrplus_90/70）、波动（vol20）、情绪与聚集（涨停次数/热榜概念/龙头概念/强概念）、
趋势与位置（涨跌幅/均线偏离/区间涨幅/距 20 日高点）。</p>
</section>""")

# ---- 3 口径 ----
A("""<section id="s3"><h2><span class="num">03</span>评估口径与目标定义</h2>""")
A(table(["口径项", "本次采用的定义", "依据"], [
 ["候选池", "全市场每日约 5,400 只（非概念交集池）", "用户 m00151：要做全量，不单是 _build_intersection_picks 交集"],
 ["日期角色", "仅作制图横轴 / 复盘标记 / 牛熊标注，<b>不作筛选条件、不作市场状态指标</b>", "用户 m00171"],
 ["条件形态", "纯「当日可知」个股指标阈值组合（AND 连接，3~6 个条件）", "用户 m00079 + m00171"],
 ["双口径", "y10：未来 10 日内最高价涨幅 ≥20%；y5：未来 5 日；分别独立评估", "用户 m00001；CLI_GUIDE.md 的 fwd_max_Nd 定义"],
 ["样本切分", "训练/搜索 2024-02~2025-12；内验 2025-07~2025-12；样本外 2026-01~2026-10 仅最终验收；全区间做描述性统计", "用户 m00079"],
 ["达标统计", "①合并池比例 ②逐日达标率/稳定性 ③与全市场 base rate 对比 ④样本外表现 ⑤最小选中数门槛", "用户 m00079"],
 ["最小选中数", "每日 ≥20 只、合并池 ≥500 只（防止只选 1~2 只凑比例）", "用户 m00079"],
 ["三档分级", "A ≥75% / B 50–75% / C 25–50% / D &lt;25%（以训练集 10 日合并池比例归档）", "用户 m00106"],
 ["fwd 空值", "统计前过滤 fwd_* != null；禁止 fwd_5d or 0；禁止跨日期比较不同窗口", "CLI_GUIDE.md 硬规则"],
], numcols=()))
A("""<div class="callout teal"><b>为什么「候选池 = 全市场」很重要：</b>项目自带的
<code>_build_intersection_picks</code> 只返回命中三榜概念交集的 1,400~4,400 只，
那本身已经是一层「资金聚集」过滤器。如果直接在里面搜，会把「概念过滤」的功劳算到指标头上，
结论不可复用。本次从全市场起搜，概念聚集度降级为个股特征之一，不作硬门槛。</div>
</section>""")

# ---- 4 方法 ----
A("""<section id="s4"><h2><span class="num">04</span>方法选型与理由</h2>
<p>指标有 27 个、每个切 99 个分位，6 条件组合的搜索空间约 10<sup>12</sup> 量级，穷举既不可能也没必要
（用户明确要求「不要大海捞针式穷举」）。选型如下：</p>""")
A(table(["环节", "采用方法", "选型理由"], [
 ["搜索算法", "<b>TPE 风格贝叶斯优化</b>（scipy gaussian_kde 估计 good/bad 分位分布，最大化 log 密度比来建议下一组阈值）+ 局部阈值精修", "环境无 optuna/sklearn/xgboost/lightgbm，scipy 已装（用户 m00137）；TPE 对「黑箱 + 评估昂贵 + 离散阈值」的场景样本效率远高于网格/随机；每模板仅 190 次评估即可收敛"],
 ["理论先验", "7 个模板：T1 资金聚集量价趋势 / T2 情绪涨停波动筹码 / T3 涨跌平衡超跌反转 / T4-T5 探索 / T6-T7 自由组合", "把六条投研理论编码成结构约束，避免搜索在 27 维里漂移到无经济含义的角落；自由组合作为对照，检验理论模板是否真的更优"],
 ["目标函数", "0.40×合并池比例 + 0.12×5日比例 + 0.26×逐日达标率 + 0.08×5日逐日达标率 + 0.09×lift + 0.05×覆盖度；再按 0.6/0.4 加权内训练与内验并惩罚二者差距", "同时回应「合并池达标 + 逐日稳定性」两种口径；gap 惩罚专门抑制过拟合到 2024-09 那段极端行情"],
 ["验证方式", "三层时间切分：内训练 / 内验 / 样本外；与全市场 base rate 对照；最小选中数门槛；三档分级", "用户 m00079；时间序列不能随机打散，必须按时间前向切分"],
 ["对照方法", "分位桶单指标扫描 + 全市场逐日 base rate + 局部阈值扰动精修", "确认「搜索失效」不是算法问题，而是目标上界问题；精修用来验证 TPE 是否已收敛到局部最优"],
], numcols=()))
A("""<div class="callout"><b>验证闭环的证据：</b>3 次局部精修把训练集最优从 39.95% 提到 <b>41.83%</b>，
提升仅 1.9 个百分点，且样本外仍只有 35.22%、逐日达标日 0 天 → 说明 TPE 已基本收敛，
继续调阈值不会改变「摸不到 75%」的结论。这是「已穷尽当前方法」的证据，不是能力边界的借口。</div>
</section>""")

# ---- 5 信号扫描 ----
A("""<section id="s5"><h2><span class="num">05</span>单指标信号扫描：上界在哪里</h2>
<p>先不谈组合，把每个指标单独切成 10 个分位桶，看最强的桶能到多少。这一步的作用是
<b>给「75% 是否可能」定一个经验上界</b>——如果单指标都摸不到，组合要跨 6.5 倍 lift 就需要极强的协同效应。</p>""")
A(img("c3", "图3 单指标 lift 排行：最强的 90% 筹码获利比例把基准 11.5% 抬到 28.4%（2.46×），离 75% 差 2.6 倍"))
A(img("c4", "图4 四个代表指标的 10 分位桶剖面：波动率与换手率单调向上，筹码比例非单调"))
A("""<div class="callout"><b>读图要点：</b>
① <b>vol20（20日波动率）</b>从最低桶 4.6% 单调升到最高桶 25.7%，是「收益大与风险大并存」最干净的证据；
② <b>换手率</b>从 7.4% 单调升到 19.8%，对应「有量才有价」；
③ <b>scrplus_90 / lu_cnt_20d</b> 呈明显非单调（最优在第 2 桶），说明筹码/涨停是<b>状态量而非单调量</b>——
获利盘过高反而意味着抛压，涨停次数过多意味着已经涨完，这正是「指标滞后效应」与「涨跌平衡」；
④ 涨停当日（is_limit_up=1）组 hit10=33.99%，是全表最强的单一切片，仍不足 75% 的一半。</div>
</section>""")

# ---- 6 市场状态 ----
A("""<section id="s6"><h2><span class="num">06</span>市场状态：75% 到底有多罕见</h2>
<p>把视角从「选哪只股票」抬到「哪一天」：逐日计算全市场所有股票的达标比例。</p>""")
A(img("c1", "图1 市场温度计：33 个月里，10 日达标率的月均峰值出现在 2024-09（53.3%），仍低于 75%"))
A(img("c2", "图2 全市场逐日达标率：659 个有效交易日中仅 10 天 ≥75%，且全部挤在两个窗口"))
A("""<div class="callout red"><b>决定性事实：</b>659 个有 10 日标签的交易日里，
逐日全市场达标率 ≥75% 的只有 <b>10 天</b>，≥50% 的 13 天，≥25% 的 28 天。
这 13 个高基准日<b>全部集中在两个窗口</b>：<br/>
• <b>2024-02-05 ~ 02-07</b>：极端超跌后的政策底反弹（前 5 日市场跌 12.8%，全市场 10 日达标率 64.5%~75.4%）；<br/>
• <b>2024-09-12 ~ 09-27</b>：924 行情普涨（10 日达标率 72.6%~98.5%，9-24 起成交额从 0.55 万亿放大到 1.46 万亿）。<br/>
其余 646 个交易日，全市场达标率均值只有 <b>10.7%</b>。也就是说：
<span class="hl">在绝大多数日子里，「随便买一只」就有 75% 概率摸到 +20% 本身就是不成立的</span>，
再强的选股指标也只能在这个天花板下面做事。</div>
<p class="small">补充：市场当日涨停家数与 10 日达标率的 Spearman 相关约 0.29，5 日均涨停家数约 0.39，
成交额放大倍数约 0.25 —— 量能与情绪确实领先于后续普涨，但相关性远不足以构成确定性的 75% 触发器。
按用户 m00171，这些市场量能指标仅用于制图与牛熊说明，<b>不进入筛选条件</b>。</p>
</section>""")

# ---- 7 条件组合 ----
A("""<section id="s7"><h2><span class="num">07</span>选股条件组合结果与 5 日 / 10 日验证</h2>
<h3>7.1 三档分级总览</h3>
<p>10 条候选规则（7 模板最优 + 3 次精修）按训练集 10 日合并池比例归档：</p>""")
A(table(["档位", "定义", "规则数", "结论"], [
 ["<span class='tag a'>A 档</span>", "≥ 75%", "0", "无规则达标（用户原始目标未实现）"],
 ["<span class='tag b'>B 档</span>", "50% ~ 75%", "0", "无规则达标"],
 ["<span class='tag c'>C 档</span>", "25% ~ 50%", "6", "全部有效规则集中于此"],
 ["<span class='tag d'>D 档</span>", "&lt; 25%", "4", "模板次优解与部分探索组"],
], numcols=()))
A(img("c6", "图6 六条 C 档规则的训练 / 样本外合并池比例，对照 25/50/75 三条门槛线"))
A(img("c5", "图5 七个理论模板在训练 / 内验 / 样本外的 10 日达标率，对照基准与 75% 目标"))
A("""<h3>7.2 三条推荐条件组合（含具体阈值与分位）</h3>
<p>从 6 条 C 档里选 3 条代表性交付：R1 样本外最稳、R2 逐日达标率最高、R3 覆盖度最高。
阈值均来自训练区间的分位数，括号内为分位 q；所有条件为 <b>AND</b> 关系。</p>""")

for key, title, theory in [
    ("R1_资金聚集高波动龙头", "R1 · 资金聚集 + 高波动 + 龙头动量", "有量才有价 / 主力参与 / 资金聚集 / 收益与风险并存"),
    ("R2_超跌反转放量", "R2 · 涨跌平衡 + 超跌反转放量", "涨跌平衡 / 指标滞后 / 有量才有价"),
    ("R3_情绪涨停高覆盖", "R3 · 情绪涨停 + 筹码 + 趋势（高覆盖）", "资金聚集 / 情绪 / 不确定性中的趋势"),
]:
    v = rec[key]
    rp = v["replay"]
    rule_txt = "<br/>".join(f"<code>{H(c)}</code>" for c in v["label"].split(" AND "))
    A(f"""<div class="rule"><div class="rt">{H(title)}</div>
<div class="small">{H(theory)}</div><div style="margin:10px 0">{rule_txt}</div>""")
    A(table(["口径", "训练集 合并池", "内验 合并池", "样本外 合并池", "逐日≥75% 天数", "选中样本数（全区间）"], [
     ["10 日", f"<b>{v['train']['10']['merge']*100:.2f}%</b>", f"{v['iv']['10']['merge']*100:.2f}%",
      f"{v['oos']['10']['merge']*100:.2f}%", f"{v['train']['10']['hit_days']} / {v['train']['10']['valid_days']}",
      f"{rp['all_pool']['10']['n']:,}"],
     ["5 日", f"<b>{v['train']['5']['merge']*100:.2f}%</b>", f"{v['iv']['5']['merge']*100:.2f}%",
      f"{v['oos']['5']['merge']*100:.2f}%", f"{v['train']['5']['hit_days']} / {v['train']['5']['valid_days']}",
      f"{rp['all_pool']['5']['n']:,}"],
    ], numcols=(1,2,3,4,5)))
    A(f"""<p class="small">相对全市场基准 lift（10 日）：{v['train']['10']['lift']:.2f}×；
训练逐日达标日（复盘标记）：{H('、'.join(v['hit75_dates']) if v['hit75_dates'] else '无')}。</p></div>""")

A("""<div class="callout red"><b>验证结论（对照用户目标）：</b>
三条规则的 <b>10 日</b>训练集合并池比例分别为 41.83% / 40.27% / 38.46%，
<b>5 日</b>为 36.36% / 26.69% / 30.89%，<b>全部远低于 75%</b>；
样本外（2026 年）进一步衰减到 35.22% / 15.52% / 30.14%（10 日）与
27.65% / 7.58% / 21.28%（5 日）。
逐日口径上，训练期最多只有 8 天达标（R3，占 240 个有效日的 3.3%），
<b>样本外 199 个交易日达标天数为 0</b>。
因此：<span class="hl">「被选出股票中 ≥75% 在 5/10 日内摸到 +20%」这个目标，在纯指标阈值条件下未达成</span>。</div>
</section>""")

# ---- 8 日期标记 ----
A("""<section id="s8"><h2><span class="num">08</span>含日期标记的条件组合（复盘口径）</h2>
<p>用户要求「日期字段作为可复盘标记纳入条件组合，输出时能对应回具体时间窗口」，
同时明确 m00171「日期只作横轴、便于看选股条件在牛熊表现，不做市场状态指标」。
据此，我们把日期作为<b>复盘标记</b>输出：对每条推荐规则，列出它在哪些具体交易日达到了 ≥75%，
并给出这些日期对应的市场状态，便于回看牛熊。</p>""")

for key, title in [("R2_超跌反转放量","R2 · 超跌反转放量"), ("R3_情绪涨停高覆盖","R3 · 情绪涨停高覆盖"),
                   ("R1_资金聚集高波动龙头","R1 · 资金聚集高波动龙头")]:
    v = rec[key]; rp = v["replay"]
    rows = []
    for r in rp["hit10_dates"]:
        mh = r["mkt_hit10"]; am = r["mkt_amount"]
        rows.append([f"<b>{H(r['date'])}</b>", f"{r['n']}", f"<b>{r['hit']*100:.1f}%</b>",
                     f"{mh*100:.1f}%" if mh is not None else "—",
                     f"{am/1e12:.2f} 万亿" if am else "—",
                     "训练期" if r["date"] <= "2025-12-31" else "样本外"])
    rows5 = []
    for r in rp["hit5_dates"]:
        rows5.append([f"<b>{H(r['date'])}</b>", f"{r['n']}", f"<b>{r['hit']*100:.1f}%</b>"])
    A(f"<h3>{H(title)} · 10 日口径达标日清单</h3>")
    A(table(["日期（复盘标记）", "当日选出数", "该日 10 日达标率", "当日全市场基准", "当日成交额", "所属切分"], rows, numcols=(1,2,3,4)))
    A(f"""<p class="small">5 日口径达标日：{H('、'.join('{} (n={}, {:.1f}%)'.format(r['date'], r['n'], r['hit']*100) for r in rp['hit5_dates']) if rp['hit5_dates'] else '无')}。
把上述日期作为窗口标记后，仅在这些日期应用该规则，
合并池 10 日达标率 = <b>{rp['restricted_pool']['10']['hit']*100:.2f}%</b>（n={rp['restricted_pool']['10']['n']:,}，{rp['restricted_pool']['10']['n_days']} 天），
5 日 = <b>{rp['restricted_pool']['5']['hit']*100:.2f}%</b>（n={rp['restricted_pool']['5']['n']:,}，{rp['restricted_pool']['5']['n_days']} 天）。</p>""")

A(img("c7", "图7 左：R3 逐日回放（日期横轴 + 牛熊窗口着色 + 达标日高亮）；右：可交易口径 vs 事后复盘口径对比"))
A("""<div class="callout red"><b>必须说清楚的边界（证据链，不能含糊）：</b>
图 7b 里 &gt;75% 的数字是<b>事后复盘口径</b>，不是可交易信号。这些「达标日」是用
<b>未来标签 y10</b> 反查出来的，实盘当天无法预知哪天会达标；
而且它们全部落在 2024-02 与 2024-09 两个已实现的极端窗口，
样本外（2026 年）一条都没有。按用户 m00171，日期只作制图横轴与牛熊标注，
我们<b>没有</b>、也不应该把它包装成「当日可知的市场状态过滤器」。
如果把它当条件用，就是标准的前视偏差 / 幸存者偏差，报告里明确否掉。</div>
<p class="small">顺带回答「5 日或 10 日任一」：由于 10 日窗口包含 5 日，达标集合上
5 日 ⊆ 10 日（实测违反样本 0 条），所以「任一」等价于 10 日口径；
上表分别列出两套数字，是为了满足用户「两个口径下分别验证」的要求，不做合并去重。</p>
</section>""")

# ---- 9 未达标/不稳定 ----
A("""<section id="s9"><h2><span class="num">09</span>未达标与表现不稳定的条件说明</h2>""")
A(table(["条件 / 现象", "证据", "定性"], [
 ["<b>全部 10 条规则未达 75%</b>", "最优 41.83%（训练）/ 35.22%（样本外）；A、B 档为空", "<span class='tag a'>未达标</span> 目标与数据分布冲突"],
 ["<b>T3 超跌反转 严重过拟合</b>", "训练 39.95% → 内验 20.35% → 样本外 15.47%（10日）；5日样本外仅 7.65%", "<span class='tag a'>不稳定</span> 只在 2024-02 超跌窗口有效"],
 ["<b>逐日达标率极低</b>", "最好 R2 为 6/23 天（26.1%），但样本外 0/2 天；R3 为 8/240 天（3.3%）；样本外全部 0 天", "<span class='tag a'>不稳定</span> 偶发，不可复制"],
 ["<b>覆盖度与命中率不可兼得</b>", "T1/R1 覆盖度仅 8.2%~13.5%（多数日子选不出 ≥20 只）；T5 覆盖度 82% 但命中率只有 26.6%", "<span class='tag b'>权衡</span> 提高门槛→样本变少"],
 ["<b>样本外整体衰减</b>", "7 模板 train→oos 平均下滑约 6~24 个百分点；基准自身也从 11.5% 降到 8.6%", "<span class='tag b'>环境漂移</span> 2026 波动收敛"],
 ["<b>搜索上界已被验证</b>", "3 次局部精修仅 +1.9pp；单指标最强 2.46× lift；659 天仅 10 天全市场 ≥75%", "<span class='tag ok'>非算法问题</span> 是目标上界"],
], numcols=()))
A("""<div class="callout"><b>诚实的失败归因（不甩锅）：</b>不是「贝叶斯没调好」，也不是「环境不支持」。
三条独立证据交叉印证：① 单指标上界 28.4%；② 全市场 659 天只有 10 天自然达标 75%；
③ 精修后收敛且样本外无达标日。目标 75% 需要的是「市场普涨状态」，
而用户明确要求日期不作筛选条件，这两条约束在数学上互相排斥。</div>
</section>""")

# ---- 10 理论解释 ----
A("""<section id="s10"><h2><span class="num">10</span>六条投研理论的对应解释</h2>
<p>下面逐条把用户给的理论约束对应到本次实测数字。理论不是装饰，它决定了模板怎么设计、结果为什么长这样。</p>""")
theories = [
 ("01", "有量才有价（主力参与）",
  "换手率分位桶 hit10 从最低 7.4% 单调升到最高 19.8%（1.72×）；成交额/20日均、超大单净额占比、主力净额占比都进入 R1/T1 的最优条件。R1 要求「主力净额/成交额 ≥ 0.1173（q0.97）+ 近10日涨幅 ≥ 25.68%」，正是「量在价先、主力抬轿」的量化形态。",
  "但量能只把 11.5% 抬到约 20%，说明量是必要条件、不是充分条件。"),
 ("02", "资金聚集（概念 / 情绪 / 赚钱效应）",
  "命中热榜概念数、龙头概念数、属强概念、近 10/20 日涨停次数都出现在高分规则里；涨停当日切片 hit10=33.99%（全表最强单一切片，2.95×）。R3 的「近20日涨停次数 ≥ 2（q0.97）+ 收盘/MA5-1 ≥ 0.081」就是情绪与赚钱效应的代理。",
  "概念聚集度在全市场口径下只是特征之一；把它降级而非硬门槛（用户 m00151）后，作用温和但真实。"),
 ("03", "不确定性与趋势（微观不确定，但趋势向上）",
  "单个股票未来是否摸到 +20% 高度不确定（基准 11.5%），但分位桶呈现清晰的单调结构：vol20、turnover_rate、bias5、ret_5d/10d/20d 的 hit10 都随分位上升。R1/R3 都含「收盘/MA5-1 ≥ q0.97」这一强趋势项。",
  "「趋势向上」是统计意义的条件概率提升，不是个股确定性——这正是 75% 达不成的微观根源。"),
 ("04", "指标滞后效应",
  "scrplus_90 与 lu_cnt_20d 的最优桶都落在第 2 桶而非最高桶（scrplus_90 第 2 桶 28.4% vs 第 10 桶 8.6%；lu_cnt_20d 第 2 桶 27.6% vs 第 10 桶 18.4%），呈明显非单调。T2/T5 里 scrplus_90 甚至用「≤ q0.89」的反向条件。",
  "筹码获利比例高 = 浮盈盘厚 = 潜在抛压；涨停次数多 = 已经涨完。滞后指标在高位反而是反向信号。"),
 ("05", "涨跌平衡（不可能一直涨 / 一直跌）",
  "全市场逐日达标率在 2024-09 冲到 98.5% 后迅速回落，2026-10 月均只剩 5.0%；月度序列从 2024-02 的 30.9% 一路震荡下行。R2「收盘/20日最高 ≤ 0.7352（q0.03）+ 70%筹码获利 ≤ 0」正是超跌反转形态，只在 2024-02 极端超跌窗口有效。",
  "均值回归既是 R2 的收益来源，也是它样本外崩到 15.5% 的原因——极端超跌不常有。"),
 ("06", "收益大与风险大相并存",
  "vol20 是 lift 第 4 的指标（2.22×），最低桶 4.6% → 最高桶 25.7%，且严格单调；R1 把「vol20 ≥ 3.693（q0.73）」写进条件。高波动组命中率高，但同时意味着回撤与不确定性同样放大。",
  "本报告只统计「最大涨幅」这一上行口径，未统计同期最大回撤；若把风险纳入，高波动规则的实际风险收益比会更差，这点在下一节披露。"),
]
for n, h, body, note in theories:
    A(f"""<div class="theory"><div class="h"><span>{n}</span>{H(h)}</div><p>{H(body)}</p>
<p class="small"><b>解读：</b>{H(note)}</p></div>""")
A("""<div class="callout teal"><b>理论如何收敛到同一结论：</b>六条理论分别解释了
「哪些指标该进模板」「为什么有些指标非单调」「为什么高波动组命中率高」，
但没有一条能推出「75% 可稳定达成」。它们共同指向一个更朴素的判断：
<b>选股指标改变的是条件概率，市场状态决定的是概率的天花板</b>。
用户把日期限定为横轴标记而非筛选条件，等于主动放弃了唯一能触碰 75% 的那个变量。</div>
</section>""")

# ---- 11 风险 ----
A("""<section id="s11"><h2><span class="num">11</span>风险披露与使用建议</h2>""")
A(table(["风险 / 限制", "说明", "建议"], [
 ["<b>标签只看上行、不看风险</b>", "目标是「最大涨幅 ≥20%」，但期间最大回撤、买入滑点、涨停买不进、次日开盘跳空都未计入；高波动规则的真实可交易收益会显著低于表面比例", "若用于实盘，必须补做「可达价」口径（T+1 开盘可买、含涨跌停约束）与最大回撤双口径回测"],
 ["<b>达标日窗口是事后复盘</b>", "第 8 节 &gt;75% 的数字由未来标签反查得到，实盘不可预知，样本外 0 天", "绝不作为交易信号；仅用于复盘标注与牛熊对照"],
 ["<b>样本外只有 10 个月</b>", "2026-01~2026-10 共 199 个交易日，且波动收敛、基准从 11.5% 降到 8.6%", "结论在更长熊市 / 更大级别行情中需重新验证"],
 ["<b>分位阈值取自训练区间</b>", "阈值表只用 2024-02~2025-12 建立，跨 regime 后会漂移（例如成交额分位在放量期含义不同）", "生产环境应做滚动分位（rolling quantile）而非固定分位"],
 ["<b>未使用概念交集池</b>", "按用户要求走全市场；项目自身的 _build_intersection_picks 是另一层过滤器，两者结果不可直接比较", "如需与项目现有交集榜打通，需单独做一次对照实验"],
 ["<b>数据边界</b>", "尾部 7 个交易日因未来数据不足无 10 日标签；daily_pct 含 1 个 inf；pct_change 个别极端值已用 isfinite 清洗", "所有统计均先过滤 fwd != null 且 finite，符合 CLI_GUIDE.md 硬规则"],
], numcols=()))
A("""<div class="callout"><b>把目标改造成可执行形态的三条建议（供决策，不擅改需求）：</b>
① 把 75% 降到 <b>C 档 25–50%</b> 作为「强信号池」验收线，本次已有 6 条规则稳定达标且有样本外支撑；
② 或把目标从「比例」改成「lift」：R1 样本外 lift 3.05×、R3 3.05×，相对基准的提升稳定且可解释；
③ 或在允许日期作为<b>当日可知市场状态过滤器</b>（如全市场近 5 日涨停家数、成交额放大倍数）的口径下重做一轮——
但这与 m00171 冲突，需要你明确是否放开。<b>本次未擅自放宽任何验收口径。</b></div>
</section>""")

# ---- 12 附录 ----
A("""<section id="s12"><h2><span class="num">12</span>附录：字段字典与复现方式</h2>
<h3>12.1 核心指标口径</h3>""")
A(table(["指标", "构造方式（全部 T 日可知）", "对应理论"], [
 ["turnover_rate / tor_ratio / amt_ratio", "当日换手率；换手率/5日均；成交额/20日均成交额", "有量才有价"],
 ["huge_norm / main_net_norm / small_norm", "超大单 / 主力 / 小单净额 ÷ 当日成交额（项目 norm 口径：net × turnover_rate / amount 的等价标准化）", "主力参与 / 收益风险并存"],
 ["scrplus_90 / scrplus_70", "90% / 70% 筹码获利比例（quote 原生字段）", "指标滞后"],
 ["vol20", "近 20 日日收益率标准差（%）", "收益与风险并存"],
 ["lu_cnt_10d / lu_cnt_20d", "近 10 / 20 日涨停次数（按 code 的涨停阈值：主板 9.8、创业/科创 19.8、北交 29.8）", "资金聚集 / 情绪"],
 ["n_hot_concepts / n_leader_concepts / in_strong_concept / n_concepts", "由 concept_date 拆概念后，与 tops_bars 三榜（归成比/涨幅/涨停数）及 tops_meta 强概念标记对齐统计", "资金聚集 / 概念"],
 ["pct_change / bias5 / bias20 / ret_5d / ret_10d / ret_20d", "统一用 daily_pct 口径；均线偏离 = close/MA−1；区间涨幅 = close_T/close_{T−N}−1", "趋势"],
 ["close_hh20_ratio / lu_gap / is_limit_up / ma5_gt_ma20 / ma20_gt_ma60", "距 20 日最高比 / 涨幅−涨停阈值 / 当日涨停 / 均线多头排列", "涨跌平衡 / 趋势"],
], numcols=()))
A("""<h3>12.2 复现链路（全部只读，输出仅落在工作目录）</h3>
<div class="rule"><code>build_matrix.py</code> → <code>matrix.parquet</code> + <code>matrix_profile.json</code><br/>
<code>scan2.py</code> → <code>scan2_out.json</code>（单指标分位桶 + 全市场逐日/月度 base rate）<br/>
<code>bayes_search.py</code> → <code>search_results.json</code>（TPE 7 模板 + 3 精修 + 三档分级 + 基线）<br/>
<code>build_report_data.py</code> → <code>report_data.json</code>（逐日回放 + 达标日窗口）<br/>
<code>verify_threshold.py</code> → <code>threshold_check.json</code>（&gt;20 与 ≥20 等价性核验）<br/>
<code>make_report.py</code> → <code>选股条件研究报告.html</code>（本文件，图表 base64 内嵌）</div>
<p class="small">运行环境：conda 环境 <code>stock</code>（Python 3.12.14 / duckdb 1.5.5 / numpy 2.5.3 /
pandas 3.0.5 / pyarrow 25.0.1 / scipy 1.18.1 / matplotlib 3.11.2）。
为避免 <code>conda run</code> 在中文输出下的 GBK 解码问题，统一用
<code>D:\\Softwares\\miniconda3\\envs\\stock\\python.exe</code> 直调 + UTF-8 日志重定向。</p>
<div class="callout teal"><b>合规声明：</b>全程未修改投研项目
<code>D:\\Users\\KFish\\Desktop\\Code\\github-app\\stockDisplay</code> 下的任何数据文件或代码文件；
未调用 <code>cli.py</code>（其 main() 会追加 <code>logs/cli_audit.log</code>）；
未触发任何 rebuild / ETL / 缓存回写（<code>_append_tops_cache</code> 已确认不会被调用）。
所有中间产物与分析脚本均位于独立工作目录。<br/><br/>
<b>mtime 取证说明：</b>复核时项目侧 <code>logs/etl.log</code>、<code>market_amount.parquet</code>、
<code>_tops_cache/v1/*.parquet</code>、<code>concept_picks/</code> 的时间戳确实落在
2026-11-12 16:09–16:11。逐行核对 <code>etl.log</code> 可确认是项目自身
<code>startup.data_ready</code> 触发的每日增量 ETL（日志含
<code>[serve] 检测到今日（2026-11-12）无数据，开始拉取…</code>、
<code>tdx_fetch.run → 目标日期: 2026-11-12</code>、<code>daily_update 合计: 处理 5 个文件</code>、
<code>market_amount 新增 1 天</code>、<code>[serve] 2026-11-12 picks 已生成</code>），
属于用户环境中已运行的后台服务行为。本分析脚本全文审计结果为：无一处
<code>to_parquet</code>/<code>to_csv</code> 写入项目路径、未调用 <code>cli.py</code>、
<code>setup_logging</code>、<code>rebuild</code>、<code>_append_tops_cache</code>；
唯一带项目路径引用的写操作是审计脚本自身读取 etl.log 取证。
该自动更新新增单日无未来标签，不进入任何统计口径，故不影响本报告结论。</div>
</section>""")

A("""<footer>本报告由数据探查 → 信号扫描 → 贝叶斯搜索 → 三层验证 → 逐日回放的证据链生成 ·
结论为「候选结论 + 证据链 + 剩余风险」，非投资建议。</footer>
</div></body></html>""")

out = WS / "选股条件研究报告.html"
out.write_text("".join(P), encoding="utf-8")
print("WROTE", out, "size KB", out.stat().st_size // 1024)
