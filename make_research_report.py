# -*- coding: utf-8 -*-
"""生成商业级研究报告 HTML：情绪+资金筹码+高波动 三条件叠加因子的增量归因。
纯读工作目录 JSON，输出报告到工作目录（不写项目）。图表 matplotlib base64 内嵌。
"""
from __future__ import annotations
import json, base64, io, html
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
def load(n): return json.loads((WS/n).read_text(encoding="utf-8"))
FA = load("factor_attribution_out.json")
CA = load("combo_attribution_out.json")
FE = load("focused_extras_out.json")
FS = load("final_supp_out.json")
MP = load("research_matrix_profile.json")
CD = load("c7_daily_out.json")          # C7 逐日表现 + 两次对比数字
CC = load("c7_charts.json")             # 新增 4 张图 (c8~c11)

# ---------- 绘图样式 ----------
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False
C_BLUE, C_ORANGE, C_GREEN, C_RED, C_GRAY = '#1e3a5f', '#e8833a', '#2e8b6f', '#c0392b', '#95a5a6'
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = '#fafbfc'
plt.rcParams['axes.grid'] = True
plt.rcParams['grid.alpha'] = 0.3
plt.rcParams['axes.spines.top'] = False
plt.rcParams['axes.spines.right'] = False

def b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight')
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()

def img(tag):
    return f'<div class="chart"><img src="data:image/png;base64,{tag}" alt="图表"></div>'

CHARTS = {}
# 追加 C7 逐日/牛熊/对比四图（由 generate_c7_charts.py 产出）
for _k in ('c8','c9','c10','c11'):
    CHARTS[_k] = CC[_k]

# C7 逐日统计（供第13节表格）
C7_OV  = CD['overall']
C7_SP  = CD['by_split']
C7_RG  = CD['by_regime']
FR1    = CD['first_report_r1']
C7_TH  = CD['thresholds']

# 图1 组合递进 hit10 train vs oos
names = ["L0 基准池(情绪+资金+高波动)","L1 +近涨停(进攻启动)","L2 +逼近日高(突破前夜)","L3 +龙头概念","L5' +多头排列","L5 +短期动量(R80)","L6 全叠加(动量+多头+市场+小单)"]
short_names = ["基准三类","+近涨停","+逼近日高","+龙头概念","+多头排列","+短期动量","全叠加"]
trh = [CA['train'][n]['y10']['hit']*100 for n in names]
ooh = [CA['oos'][n]['y10']['hit']*100 for n in names]
x = np.arange(len(names)); w=0.38
fig,ax=plt.subplots(figsize=(11,5))
ax.bar(x-w/2,trh,w,label='训练期 2024-02~2025-12',color=C_BLUE)
ax.bar(x+w/2,ooh,w,label='样本外 2026-01~2026-10',color=C_ORANGE)
ax.axhline(75,color=C_RED,ls='--',lw=1.5,label='目标线 75%')
ax.set_ylabel('未来10日最大涨幅>20% 命中率 (%)'); ax.set_ylim(0,80)
ax.set_xticks(x); ax.set_xticklabels(short_names,rotation=18,ha='right',fontsize=9)
ax.set_title('图1  组合递进：叠加因子后命中率（5日/10日双口径中的10日）',fontsize=12,fontweight='bold')
ax.legend(fontsize=9)
for i,(a,b) in enumerate(zip(trh,ooh)):
    ax.text(i-w/2,a+1,f'{a:.1f}',ha='center',fontsize=8,color=C_BLUE)
    ax.text(i+w/2,b+1,f'{b:.1f}',ha='center',fontsize=8,color=C_ORANGE)
CHARTS['c1']=b64(fig)

# 图2 因子稳健性散点 train vs oos delta10
rob=CA['robustness']
fac=list(rob.keys())
td=[rob[k]['train_delta10']*100 for k in fac]
od=[rob[k]['oos_delta10']*100 for k in fac]
colors=[]
for k in fac:
    v=rob[k]['verdict']
    colors.append(C_GREEN if v=='稳健有效' else (C_ORANGE if '方向一致' in v else C_RED))
fig,ax=plt.subplots(figsize=(9.5,6.5))
ax.scatter(td,od,c=colors,s=70,alpha=.85,edgecolors='white',linewidth=.8)
for k,a,b in zip(fac,td,od):
    ax.annotate(k.replace('概念-','概:').replace('市场-','市:').replace('其他-',''),
                (a,b),fontsize=7.5,xytext=(4,3),textcoords='offset points')
ax.axhline(0,color=C_GRAY,lw=1); ax.axvline(0,color=C_GRAY,lw=1)
ax.set_xlabel('训练期 hit10 提升 (百分点)'); ax.set_ylabel('样本外 hit10 提升 (百分点)')
ax.set_title('图2  单因子稳健性：训练期 vs 样本外提升（绿=稳健 橙=单侧 红=不稳定）',fontsize=12,fontweight='bold')
CHARTS['c2']=b64(fig)

# 图3 概念两口径对比（基准池进攻池C2上）
cb=CA['concept_branch']
groups=["当日强榜","主线延续","退出榜但主线未结束"]
for sp,c in [('train',C_BLUE),('oos',C_ORANGE)]:
    pass
fig,ax=plt.subplots(figsize=(9,5))
cats=["当日强榜(仅看当日)","主线延续(历史强>=2)"]
for sp,col,off in [('train',C_BLUE,-0.2),('oos',C_ORANGE,0.2)]:
    vals=[cb[sp][g]['y10']*100 for g in groups[:2]]
    ax.bar(np.arange(2)+off,vals,0.4,label=sp,color=col)
    for i,v in enumerate(vals): ax.text(i+off,v+1,f'{v:.1f}',ha='center',fontsize=9,color=col)
ax.set_xticks(range(2)); ax.set_xticklabels(cats,fontsize=10)
ax.set_ylabel('hit10 (%)'); ax.set_ylim(0,42)
ax.set_title('图3  概念口径对照：只看当日榜单 vs 看主线是否延续',fontsize=12,fontweight='bold')
ax.legend()
CHARTS['c3']=b64(fig)

# 图4 滞后曲线 y5/y7/y10/y12
lag=FE['lag_curve']
labs=['5日','7日(放宽2日)','10日','12日(放宽2日)']
fig,ax=plt.subplots(figsize=(9,5))
for sp,col,mk in [('train',C_BLUE,'o'),('oos',C_ORANGE,'s')]:
    vals=[lag[sp]['y5']*100,lag[sp]['y7']*100,lag[sp]['y10']*100,lag[sp]['y12']*100]
    ax.plot(labs,vals,marker=mk,lw=2.2,color=col,label=sp)
    for i,v in enumerate(vals): ax.text(i,v+1.2,f'{v:.1f}',ha='center',fontsize=9,color=col)
