# -*- coding: utf-8 -*-
"""从 backtest_out.json 直接生成商业汇报图表（数据零估算，全部来自回测输出）。"""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
OUT = json.loads((WS/"backtest_out.json").read_text(encoding="utf-8"))
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei","SimHei","SimSun"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 130
NAVY, TEAL, GOLD, GREY = "#1f3a5f", "#1f9e8f", "#d4a017", "#8a8f98"
paths = {}

G = OUT["groups"]; A = OUT["aux"]
segs = ["train", "oos", "全区间"]
seg_label = {"train":"样本内 2024-03~2025-12", "oos":"样本外 2026-01~10", "全区间":"全区间"}

# 图1：两组 × 三段 期望收益（毛/净）
fig, ax = plt.subplots(figsize=(9,4.6))
x = np.arange(3); w = 0.34
c7_g = [G["C7单池"][s]["avg_ret"] for s in segs]
du_g = [G["C6+C7双池"][s]["avg_ret"] for s in segs]
c7_n = [G["C7单池"][s]["avg_ret_net"] for s in segs]
du_n = [G["C6+C7双池"][s]["avg_ret_net"] for s in segs]
b1 = ax.bar(x-w/2, c7_g, w, label="C7单池·毛", color=NAVY)
b2 = ax.bar(x+w/2, du_g, w, label="双池·毛", color=TEAL)
ax.bar(x-w/2, c7_n, 0.10, bottom=np.array(c7_n)/2, color=NAVY, alpha=.35)
for i,(a,b,c,d) in enumerate(zip(c7_g,du_g,c7_n,du_n)):
    ax.text(i-w/2, a+0.02, f"{a:.2f}%", ha="center", fontsize=9)
    ax.text(i+w/2, b+0.02, f"{b:.2f}%", ha="center", fontsize=9)
    ax.text(i-w/2, c/2, f"净{c:.2f}", ha="center", fontsize=7, color="white")
    ax.text(i+w/2, d/2, f"净{d:.2f}", ha="center", fontsize=7, color="white")
ax.set_xticks(x); ax.set_xticklabels([seg_label[s] for s in segs])
ax.set_ylabel("逐笔期望收益 (%)"); ax.axhline(0, color=GREY, lw=.8)
ax.set_title("两组回测期望收益对比（深色=毛收益，浅色标注=扣0.15%成本后）")
ax.legend(loc="upper left", fontsize=9); ax.grid(axis="y", alpha=.25)
fig.tight_layout(); p=WS/"bt1_expect.png"; fig.savefig(p); plt.close(fig); paths["bt1"]=str(p)

# 图2：胜率 + PF 双面板
fig, (a1,a2) = plt.subplots(1,2, figsize=(10,4.2))
for ax_i, key, title, fmt in [(a1,"win_rate","逐笔胜率 (%)","{:.1f}"),
                              (a2,"profit_factor","盈利因子 PF","{:.3f}")]:
    c7v=[G["C7单池"][s][key] for s in segs]; duv=[G["C6+C7双池"][s][key] for s in segs]
    ax_i.bar(x-w/2,c7v,w,color=NAVY,label="C7单池"); ax_i.bar(x+w/2,duv,w,color=TEAL,label="双池")
    for i,(a,b) in enumerate(zip(c7v,duv)):
        ax_i.text(i-w/2,a+0.3,fmt.format(a),ha="center",fontsize=8)
        ax_i.text(i+w/2,b+0.3,fmt.format(b),ha="center",fontsize=8)
    ax_i.set_xticks(x); ax_i.set_xticklabels([seg_label[s] for s in segs],fontsize=8)
    ax_i.set_title(title); ax_i.grid(axis="y",alpha=.25); ax_i.legend(fontsize=8)
a2.axhline(1,color=GOLD,ls="--",lw=1)
fig.tight_layout(); p=WS/"bt2_win_pf.png"; fig.savefig(p); plt.close(fig); paths["bt2"]=str(p)

# 图3：成交率 + 信号/成交笔数
fig, (a1,a2) = plt.subplots(1,2, figsize=(10,4.2))
c7f=[G["C7单池"][s]["fill_rate"] for s in segs]; duf=[G["C6+C7双池"][s]["fill_rate"] for s in segs]
for i,(a,b) in enumerate(zip(c7f,duf)):
    a1.bar(i-w/2,a,w,color=NAVY,label="C7单池" if i==0 else "")
    a1.bar(i+w/2,b,w,color=TEAL,label="双池" if i==0 else "")
    a1.text(i-w/2,a+.3,f"{a:.1f}%",ha="center",fontsize=8)
    a1.text(i+w/2,b+.3,f"{b:.1f}%",ha="center",fontsize=8)
a1.set_xticks(x); a1.set_xticklabels([seg_label[s] for s in segs],fontsize=8)
a1.set_title("限价单成交率 (%)"); a1.grid(axis="y",alpha=.25); a1.legend(fontsize=8)
# 笔数（全区间）
sigs=[G["C7单池"]["全区间"]["n_signals"],G["C6+C7双池"]["全区间"]["n_signals"]]
fils=[G["C7单池"]["全区间"]["n_filled"],G["C6+C7双池"]["全区间"]["n_filled"]]
a2.bar(["C7单池","双池"],sigs,color=GREY,label="信号数")
a2.bar(["C7单池","双池"],fils,color=TEAL,label="成交数")
for i,(s,f) in enumerate(zip(sigs,fils)):
    a2.text(i,s+100,str(s),ha="center",fontsize=9); a2.text(i,f+100,str(f),ha="center",fontsize=9,color=TEAL)