ax.set_ylabel('命中率 (%)'); ax.set_ylim(0,45)
ax.set_title('图4  1-2日滞后处理：放宽观察窗口后的概率变化（C6双叠加池）',fontsize=12,fontweight='bold')
ax.legend()
CHARTS['c4']=b64(fig)

# 图5 scrplus 真值轨道
scr=FE['scrplus_track']['layers']
sn=list(scr.keys())
lo=[scr[k]['hit10_all']*100 for k in sn]
hi=[scr[k]['hit10_high']*100 for k in sn]
fig,ax=plt.subplots(figsize=(10,5))
x=np.arange(len(sn)); w=.38
ax.bar(x-w/2,lo,w,label='筹码集中度低于中位',color=C_GRAY)
ax.bar(x+w/2,hi,w,label='筹码集中度高于中位',color=C_GREEN)
ax.set_xticks(x); ax.set_xticklabels(sn,fontsize=9)
ax.set_ylabel('hit10 (%)'); ax.set_ylim(0,45)
ax.set_title('图5  真实筹码集中度增量检验（仅2026-04+有真值，样本外区间）',fontsize=12,fontweight='bold')
ax.legend(fontsize=9)
for i,(a,b) in enumerate(zip(lo,hi)):
    ax.text(i+w/2,b+.8,f'+{(b-a):.1f}',ha='center',fontsize=8,color=C_GREEN)
CHARTS['c5']=b64(fig)

# 图6 过拟合：逐层叠加 train vs oos
lay_keys=["L0 基准池(情绪+资金+高波动)","L1 +近涨停(进攻启动)","L2 +逼近日高(突破前夜)","L3 +龙头概念",
          "L5 +短期动量(R80)","L5' +多头排列","L5'' +市场暖(滞后赚钱+量能)","L6 全叠加(动量+多头+市场+小单)"]
lay=["L0 基准","L1 +近涨停","L2 +近高","L3 +龙头","L5 +动量","L5' +多头","L5'' +市场暖","L6 全叠加"]
trv=[CA['train'][n]['y10']['hit']*100 for n in lay_keys]
oov=[CA['oos'][n]['y10']['hit']*100 for n in lay_keys]
fig,ax=plt.subplots(figsize=(11,5))
_x=np.arange(len(lay))
ax.plot(_x,trv,marker='o',lw=2,color=C_BLUE,label='训练期')
ax.plot(_x,oov,marker='s',lw=2,color=C_ORANGE,label='样本外')
ax.set_xticks(_x); ax.set_xticklabels(lay,rotation=18,ha='right',fontsize=8.5)
ax.set_ylabel('hit10 (%)'); ax.set_ylim(15,40)
ax.set_title('图6  因子不是越多越好：全叠加时样本外命中率明显回落（过拟合信号）',fontsize=12,fontweight='bold')
ax.legend()
CHARTS['c6']=b64(fig)

# 图7 三层基准对比
fig,ax=plt.subplots(figsize=(8,5))
mkt_tr=11.54; mkt_oo=8.76
base_tr=CA['train']['L0 基准池(情绪+资金+高波动)']['y10']['hit']*100
base_oo=CA['oos']['L0 基准池(情绪+资金+高波动)']['y10']['hit']*100
best_tr=CA['train']['L3 +龙头概念']['y10']['hit']*100
best_oo=CA['oos']['L3 +龙头概念']['y10']['hit']*100
x=np.arange(3); w=.38
ax.bar(x-w/2,[mkt_tr,base_tr,best_tr],w,label='训练期',color=C_BLUE)
ax.bar(x+w/2,[mkt_oo,base_oo,best_oo],w,label='样本外',color=C_ORANGE)
ax.set_xticks(x); ax.set_xticklabels(['全市场基准','三类条件基准池','叠加最优组合'],fontsize=10)
ax.set_ylabel('hit10 (%)'); ax.set_ylim(0,42)
ax.set_title('图7  层层抬升：从全市场11.5%到组合35%（训练期）',fontsize=12,fontweight='bold')
ax.legend()
for i,(a,b) in enumerate(zip([mkt_tr,base_tr,best_tr],[mkt_oo,base_oo,best_oo])):
    ax.text(i-w/2,a+1,f'{a:.1f}',ha='center',fontsize=8,color=C_BLUE)
    ax.text(i+w/2,b+1,f'{b:.1f}',ha='center',fontsize=8,color=C_ORANGE)
CHARTS['c7']=b64(fig)

# ---------- 表格构造 ----------
def pct(x,d=2):
    return '—' if x is None else f'{x*100:.{d}f}%'

# 组合递进表
combo_rows=[]
order=["C0 基准三类","C1 +近涨停","C2 +逼近日高","C3 +龙头概念","C4 +动量","C5 +多头",
       "C6 C2+动量+多头(双叠加)","C7 C6+龙头概念","C9 C6+主线延续(宽松)","C10 C2+逼近日高+概念热(主线延续严格)"]
ckeys_train=FE['combos']['train']; ckeys_oos=FE['combos']['oos']
for nm in order:
    a=ckeys_train.get(nm); b=ckeys_oos.get(nm)
    if not a or not b: continue
    combo_rows.append(f"""<tr><td class='l'>{nm}</td>
      <td>{a['n']:,}</td><td>{pct(a['y5']['hit'])}</td><td class='hi'>{pct(a['y10']['hit'])}</td>
      <td>{a['y10']['lift']}×</td><td>{b['n']:,}</td><td>{pct(b['y5']['hit'])}</td>
      <td class='hi'>{pct(b['y10']['hit'])}</td><td>{b['y10']['lift']}×</td></tr>""")
COMBO_TBL="\n".join(combo_rows)

# 稳健性表
rob_rows=[]
for k,v in CA['robustness'].items():
    cls='ok' if v['verdict']=='稳健有效' else ('warn' if '方向一致' in v['verdict'] else 'bad')
    p1='—' if v['train_p'] is None else (f"{v['train_p']:.3f}" if v['train_p']>=0.001 else '<0.001')
    p2='—' if v['oos_p'] is None else (f"{v['oos_p']:.3f}" if v['oos_p']>=0.001 else '<0.001')
    rob_rows.append(f"<tr><td class='l'>{k}</td><td>{v['train_delta10']*100:+.2f}pct</td><td>{p1}</td>"
                    f"<td>{v['oos_delta10']*100:+.2f}pct</td><td>{p2}</td>"
                    f"<td class='{cls}'>{v['verdict']}</td></tr>")