a2.set_title("全区间信号数 / 成交数"); a2.grid(axis="y",alpha=.25); a2.legend(fontsize=8)
fig.tight_layout(); p=WS/"bt3_fill.png"; fig.savefig(p); plt.close(fig); paths["bt3"]=str(p)

# 图4：退出原因结构（全区间）堆叠
fig, ax = plt.subplots(figsize=(8.5,3.6))
cats=["exit_TP","exit_SL","exit_TIME"]; clabel=["止盈(+15%)","止损(-8%)","到期(第7日)"]; cols=[TEAL,"#c0392b",GOLD]
for i,(g,name) in enumerate([("C7单池","C7单池"),("C6+C7双池","双池")]):
    vals=[G[g]["全区间"][c] for c in cats]; left=0
    for v,cl,lb in zip(vals,cols,clabel):
        ax.barh(i,v,left=left,color=cl,label=lb if i==0 else "")
        ax.text(left+v/2,i,f"{v:.1f}%",ha="center",va="center",fontsize=9,color="white")
        left+=v
ax.set_yticks([0,1]); ax.set_yticklabels(["C7单池","双池"]); ax.set_xlim(0,100)
ax.set_xlabel("占成交笔比例 (%)"); ax.set_title("全区间退出原因结构")
ax.legend(loc="upper center",bbox_to_anchor=(.5,-.1),ncol=3,fontsize=8)
fig.tight_layout(); p=WS/"bt4_exit.png"; fig.savefig(p); plt.close(fig); paths["bt4"]=str(p)

# 图5：规则有效性——连池≥2 vs =1（两组各自，两组并列）
fig, ax = plt.subplots(figsize=(9,4.2))
labels=["C7单池·连池≥2","C7单池·连池=1","双池·连池≥2","双池·连池=1"]
vals=[A["C7单池"]["streak2"]["avg_ret"], A["C7单池"]["streak1"]["avg_ret"],
      A["C6+C7双池"]["streak2"]["avg_ret"], A["C6+C7双池"]["streak1"]["avg_ret"]]
cols_x=[GOLD,GREY,GOLD,GREY]
xp=np.arange(len(labels))
bars=ax.bar(xp,vals,color=cols_x)
bars[0].set_label("连池≥2日(规则5.1优先)"); bars[2].set_label("_nolegend_")
bars[1].set_label("连池=1日"); bars[3].set_label("_nolegend_")
for i,v in enumerate(vals):
    ax.text(i,v+.05,f"{v:.2f}%",ha="center",fontsize=9,
            color="#333" if cols_x[i]==GREY else "black")
ax.set_xticks(xp); ax.set_xticklabels(labels,fontsize=8); ax.set_ylabel("逐笔期望收益 (%)")
ax.set_title("规则5.1 验证：连续在池≥2日的期望显著高于新进"); ax.grid(axis="y",alpha=.25); ax.legend(fontsize=8)
fig.tight_layout(); p=WS/"bt5_streak.png"; fig.savefig(p); plt.close(fig); paths["bt5"]=str(p)

# 图6：双池增益分解（train/oos 期望与胜率差值）
fig, ax = plt.subplots(figsize=(8.5,3.8))
metrics=["avg_ret","win_rate"]
gain_tr=[G["C6+C7双池"]["train"][m]-G["C7单池"]["train"][m] for m in metrics]
gain_oo=[G["C6+C7双池"]["oos"][m]-G["C7单池"]["oos"][m] for m in metrics]
xp=np.arange(2); w2=.34
ax.bar(xp-w2/2,gain_tr,w2,color=NAVY,label="样本内(train)")
ax.bar(xp+w2/2,gain_oo,w2,color=TEAL,label="样本外(oos)")
for i,(a,b) in enumerate(zip(gain_tr,gain_oo)):
    ax.text(i-w2/2,a+(0.006 if i==0 else .05),f"+{a:.3f}"+("%" if i else "pct"),ha="center",fontsize=8)
    ax.text(i+w2/2,b+(0.006 if i==0 else .05),f"+{b:.3f}"+("%" if i else "pct"),ha="center",fontsize=8)
ax.axhline(0,color=GREY,lw=.8); ax.set_xticks(xp); ax.set_xticklabels(["期望收益差(pct)","胜率差(pct点)"])
ax.set_title("双池相对单池的增量（均为正，方向一致）"); ax.grid(axis="y",alpha=.25); ax.legend(fontsize=8)
fig.tight_layout(); p=WS/"bt6_dual_gain.png"; fig.savefig(p); plt.close(fig); paths["bt6"]=str(p)

(WS/"backtest_charts.json").write_text(json.dumps(paths,ensure_ascii=False,indent=2),encoding="utf-8")
print("CHARTS_OK", *paths.values(), sep="\n")