ROB_TBL="\n".join(rob_rows)

# 概念两口径表
conc_rows=[]
for gn in ["当日强榜","主线延续","退出榜但主线未结束"]:
    a=CA['concept_branch']['train'][gn]; b=CA['concept_branch']['oos'][gn]
    conc_rows.append(f"<tr><td class='l'>{gn}</td><td>{a['n']:,}</td><td>{pct(a['y5'])}</td><td>{pct(a['y10'])}</td>"
                     f"<td>{b['n']:,}</td><td>{pct(b['y5'])}</td><td>{pct(b['y10'])}</td></tr>")
CONC_TBL="\n".join(conc_rows)

# 滞后表
lag_rows=[]
for sp in ['train','oos']:
    l=FE['lag_curve'][sp]
    lag_rows.append(f"<tr><td class='l'>{sp}</td><td>{l['n']:,}</td><td>{pct(l['y5'])}</td><td>{pct(l['y7'])}</td>"
                    f"<td class='ok'>+{l['gain_5to7']*100:.2f}pct</td><td>{pct(l['y10'])}</td><td>{pct(l['y12'])}</td>"
                    f"<td class='ok'>+{l['gain_10to12']*100:.2f}pct</td></tr>")
LAG_TBL="\n".join(lag_rows)

# scrplus 表
scr_rows=[]
for k,v in FE['scrplus_track']['layers'].items():
    pv='—' if v['p'] is None else (f"{v['p']:.3f}" if v['p']>=0.001 else '<0.001')
    scr_rows.append(f"<tr><td class='l'>{k}</td><td>{v['n_all']:,}</td><td>{pct(v['hit10_all'])}</td>"
                    f"<td>{v['n_high']:,}</td><td>{pct(v['hit10_high'])}</td>"
                    f"<td class='ok'>+{v['delta10']*100:.2f}pct</td><td>{pv}</td></tr>")
SCR_TBL="\n".join(scr_rows)

# 退出榜宽松对照（选取有代表性的行）
off_rows=[]
for key in ["train/全样本","train/基准池C0","oos/全样本","oos/基准池C0"]:
    d=FS['offlist_defs'][key]
    off_rows.append(f"<tr><td class='l'>{key}</td><td>{d['pool_n']:,}</td><td>{pct(d['pool_hit10'])}</td>"
                    f"<td>{d['严格(构造标志n_mainline_not_onlist>=1)']['n']:,}</td>"
                    f"<td>{pct(d['严格(构造标志n_mainline_not_onlist>=1)']['hit10'])}</td>"
                    f"<td>{d['宽松(近10日强>=1 且 当日不在强榜)']['n']:,}</td>"
                    f"<td>{pct(d['宽松(近10日强>=1 且 当日不在强榜)']['hit10'])}</td></tr>")
OFF_TBL="\n".join(off_rows)

# 基础数字
tr_base=CA['train']['L0 基准池(情绪+资金+高波动)']['y10']['hit']
oo_base=CA['oos']['L0 基准池(情绪+资金+高波动)']['y10']['hit']
tr_best=FE['combos']['train']['C7 C6+龙头概念']['y10']['hit']
oo_best=FE['combos']['oos']['C7 C6+龙头概念']['y10']['hit']
micro=FS['concept_persistence_micro']
stay=micro['stay_rate']*100
avg_strong=FS['strong_list_persistence'][0]['avg_strong_per_day']

HTML=f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>选股因子增量归因研究报告</title>
<style>
:root{{--navy:#1e3a5f;--orange:#e8833a;--green:#2e8b6f;--red:#c0392b;--ink:#2c3e50;--mute:#7f8c8d;--line:#e8ecf1;--bg:#f4f6f9}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:"Microsoft YaHei","PingFang SC",sans-serif;color:var(--ink);background:var(--bg);line-height:1.75;font-size:15px}}
.wrap{{max-width:1080px;margin:0 auto;background:#fff;box-shadow:0 2px 28px rgba(30,58,95,.08)}}
header{{background:linear-gradient(135deg,#1e3a5f 0%,#2c5282 55%,#e8833a 140%);color:#fff;padding:54px 60px 44px}}
header .kicker{{font-size:13px;letter-spacing:3px;opacity:.85;text-transform:uppercase}}
header h1{{font-size:32px;margin:14px 0 10px;font-weight:800;letter-spacing:1px}}
header .sub{{font-size:16px;opacity:.92;max-width:760px}}
header .meta{{margin-top:24px;display:flex;gap:28px;flex-wrap:wrap;font-size:13px;opacity:.9}}
header .meta b{{display:block;font-size:19px;opacity:1;margin-top:3px}}
.sec{{padding:38px 60px;border-bottom:1px solid var(--line)}}
.sec:nth-child(even){{background:#fcfdfe}}
h2{{font-size:21px;color:var(--navy);margin-bottom:6px;display:flex;align-items:center;gap:12px}}
h2 .no{{background:var(--navy);color:#fff;width:30px;height:30px;border-radius:8px;display:inline-flex;align-items:center;justify-content:center;font-size:14px}}
h2 .no.o{{background:var(--orange)}}
.lead{{color:var(--mute);margin:6px 0 22px;font-size:14px}}
h3{{font-size:16px;color:var(--navy);margin:22px 0 10px}}
p{{margin:10px 0}}
.callout{{border-left:4px solid var(--orange);background:#fff8f2;padding:15px 20px;border-radius:0 8px 8px 0;margin:18px 0;font-size:14px}}
.callout.g{{border-color:var(--green);background:#f1faf6}}
.callout.r{{border-color:var(--red);background:#fdf2f1}}
.callout b{{color:var(--navy)}}
table{{width:100%;border-collapse:collapse;margin:16px 0;font-size:13px}}
th{{background:var(--navy);color:#fff;padding:11px 9px;text-align:center;font-weight:600}}
td{{padding:9px;border-bottom:1px solid var(--line);text-align:center}}
td.l{{text-align:left}}
tr:hover td{{background:#f7f9fc}}
td.hi{{color:var(--orange);font-weight:700}}
td.ok{{color:var(--green);font-weight:600}}
td.warn{{color:#b8860b;font-weight:600}}
td.bad{{color:var(--red);font-weight:600}}
.chart{{margin:20px 0;text-align:center}}
.chart img{{max-width:100%;border:1px solid var(--line);border-radius:10px;box-shadow:0 2px 12px rgba(0,0,0,.05)}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:22px 0}}
.kpi{{background:#fff;border:1px solid var(--line);border-top:3px solid var(--orange);border-radius:10px;padding:16px;text-align:center}}
.kpi .v{{font-size:26px;font-weight:800;color:var(--navy)}}
.kpi .k{{font-size:12px;color:var(--mute);margin-top:4px}}
.kpi.b{{border-top-color:var(--green)}} .kpi.b .v{{color:var(--green)}}
ul,ol{{margin:10px 0 10px 24px}} li{{margin:6px 0}}
.foot{{padding:30px 60px;color:var(--mute);font-size:12px;background:#fbfcfd}}
.tag{{display:inline-block;background:#eef2f7;color:var(--navy);padding:2px 10px;border-radius:12px;font-size:12px;margin:2px}}
.badge{{display:inline-block;padding:2px 9px;border-radius:10px;font-size:12px;font-weight:600}}
@media(max-width:760px){{.sec,header,.foot{{padding:24px}}.kpis{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><div class="wrap">

<header>
 <div class="kicker">QUANTITATIVE RESEARCH · 增量归因专题</div>
 <h1>情绪 · 资金筹码 · 高波动三条件之上，什么还能再提高命中率？</h1>
 <div class="sub">在已确认的三类高收益因子基础上，系统检验强概念、市场状况与动量类因子对未来 5 / 10 日大涨（&gt;20%）概率的增量贡献——并直面筹码数据缺失、1–2 日进攻滞后、概念涨跌并存三个真实世界的复杂问题。</div>
 <div class="meta">
  <div>样本区间<b>2024-02 ~ 2026-10</b></div>
  <div>样本规模<b>3,590,923 行 / 5,741 只</b></div>
  <div>训练 / 样本外<b>463 日 / 199 日</b></div>
  <div>报告日期<b>2026-11-19</b></div>
 </div>
</header>

<div class="sec">
 <h2><span class="no">01</span>执行摘要</h2>
 <p class="lead">一句话结论：三条件基准池已把命中率抬到全市场的约 1.8–2.2 倍；在其之上，<b>近涨停、逼近日高、短期动量、多头排列、龙头概念</b>是最稳的五个增量因子，最优组合训练期 {pct(tr_best)} / 样本外 {pct(oo_best)}，但 75% 目标依旧不可达。</p>
 <div class="kpis">
  <div class="kpi"><div class="v">{pct(tr_base,1)}</div><div class="k">训练期 三条件基准池 hit10</div></div>
  <div class="kpi"><div class="v">{pct(oo_base,1)}</div><div class="k">样本外 三条件基准池 hit10</div></div>
  <div class="kpi b"><div class="v">{pct(tr_best,1)}</div><div class="k">训练期 叠加最优组合 hit10</div></div>
  <div class="kpi b"><div class="v">{pct(oo_best,1)}</div><div class="k">样本外 叠加最优组合 hit10</div></div>
 </div>
 <div class="callout g"><b>确实提高概率的因子（训练+样本外双显著）：</b>近涨停（+10.5 / +7.8 pct）、逼近日高（+6.0 / +4.1）、短期动量（+4.0 / +3.5）、多头排列（+2.1 / +3.8）、龙头概念（+3.4 / +3.1）、资金力度高分位、当日强榜、主线延续、量能放大、涨停情绪、小单流出。</div>
 <div class="callout r"><b>无效或过拟合的因子：</b>全因子堆叠加（L6）样本外回落到 25.3%（比叠加最优低约 7 pct）；"滞后赚钱效应"样本内外反向（训练 +0.6 pct、样本外 −2.9 pct）；"退出榜但主线未结束"样本极稀少（历史强概念当日仍在榜率 {stay:.2f}%），无统计效力。</div>
 {img(CHARTS['c7'])}
</div>

<div class="sec">
 <h2><span class="no o">02</span>先纠错：筹码集中度数据的真相</h2>
 <p class="lead">这是本次研究的第一个必须交代的事实修正——它直接改变了研究方法。</p>
 <p>上一轮分析中"筹码集中度第 2 分位命中率最高（约 28%）"是一个<b>数据伪影</b>。本次逐值核查发现：<b>训练期（2024-02~2025-12）的 scrplus_90 / scrplus_70 全部为 0</b>（240 万个非Null值只有 1 个唯一值）。所谓"第 2 分位最优"，是 ntile() 对一组全 0 的值按行号机械切分后形成的"日期块"假象，并非真实的筹码信号。真实值只在 <b>2026-04 之后</b>才出现。</p>
 <div class="callout"><b>方法修正（双轨制）：</b>① <b>轨道 A（全区间）</b>：用全程可得的 <span class="tag">main_net_norm 主力净额占比</span><span class="tag">huge_norm 超大单</span>作为"资金 / 筹码集中"的操作化代理，情绪用涨停次数、高波动用 vol20；② <b>轨道 B（仅 2026-04+ 样本外）</b>：单独检验真实 scrplus 筹码集中度的增量。不推翻研究意图，只校正数据口径。</div>
 <p>因此下文所有"资金筹码集中"三类条件基准池，均指<b>轨道 A 的可得性口径</b>；真实筹码集中度的结论单列于第 8 节。</p>
</div>

<div class="sec">
 <h2><span class="no">03</span>研究设计：样本、标签与防前视</h2>
 <h3>3.1 三类条件基准池（固定不变的比较基准）</h3>
 <p>用四个 T 日可知的条件锁定"情绪 + 资金筹码集中 + 高波动"标的：<span class="tag">近20日涨停≥1次（情绪）</span><span class="tag">主力净额占比&gt;0（资金/筹码）</span><span class="tag">vol20≥分位70（高波动）</span><span class="tag">换手率≥分位60（活跃）</span>。阈值全部用训练期确定，样本外直接套用。</p>
 <h3>3.2 标签口径（双口径 + 滞后窗口）</h3>
 <p>标签 = 未来 N 日内最高价相对触发日收盘价涨幅 &gt;20%。四套窗口：<span class="tag">y5 = T+1~T+5</span><span class="tag">y7 = T+1~T+7（放宽2日）</span><span class="tag">y10 = T+1~T+10</span><span class="tag">y12 = T+1~T+12（放宽2日）</span>。y5/y10 对应"当日进攻"，y7/y12 对应"放宽 2 日观察窗口"，都按<b>条件触发日归集样本</b>，未来交易日不足则标签为空。</p>
 <h3>3.3 防前视红线</h3>
 <div class="callout r">全部筛选因子仅用 T 日及之前数据。市场总命中率 mkt_hit5 / mkt_hit10 由未来收益计算，<b>含前视，一律禁止入池</b>；市场状况只用滞后赚钱效应 eff_hit10_lag（过去 11–30 日，T 日可知）、量能比、涨停家数均值等。日期只作复盘横轴与牛熊标注，不作筛选条件。</div>
 <h3>3.4 统计口径</h3>
 <p>每个因子在基准池上单独叠加，报告命中率、相对基准的 lift、提升百分点（delta），并用两比例 z 检验给出 p 值；训练与样本外同法复算。判定"稳健有效"要求：训练与样本外 delta 同号且均 p&lt;0.05。</p>
</div>

<div class="sec">
 <h2><span class="no">04</span>基准池验证：三类条件确实立住了</h2>
 <p>基准池训练期 hit10 = <b>{pct(tr_base)}</b>（全市场同期 11.54%，约 <b>{tr_base/0.1154:.2f}×</b> lift），样本外 hit10 = <b>{pct(oo_base)}</b>（全市场同期 8.76%，约 <b>{oo_base/0.0876:.2f}×</b> lift）。5 日口径训练期 {pct(CA['train']['L0 基准池(情绪+资金+高波动)']['y5']['hit'])}、样本外 {pct(CA['oos']['L0 基准池(情绪+资金+高波动)']['y5']['hit'])}，同样显著高于全市场。三类条件不是空话，是真 uplift。</p>
</div>

<div class="sec">
 <h2><span class="no o">05</span>核心结果：组合递进（增量提升表）</h2>
 <p class="lead">在基准池上按经济逻辑逐层叠加。lift 相对各自 split 的基准池。</p>
 <table><thead><tr><th rowspan="2">组合</th><th colspan="4">训练期 2024-02~2025-12</th><th colspan="4">样本外 2026-01~2026-10</th></tr>
 <tr><th>样本数</th><th>hit5</th><th>hit10</th><th>lift10</th><th>样本数</th><th>hit5</th><th>hit10</th><th>lift10</th></tr></thead>
 <tbody>{COMBO_TBL}</tbody></table>
 {img(CHARTS['c1'])}
 <div class="callout g"><b>最优稳定组合（C7）：</b>基准三类 + 近涨停 + 逼近日高 + 短期动量 + 多头排列 + 龙头概念，训练期 <b>{pct(tr_best)}</b>、样本外 <b>{pct(oo_best)}</b>（仅差约 2 pct，跨期稳定），样本量训练 3,037 / 样本外 1,674。这是本次研究推荐的落地组合。</div>
 <div class="callout r"><b>过拟合的活证据：</b>当把市场暖、小单流出等因子也全部堆上（L6 全叠加），命中率不升反降——样本外从 31% 掉到 <b>25.3%</b>，样本数也从 4,592 萎缩到 154。因子不是越多越好，堆叠加会同时损失统计效力与样本外泛化。</div>
 {img(CHARTS['c6'])}
</div>

<div class="sec">
 <h2><span class="no">06</span>单因子稳健性：谁真有效，谁不稳定</h2>
 <p>横轴训练期提升、纵轴样本外提升；落在第一象限（双正）且绿点=稳健有效。第三象限或跨象限（红点）=样本内外反向，不可信。</p>
 {img(CHARTS['c2'])}
 <table><thead><tr><th>因子</th><th>训练期Δ10</th><th>p值</th><th>样本外Δ10</th><th>p值</th><th>判定</th></tr></thead>
 <tbody>{ROB_TBL}</tbody></table>
 <div class="callout"><b>不稳定因子解读：</b>"滞后赚钱效应高"训练期 +0.64 pct（p=0.014）但样本外 −2.94 pct（p&lt;0.001）——高赚钱效应往往出现在行情尾声，追高反而受伤，符合"涨跌平衡"约束；"短期趋势向上"训练期几乎无作用、样本外才 +1.36 pct，属市场阶段依赖，非稳定因子。</div>
</div>

<div class="sec">
 <h2><span class="no o">07</span>概念专题：不能只看当天在不在强榜</h2>
 <p>用户特别指出：主线概念可能因涨太猛而跌出强概念榜，但主线未结束仍对概率有帮助。据此拆成两个口径对照。</p>
 <table><thead><tr><th>概念口径</th><th>训练样本</th><th>训练 hit5</th><th>训练 hit10</th><th>样本外样本</th><th>样本外 hit5</th><th>样本外 hit10</th></tr></thead>
 <tbody>{CONC_TBL}</tbody></table>
 {img(CHARTS['c3'])}
 <div class="callout g"><b>结论一（支持用户判断）：</b>在基准池进攻池上，"主线延续（历史强≥2）"命中率训练期 {pct(CA['concept_branch']['train']['主线延续']['y10'])} vs "当日强榜" {pct(CA['concept_branch']['train']['当日强榜']['y10'])}；样本外 {pct(CA['concept_branch']['oos']['主线延续']['y10'])} vs {pct(CA['concept_branch']['oos']['当日强榜']['y10'])}。按"主线是否延续"比只看当日榜单<b>两期都更高</b>——榜单进出不是概念强度的唯一口径。全样本单因子检验中，主线延续样本外提升 +2.04 pct（p&lt;0.001），稳健有效。</div>
 <div class="callout r"><b>结论二（数据事实，如实披露）：</b>"退出榜但主线未结束"极少见——历史强概念中当日仍在强榜的比例高达 <b>{stay:.2f}%</b>，每日强概念约 {avg_strong:.0f} 个且高度持续，退出榜候选仅 4,783 行（占 0.29%）。严格定义下样本外进攻池只有 1 个样本，宽松定义也只有个位数到百位。多档定义检验下符号不稳定（详见下表），<b>无法作为独立可交易因子</b>，只能作为概念延续性的边缘补充。</div>
 <table><thead><tr><th>样本组</th><th>池样本</th><th>池 hit10</th><th>严格定义样本</th><th>严格 hit10</th><th>宽松定义样本</th><th>宽松 hit10</th></tr></thead>
 <tbody>{OFF_TBL}</tbody></table>
</div>

<div class="sec">
 <h2><span class="no">08</span>1–2 日滞后：放宽观察窗口确实提高概率</h2>
 <p>用户指出好股不一定当天进攻、可能推迟 1–2 日。处理方法：保留"条件触发日"归集样本，把观察窗口从 5 日放宽到 7 日、从 10 日放宽到 12 日，比较命中率变化。</p>
 {img(CHARTS['c4'])}
 <table><thead><tr><th>样本期</th><th>样本数</th><th>hit5</th><th>hit7（+2日）</th><th>5→7提升</th><th>hit10</th><th>hit12（+2日）</th><th>10→12提升</th></tr></thead>
 <tbody>{LAG_TBL}</tbody></table>
 <div class="callout g"><b>结论：</b>放宽 2 日窗口后命中率稳定上升——5→7 日训练期 +3.48 pct、样本外 +4.60 pct；10→12 日训练期 +2.03 pct、样本外 +2.98 pct。这印证了滞后假设：<b>只看"今日"确实会漏掉近几日满足条件、稍后才进攻的标的</b>。代价是"最大涨幅"在更长窗口内更容易出现（时间越长越容易触及 20%），因此 5/7 日与 10/12 日口径应分开解读，不能混为一谈。</div>
</div>

<div class="sec">
 <h2><span class="no o">09</span>真实筹码集中度增量（仅样本外 2026-04+）</h2>
 <p>双轨制的轨道 B：在 2026-04 之后有真实 scrplus 值的样本上，检验高筹码集中度（≥中位 25.8）相对低集中度的增量。</p>
 {img(CHARTS['c5'])}
 <table><thead><tr><th>组合层</th><th>全样本数</th><th>hit10</th><th>高集中度样本</th><th>hit10</th><th>提升</th><th>p值</th></tr></thead>
 <tbody>{SCR_TBL}</tbody></table>
 <div class="callout"><b>结论：</b>真实筹码集中度有<b>正向但有限</b>的增量——基准池 +1.86 pct（p&lt;0.001）、近涨停池 +1.86 pct（p=0.029）显著；但在双叠加深池 +2.42 pct 却不显著（p=0.11，样本仅 1,439）。方向上支持"筹码集中→更易大涨"，但幅度远小于近涨停/逼近日高等技术信号，且受可得时间窗口短的限制，不能过度解读。</div>
</div>

<div class="sec">
 <h2><span class="no">10</span>为什么 75% 依旧不可达</h2>
 <p>本次最优组合训练期 {pct(tr_best)}、样本外 {pct(oo_best)}，与上一轮 TPE 搜索结论（最优约 41.8%、样本外 35.2%）方向一致。75% 的门槛对应的是"极高 base rate 的特殊交易日"（全市场仅 13 天 hit10≥75%，集中在 2024-02 与 2024-09 两个极端窗口），且这些日子事后才知道、当日不可预知。在不使用任何前视信息的纯当日可知因子条件下，把任意标的池推到 75% 缺乏数据支撑。<b>这是目标上界问题，不是算法或因子数量问题。</b></p>
</div>

<div class="sec">
 <h2><span class="no o">11</span>理论约束的逐条对应</h2>
 <table><thead><tr><th>理论</th><th>数据发现</th><th>解释</th></tr></thead><tbody>
 <tr><td class='l'>有量才有价（主力参与）</td><td class='l'>资金力度高分位 +1.9/+1.4pct、量能放大 +2.4/+1.8pct、小单流出 +1.0/+0.6pct 均稳健</td><td class='l'>主力净流入占比高、市场放量、散户小单流出，共同印证"有资金才有行情"</td></tr>
 <tr><td class='l'>资金聚集（概念/情绪/赚钱效应）</td><td class='l'>龙头概念 +3.4/+3.1pct、主线延续 +1.4/+2.0pct、涨停情绪 +2.6/+1.2pct</td><td class='l'>龙头概念与主线延续比单纯当日榜单更有效，赚钱效应体现资金抱团</td></tr>
 <tr><td class='l'>不确定性与趋势（微观不确定、趋势向上）</td><td class='l'>多头排列 +2.1/+3.8pct、短期动量 +4.0/+3.5pct 双显著</td><td class='l'>个股短期不确定性高，但均线多头与动量代表趋势方向，顺势者胜</td></tr>
 <tr><td class='l'>指标滞后效应</td><td class='l'>近涨停 +10.5pct、近20日涨停最优在第2分位（龙头隐匿期）而非最高分位</td><td class='l'>信号先于涨幅、进攻滞后 1–2 日；放宽窗口提高概率直接印证滞后</td></tr>
 <tr><td class='l'>涨跌平衡</td><td class='l'>滞后赚钱效应样本外 −2.9pct；全叠加因子反而回落</td><td class='l'>追高赚钱效应尾声易回撤，涨多必跌；因子堆砌违背平衡</td></tr>
 <tr><td class='l'>收益大与风险大并存</td><td class='l'>高命中组合样本数从基准 85,595 萎缩到 3,037（叠加后），全叠加仅 154</td><td class='l'>筛选越严、命中越高，但覆盖度骤降、偶然性上升，高收益必然伴随可得性与稳定性代价</td></tr>
 </tbody></table>
</div>

<div class="sec">
 <h2><span class="no">12</span>结论与落地建议</h2>
 <ol>
  <li><b>推荐组合（C7）：</b>近20日涨停≥1 + 主力净额占比&gt;0 + vol20≥分位70 + 换手≥分位60 + 近涨停（距涨停≤3点）+ 逼近日高（≥20日高点95%）+ 短期动量（近5日涨幅≥分位80）+ 均线多头 + 龙头概念。训练期 35.0% / 样本外 33.0%，是稳健性与覆盖度的最佳平衡。</li>
  <li><b>优先因子：</b>近涨停、逼近日高、短期动量、多头排列、龙头概念——五个因子训练与样本外双显著，是最可靠的增量来源。</li>
  <li><b>慎用因子：</b>市场滞后赚钱效应（样本外反向）、全因子堆叠加（过拟合）、退出榜主线未结束（样本极稀少）。</li>
  <li><b>滞后处理：</b>实盘应以"条件触发日"归集并放宽 2 日观察窗口，5/7 日与 10/12 日口径分开跟踪，避免只看当日漏掉稍后进攻的标的。</li>
  <li><b>概念口径：</b>用"主线是否延续"替代"当日是否在榜"，可稳定提升约 1–2 pct 命中率。</li>
  <li><b>目标校准：</b>75% 不可达；建议把落地目标设为"命中率 30–35% 且跨期稳定、单日样本数≥20"，更符合数据现实。</li>
 </ol>
</div>

<div class="sec">
 <h2><span class="no">13</span>最佳条件 C7 随日期变化的表现</h2>
 <p class="lead">把推荐组合 C7 逐日回放，看它在不同日期、不同牛熊环境下的真实稳定性——而不是只看一个合并后的平均数。</p>
 <p>全区间 <b>{C7_OV['days']} 个交易日</b>共选出 <b>{C7_OV['total_picks']:,}</b> 只标的，合并命中率 <b>{C7_OV['pooled_hit10']*100:.2f}%</b>，逐日命中率均值 {C7_OV['mean_daily_hit10']*100:.2f}%、中位数 {C7_OV['median_daily_hit10']*100:.2f}%。其中单日命中率 ≥75% 的有 <b>{C7_OV['days_ge75']} 天</b>（{C7_OV['days_ge75']/C7_OV['days']*100:.1f}%），50–75% 有 {C7_OV['days_50_75']} 天，25–50% 有 {C7_OV['days_25_50']} 天，低于 25% 有 {C7_OV['days_lt25']} 天。日均选中 {C7_OV['mean_picks_per_day']} 只、中位数 {C7_OV['median_picks_per_day']:.0f} 只。</p>
 {img(CHARTS['c8'])}
 <table><thead><tr><th>样本期</th><th>交易日</th><th>选出数</th><th>合并hit10</th><th>逐日均值</th><th>≥75%天数</th><th>50–75%</th><th>25–50%</th><th>&lt;25%</th></tr></thead><tbody>
 <tr><td class='l'>训练期 2024-02~2025-12</td><td>{C7_SP['train']['days']}</td><td>{C7_SP['train']['total_picks']:,}</td><td class='hi'>{C7_SP['train']['pooled_hit10']*100:.2f}%</td><td>{C7_SP['train']['mean_daily_hit10']*100:.2f}%</td><td>{C7_SP['train']['days_ge75']}</td><td>{C7_SP['train']['days_50_75']}</td><td>{C7_SP['train']['days_25_50']}</td><td>{C7_SP['train']['days_lt25']}</td></tr>
 <tr><td class='l'>样本外 2026-01~2026-10</td><td>{C7_SP['oos']['days']}</td><td>{C7_SP['oos']['total_picks']:,}</td><td class='hi'>{C7_SP['oos']['pooled_hit10']*100:.2f}%</td><td>{C7_SP['oos']['mean_daily_hit10']*100:.2f}%</td><td>{C7_SP['oos']['days_ge75']}</td><td>{C7_SP['oos']['days_50_75']}</td><td>{C7_SP['oos']['days_25_50']}</td><td>{C7_SP['oos']['days_lt25']}</td></tr>
 </tbody></table>
 {img(CHARTS['c9'])}
 <h3>13.1 牛 / 熊 / 震荡市表现（对应"便于看牛熊表现"的诉求）</h3>
 <p>用市场近 20 日平均涨跌（mkt_ret_20d &gt;2 记为牛、&lt;−2 记为熊、其间为震荡）给交易日打环境标签。C7 在三种环境下命中率分别为：牛 <b>{C7_RG['牛']['pooled_hit10']*100:.2f}%</b>、熊 <b>{C7_RG['熊']['pooled_hit10']*100:.2f}%</b>、震荡 <b>{C7_RG['震荡']['pooled_hit10']*100:.2f}%</b>。牛市最高、震荡最低，但差距有限，且样本外整体低于训练期——说明 C7 的收益更多来自个股自身的质量信号，而非单纯依赖大盘方向，跨环境具备可用性。</p>
 {img(CHARTS['c10'])}
 <div class="callout"><b>怎么读这些数字：</b>合并命中率（约 34%）是"把所有日子的选股混在一起"的比例，是最稳健的口径；逐日均值（约 34%）与其接近，说明没有少数极端日主导。约 {C7_OV['days_ge75']/C7_OV['days']*100:.0f}% 的交易日能达到 ≥75%，但这些达标日集中在个别极端行情，<b>当日无法预知</b>，只能事后复盘，不可当作稳定承诺。样本外合并命中率 {C7_SP['oos']['pooled_hit10']*100:.2f}% 略低于训练期 {C7_SP['train']['pooled_hit10']*100:.2f}%，属正常衰减而非失效。</div>
</div>

<div class="sec">
 <h2><span class="no o">14</span>正面回答：两次报告概率接近，是不是说明本次提升不明显？</h2>
 <p class="lead">这是必须讲清楚的问题。结论先放这里：<b>数字接近是真的，但"提升不明显"这个推论不成立</b>——两次研究的基准、目标、筛选逻辑都不同，看似相近的数字背后是完全不同的东西。</p>
 <table><thead><tr><th>研究</th><th>推荐规则性质</th><th>训练期 hit10</th><th>样本外 hit10</th><th>训练期选中数</th><th>逐日≥75%天数</th><th>跨期稳定性</th></tr></thead><tbody>
 <tr><td class='l'>全市场基准（对照）</td><td class='l'>无筛选</td><td>11.50%</td><td>8.76%</td><td>全市场</td><td>10 / 463</td><td class='l'>—</td></tr>
 <tr><td class='l'>第一次 R1（窄规则冲比例）</td><td class='l'>极端分位阈值 q0.97，样本压到极小</td><td class='hi'>{FR1['merge_train']*100:.2f}%</td><td class='hi'>{FR1['merge_oos']*100:.2f}%</td><td>{FR1['pool_train']:,}</td><td>{FR1['hit_days_train']}</td><td class='l'>样本外掉 {abs(FR1['merge_train']-FR1['merge_oos'])*100:.1f}pct，逐日仅 2 天达标</td></tr>
 <tr><td class='l'>本次 C7（稳健可用组合）</td><td class='l'>适中阈值，保留覆盖度与泛化</td><td class='hi'>{C7_SP['train']['pooled_hit10']*100:.2f}%</td><td class='hi'>{C7_SP['oos']['pooled_hit10']*100:.2f}%</td><td>{C7_SP['train']['total_picks']:,}</td><td>{C7_SP['train']['days_ge75']}</td><td class='l'>样本外仅掉 {abs(C7_SP['train']['pooled_hit10']-C7_SP['oos']['pooled_hit10'])*100:.1f}pct，逐日 {C7_SP['train']['days_ge75']} 天达标</td></tr>
 </tbody></table>
 {img(CHARTS['c11'])}
 <div class="callout g"><b>三条硬数字，说明本次不是"没提升"：</b><br>
 ① <b>基准不同。</b>第一次报告拿的是"全市场基准 ~11.5%"，本次是在<b>已经抬高的三条件基准池 20.79%</b> 之上继续叠加。相对于同一个全市场基准，第一次 R1 是 41.83%÷11.5% ≈ <b>3.64×</b>，本次 C7 是 35.07%÷11.5% ≈ <b>3.05×</b>——都在 3 倍以上，量级一致。<br>
 ② <b>目标不同。</b>第一次 R1 是"用极端阈值把数字冲高"（q0.97 阈值、样本压到 4,851、逐日仅 2 天达标、样本外掉到 35.22%）；本次 C7 追求的是"覆盖度 + 跨期稳定"（样本 3,037/1,666，逐日 52/8 天达标，样本外只掉 2.1pct）。<b>数字略低换来的是可用性和稳定性，不是退步。</b><br>
 ③ <b>本次新增了第一次没有的认知。</b>证伪了"筹码集中度第 2 分位最优"这一数据伪影（训练期该字段全为 0），并首次量化了真实筹码集中度只有 +1.86~2.42pct 的有限增量、1–2 日滞后能 +3~5pct、主线延续优于当日榜单。这些是<b>方法论层面的净增益</b>，不体现在"最高命中率"这一个数字上。</div>
 <div class="callout r"><b>诚实地说，什么没有提升：</b>如果你的唯一评判标准是"把最高命中率从 41.83% 再往上推"，那本次确实没有做到——C7 训练期 35.07% 反而低于 R1 的 41.83%。原因是 R1 靠极端阈值牺牲覆盖度换数字，这条路已经走到头且不可实盘；本次选择不再冲这个虚高数字，而是把可用组合的跨期稳定性做扎实。<b>把这件事说清楚，比报一个漂亮但不可用的数字更重要。</b></div>
</div>

<div class="sec">
 <h2><span class="no">15</span>可操作落地：C7 选股筛选代码</h2>
 <p class="lead">给出可直接运行的筛选代码 <span class="tag">c7_stock_screen.py</span>，把研究结论变成生产力。</p>
 <h3>15.1 完整筛选条件（全部 T 日收盘后可知，零前视）</h3>
 <table><thead><tr><th>#</th><th>条件</th><th>阈值</th><th>经济含义</th></tr></thead><tbody>
 <tr><td>1</td><td class='l'>近 20 日涨停次数 lu_cnt_20d</td><td>≥ 1</td><td class='l'>情绪 / 主力参与</td></tr>
 <tr><td>2</td><td class='l'>主力净额占比 main_net_norm</td><td>&gt; 0</td><td class='l'>资金 / 筹码集中（轨道 A 代理）</td></tr>
 <tr><td>3</td><td class='l'>20 日波动率 vol20</td><td>≥ {C7_TH['vol20']}</td><td class='l'>高波动（train q70）</td></tr>
 <tr><td>4</td><td class='l'>当日换手率 turnover_rate</td><td>≥ {C7_TH['turnover_rate']}</td><td class='l'>活跃度（train q60）</td></tr>
 <tr><td>5</td><td class='l'>涨停缺口 lu_gap</td><td>≥ {C7_TH['lu_gap']}</td><td class='l'>逼近日高 / 强势</td></tr>
 <tr><td>6</td><td class='l'>收盘/20日高点 close_hh20_ratio</td><td>≥ {C7_TH['close_hh20_ratio']}</td><td class='l'>趋势向上</td></tr>
 <tr><td>7</td><td class='l'>近 5 日涨幅 ret_5d</td><td>≥ {C7_TH['ret_5d']}%</td><td class='l'>短期动量（train q80）</td></tr>
 <tr><td>8</td><td class='l'>均线多头 ma5&gt;ma20&gt;ma60</td><td>成立</td><td class='l'>趋势确认</td></tr>
 <tr><td>9</td><td class='l'>龙头概念数 n_leader_concepts</td><td>≥ 1</td><td class='l'>资金抱团 / 概念聚集</td></tr>
 </tbody></table>
 <h3>15.2 运行方式</h3>
 <p><span class="tag">python c7_stock_screen.py --date 2026-10-30</span>（读已验证特征矩阵，最快）<br>
 <span class="tag">python c7_stock_screen.py --date 2026-10-30 --live</span>（从项目原始 parquet 实时重算，可脱离中间文件部署）<br>
 <span class="tag">python c7_stock_screen.py --verify 2024-09-27 2025-02-10 2026-10-30</span>（双模式一致性核验）</p>
 <h3>15.3 真实日期验证结果</h3>
 <p>双模式在三个日期（2024-09-27、2025-02-10、2026-10-30）选出的股票代码<b>完全一致</b>（ALL_OK）。以 2026-10-30 为例，筛出 2 只：<b>阳光照明(600261)</b>——近20日 3 次涨停、主力净额占比 0.60、近5日涨 18.55%、均线多头、命中 1 个龙头概念；<b>大业股份(603278)</b>——近20日 7 次涨停、换手 66.3、近5日涨 22.31%、命中 1 个龙头概念。两模式逐字段一致，证明代码口径与研究报告完全对齐。</p>
 <div class="callout"><b>重要口径声明：</b>代码严格遵守"涨跌幅用 daily_pct（前复权自算）、禁用 quote 原始 pct_change"的项目硬口径。核验中曾发现 live 模式误用 quote 原始 pct_change 导致 2024-09-27 选股为 0，已定位（除权日口径不一致）并修正，复验后双模式完全一致——这正是"事实驱动、不许甩锅"的闭环。脚本全程只读项目数据，不写入任何项目文件。</div>
</div>

<div class="foot">
 <p><b>数据与合规声明：</b>本报告全部结论基于 stockDisplay 项目只读数据（快照 2024-02-01~2026-11-10），分析脚本运行于独立工作目录，未修改任何项目数据文件、未改动项目代码。所有筛选因子经前视审查，仅用 T 日可知数据；fwd_* 与 mkt_hit* 等未来数据仅用于标签与复盘，不参与筛选。训练期 = 2024-02~2025-12（463 交易日），样本外 = 2026-01~2026-10（199 交易日），阈值只由训练期确定。</p>
 <p><b>口径提示：</b>hit5/hit10 = 未来对应窗口内最高价相对触发日收盘涨幅&gt;20% 的样本占比；放宽窗口 hit7/hit12 因观察期更长，天然更易触及阈值，须与 hit5/hit10 分开解读。筹码集中度真实值仅 2026-04+ 可得，相关结论仅适用于该短窗口。</p>
 <p style="margin-top:12px;color:#b0b8c0">选股因子增量归因研究报告 · 量化研究专题 · 生成于 2026-11-19</p>
</div>

</div></body></html>"""

out=WS/"选股因子增量归因研究报告.html"
out.write_text(HTML,encoding="utf-8")
print("WROTE",out,out.stat().st_size,"bytes",flush=True)
print("CHARTS",len(CHARTS),"TABLES=10",flush=True)
