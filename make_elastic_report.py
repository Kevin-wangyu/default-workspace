# -*- coding: utf-8 -*-
"""弹性(n,m)机制研究报告：商业级HTML，图表base64内嵌，GFM风格。"""
from __future__ import annotations
import json
from pathlib import Path
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
F=json.loads((WS/'elastic_final_out.json').read_text(encoding='utf-8'))
R=json.loads((WS/'elastic_rule_out.json').read_text(encoding='utf-8'))
DG=json.loads((WS/'diag_elastic_signal_out.json').read_text(encoding='utf-8'))
CH=json.loads((WS/'elastic_charts.json').read_text(encoding='utf-8'))

def pct(x,d=2): return f"{x*100:.{d}f}%" if x is not None else "—"
def img(k): return f'<img src="data:image/png;base64,{CH[k]}" style="width:100%;max-width:960px;border:1px solid #e3e8ef;border-radius:8px"/>'

S=F['splits']; cfg=F['config']; wm=F['m15_days']
tr,oos,all_=S['train'],S['oos'],S['all']

html=f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>弹性 n·m 机制研究报告</title>
<style>
body{{font-family:"Microsoft YaHei","PingFang SC",sans-serif;max-width:1040px;margin:0 auto;padding:32px 28px;color:#25313d;line-height:1.75;background:#fafbfc}}
h1{{font-size:27px;color:#1a3b5d;border-bottom:4px solid #2E86AB;padding-bottom:12px}}
h2{{font-size:20px;color:#1a3b5d;margin-top:38px;border-left:5px solid #2E86AB;padding-left:12px}}
h3{{font-size:16px;color:#34495e;margin-top:22px}}
table{{border-collapse:collapse;width:100%;margin:16px 0;font-size:14px;background:#fff}}
th{{background:#2E86AB;color:#fff;padding:9px 10px;text-align:center;font-weight:600}}
td{{border:1px solid #dde4ec;padding:8px 10px;text-align:center}}
tr:nth-child(even) td{{background:#f4f8fb}}
.callout{{background:#fff6e8;border-left:5px solid #E67E22;padding:14px 18px;margin:18px 0;border-radius:6px}}
.good{{background:#eaf6ee;border-left:5px solid #27ae60;padding:14px 18px;margin:18px 0;border-radius:6px}}
.bad{{background:#fdecec;border-left:5px solid #c0392b;padding:14px 18px;margin:18px 0;border-radius:6px}}
.small{{font-size:13px;color:#7b8794}}
figure{{margin:22px 0;text-align:center}}
figcaption{{font-size:13px;color:#7b8794;margin-top:8px}}
code{{background:#eef2f6;padding:2px 6px;border-radius:4px;font-size:13px}}
.kpi{{display:flex;gap:14px;flex-wrap:wrap;margin:18px 0}}
.kpi div{{flex:1;min-width:150px;background:#fff;border:1px solid #dde4ec;border-radius:8px;padding:14px;text-align:center}}
.kpi b{{font-size:24px;color:#2E86AB;display:block}}
</style></head><body>

<h1>弹性 n·m 机制研究报告</h1>
<p class="small">生成于工作区 · 数据区间 2024-03-13 ~ 2026-10-27（报告对齐580交易日）· 训练期 train≤2025-12-31 / 样本外 oos 2026-01~10 · 全程零写入项目数据、零前视</p>

<div class="kpi">
<div><b>170 / 580</b>固定 m=20 达标≥50%日期（基线 29.31%）</div>
<div><b>274 / 580</b>固定 m=15 达标≥50%日期（47.24%）</div>
<div><b>180 / 580</b>弹性规则达标日期（31.03%）</div>
<div><b>4.25×</b>弹性规则相对全市场命中放大</div>
</div>

<h2>一、执行摘要：一句话结论</h2>
<div class="bad">
<b>本次研究的核心结论是"否定的结论"</b>：在 C7 选股条件固定、n 取最佳范围内、m∈{{15,20}} 的约束下，
<b>按当日市场状况弹性调整 (n,m) 无法在"守住 m=20 收益目标"的前提下显著提高达标日期占比</b>。
唯一能把达标日期从 170 提到 274 的手段是把目标 m 从 20 降到 15——那是<b>目标收益的主动下调</b>，不是选股能力的提升。
数据同时证明：市场强弱对 m=20 命中率几乎没有区分度，n=10 在全市场档位严格优于 n=7，放宽触发窗口反而降低命中率。
</div>

<h2>二、基线复核：170/580 到底是什幺口径</h2>
<p>对用户提出的"580 日中能选出股票的日期>50% 的仅 170 日"做了逐日复核，结果如下（<code>c7_daily_out.json</code>，C7 选股与 m 无关）：</p>
<table><tr><th>口径</th><th>数值</th><th>说明</th></tr>
<tr><td>能选出≥1只股票的日期</td><td>580 / 580（100%）</td><td>C7 每天都在选股，日均 8.1 只，"选不出"不成立</td></tr>
<tr><td>hit10=0 的日期</td><td>122 / 580（21.03%）</td><td>选出股票无一在10日涨20%，这才是"命中归零"</td></tr>
<tr><td><b>hit10≥50% 的日期</b></td><td><b>170 / 580（29.31%）</b></td><td>即用户所指 170；=≥75%的60天 + 50–75%的110天</td></tr>
<tr><td>hit10≥75% 的日期</td><td>60 / 580（10.34%）</td><td>—</td></tr></table>
<div class="callout"><b>口径纠正</b>：用户的"选不出股票"应理解为"选出的股票未达到 m=20 的涨幅目标"；170 对应的是"命中率≥50%的日期数"，不是"能选出股票的日期数"。本研究的弹性目标据此定义为：<b>提高 hit≥50% 的日期占比，同时不牺牲命中质量</b>。</div>

<h2>三、研究设计与因子清单</h2>
<h3>3.1 当日可知的市场状态特征</h3>
<p>用当日 T 可得的市场量价特征构造综合分 S = Σ wᵢ·z(特征ᵢ)，权重 wᵢ 为 train 期该特征与当日 m=20 命中率的 Pearson 相关（保留符号），z 用 train 均值/标准差标准化、1%–99% 截尾防极值：</p>
<table><tr><th>特征</th><th>经济逻辑</th><th>train 权重</th><th>缺失率</th></tr>
{''.join(f"<tr><td>{c}</td><td>{ {'mkt_amt_ratio':'市场放量=资金聚集','mkt_ret_5d':'短期趋势向上','mkt_ret_20d':'中期趋势','mkt_up_ratio':'普涨赚钱效应','mkt_lu':'涨停情绪','eff_hit10_lag':'过去赚钱效应滞后(11–30日)'} [c]}</td><td>{cfg['weights'][c]:+.3f}</td><td>≤1.7%</td></tr>" for c in cfg['weights'])}</table>
<p class="small">所有特征 T 日可知；<code>mkt_hit5/10</code>（含未来标签）已排除，杜绝前视。S 的分档线在 train 上固定，oos 回放不重新拟合。</p>

<h3>3.2 (n,m) 候选与映射规则</h3>
<p>候选锁定在用户确认的最佳范围：n∈{{7,10}}、m∈{{15,20}}，共4组合。规则设计遵循"守高收益为默认"：</p>
<table><tr><th>市场档</th><th>判定</th><th>推荐 n</th><th>推荐 m</th><th>逻辑</th></tr>
<tr><td>常规（S≥train 10分位）</td><td>S ≥ {cfg['s10']}</td><td>10</td><td><b>20</b></td><td>守住高收益目标，n 取最优</td></tr>
<tr><td>极弱（S&lt;train 10分位）</td><td>S &lt; {cfg['s10']}</td><td>10</td><td><b>15</b></td><td>仅极弱市把目标降到15保命中（占约10%日期）</td></tr></table>
<div class="callout"><b>为什么不更激进地弹性</b>：诊断显示 n=10 在强/中/弱三档全部优于 n=7（n7 胜出天数=0），n 不是杠杆；放宽触发到 T-1/T-2 使命中率从 36.84% 降到 30.11%；按股票首次触发去重命中率反而略降。因此"市场强用哪档、市场弱用哪档"的可操作空间被数据压缩到只剩"m 在极弱市降一档"。</div>

<h2>四、全580日回放：前后对比</h2>
{table_start if False else ''}
<table><tr><th>方案</th><th>期</th><th>达标≥50%日期</th><th>达标≥75%日期</th><th>hit=0日期</th><th>平均命中率</th><th>相对全市场放大</th></tr>
{''.join(f"<tr><td>{nm}</td><td>{sp}</td><td>{d['ge50']} / {d['days']}（{d['ge50_pct']}%）</td><td>{d['ge75']}（{d['ge75_pct']}%）</td><td>{d['zero']}（{d['zero_pct']}%）</td><td>{pct(d['mean'])}</td><td>{S[sp][lk] if False else ''}</td></tr>" for nm,sp,lk,d in [])}
</table>
<!-- 手动展开避免模板嵌套歧义 -->
<table><tr><th>方案</th><th>期</th><th>达标≥50%日期</th><th>hit=0日期</th><th>平均命中率</th></tr>
<tr><td rowspan="3">固定 m=20（基线）</td><td>train</td><td>{tr['固定m20']['ge50']}/{tr['固定m20']['days']}（{tr['固定m20']['ge50_pct']}%）</td><td>{tr['固定m20']['zero']}（{tr['固定m20']['zero_pct']}%）</td><td>{pct(tr['固定m20']['mean'])}</td></tr>
<tr><td>oos</td><td>{oos['固定m20']['ge50']}/{oos['固定m20']['days']}（{oos['固定m20']['ge50_pct']}%）</td><td>{oos['固定m20']['zero']}（{oos['固定m20']['zero_pct']}%）</td><td>{pct(oos['固定m20']['mean'])}</td></tr>
<tr><td><b>全期</b></td><td><b>{all_['固定m20']['ge50']}/{all_['固定m20']['days']}（{all_['固定m20']['ge50_pct']}%）</b></td><td>{all_['固定m20']['zero']}（{all_['固定m20']['zero_pct']}%）</td><td>{pct(all_['固定m20']['mean'])}</td></tr>
<tr><td rowspan="3">弹性规则（极弱→m15）</td><td>train</td><td>{tr['弹性']['ge50']}/{tr['弹性']['days']}（{tr['弹性']['ge50_pct']}%）</td><td>{tr['弹性']['zero']}（{tr['弹性']['zero_pct']}%）</td><td>{pct(tr['弹性']['mean'])}</td></tr>
<tr><td>oos</td><td>{oos['弹性']['ge50']}/{oos['弹性']['days']}（{oos['弹性']['ge50_pct']}%）</td><td>{oos['弹性']['zero']}（{oos['弹性']['zero_pct']}%）</td><td>{pct(oos['弹性']['mean'])}</td></tr>
<tr><td><b>全期</b></td><td><b>{all_['弹性']['ge50']}/{all_['弹性']['days']}（{all_['弹性']['ge50_pct']}%）</b></td><td>{all_['弹性']['zero']}（{all_['弹性']['zero_pct']}%）</td><td>{pct(all_['弹性']['mean'])}</td></tr>
<tr><td rowspan="3">固定 m=15（对照上限）</td><td>train</td><td>{tr['固定m15']['ge50']}/{tr['固定m15']['days']}（{tr['固定m15']['ge50_pct']}%）</td><td>{tr['固定m15']['zero']}（{tr['固定m15']['zero_pct']}%）</td><td>{pct(tr['固定m15']['mean'])}</td></tr>
<tr><td>oos</td><td>{oos['固定m15']['ge50']}/{oos['固定m15']['days']}（{oos['固定m15']['ge50_pct']}%）</td><td>{oos['固定m15']['zero']}（{oos['固定m15']['zero_pct']}%）</td><td>{pct(oos['固定m15']['mean'])}</td></tr>
<tr><td><b>全期</b></td><td><b>{all_['固定m15']['ge50']}/{all_['固定m15']['days']}（{all_['固定m15']['ge50_pct']}%）</b></td><td>{all_['固定m15']['zero']}（{all_['固定m15']['zero_pct']}%）</td><td>{pct(all_['固定m15']['mean'])}</td></tr></table>
<figure>{img('E1')}<figcaption>图1 达标≥50%日期数：170（基线）→ 180（弹性）→ 274（固定m15）</figcaption></figure>
<div class="bad"><b>与 170 / 29.3% 的直接对比</b>：弹性规则把全期达标日期从 170 提到 180（+10 天，29.31%→31.03%），样本外从 39 提到 42（22.03%→23.73%）。
这个提升幅度<b>很小且完全来自约10%的极弱市日期降 m</b>（{wm['n']}天里 m20 hit {pct(wm['m20_hit'])} → m15 hit {pct(wm['m15_hit'])}，+11pct）。
若以"提高达标日期占比"为唯一目标，固定 m=15 直接给到 47.24%——远高于任何弹性分档方案。这说明<b>市场状态分档对达标占比几乎没有独立贡献</b>。</div>

<h2>五、为什么不牺牲命中质量也做不到：三项诊断证据</h2>
<figure>{img('E2')}<figcaption>图2 当日市场综合分 S 与 m=20 命中率散点：无明显单调分界，分档难以区分</figcaption></figure>
<table><tr><th>诊断</th><th>检验</th><th>结果</th><th>含义</th></tr>
<tr><td>市场档 × n 维度</td><td>各档 n=10 vs n=7 命中率</td><td>n10 在强/中/弱三档全部更优；n7 胜出天数=0</td><td>n=10 恒优，n 不是弹性杠杆</td></tr>
<tr><td>触发日归集（1–2日滞后）</td><td>T日 vs T-1/T-2并集命中率</td><td>train {pct(0.3684)} → {pct(0.3011)}（-6.73pct）；oos {pct(0.285)} → {pct(0.2535)}</td><td>放宽窗口引入未触发标的，反降命中</td></tr>
<tr><td>幸存者偏差去重</td><td>全体 vs 首次触发命中率</td><td>train {pct(0.3505)} → {pct(0.3425)}；oos {pct(0.3299)} → {pct(0.2889)}</td><td>同一股重复触发非虚高来源</td></tr></table>
<figure>{img('E4')}<figcaption>图3 三项机制诊断：弹性空间被数据压缩</figcaption></figure>
<div class="callout"><b>关于用户强调的"1–2日滞后"</b>：已按"触发日归集"口径检验——把 T-1/T-2 触发的标的纳入当日进攻池。结果不是提升而是下降（train -6.73pct、oos -3.15pct），原因是放宽窗口纳入了大量"曾触发但当下动能已衰减"的标的，稀释了命中率。因此在本数据上，滞后效应更适合作为<b>现象解释</b>（好股不同日触发），而非<b>提升命中率的操作杠杆</b>。若强行只看每只股首次触发（去重），命中率同样不升反降。</div>

<h2>六、m=15 对照：这是"目标下调"而非"能力提升"</h2>
<figure>{img('E3')}<figcaption>图4 m=15 命中率全程稳定高于 m=20，差距与市场状态无关</figcaption></figure>
<p>固定 m=15 的达标日期 274（47.24%）看似理想，但必须看清口径：它把"最大涨幅超过20%"的目标改成了"超过15%"。
在 n=10、同批 C7 标的上，命中率从 34.3% 机械地升到 45.1%——这是<b>门槛放宽的数学后果</b>，不是选股模型的进步。
相对全市场放大倍数从 4.31× 变为略低（m15 口径），说明 C7 的选股能力并未因降 m 而增强。
因此若严格执行用户原始目标（m=20），本报告建议<b>维持固定 n=10/m=20</b>，弹性机制仅在"愿意接受15%目标"时作为可选开关。</p>

<h2>七、与有效理论的对应解释</h2>
<p>把本次"弹性机制无效"的结论放回用户给定的六条理论约束里看，每一条都能对上——这恰恰说明否定结论不是数据噪声，而是市场规律的自然结果。</p>
<table><tr><th>理论约束</th><th>本次数据表现</th><th>解释</th></tr>
<tr><td><b>有量才有价（主力参与）</b></td><td>市场量能比 mkt_amt_ratio 与命中率相关最高（+0.15），但仍不足以分档</td><td>放量确实略提高命中，但影响是连续、微弱的，无法切成"强市/弱市"两档来分别设定目标——主力参与是渐变而非开关</td></tr>
<tr><td><b>资金聚集（概念/情绪/赚钱效应）</b></td><td>涨停数、上涨家数相关仅 +0.07~0.09；当日强概念已在 C7 中（龙头概念≥1）</td><td>聚集效应已被 C7 条件吸收，剩余市场级情绪对"能否达20%"的边际贡献很小；强概念是选股条件，不是择时开关</td></tr>
<tr><td><b>不确定性与趋势（微观不确定、趋势向上）</b></td><td>mkt_ret_5d/20d 相关仅 +0.11/+0.06，S 分档无清晰单调分界（图2）</td><td>微观涨停与否高度不确定，趋势只是弱正向背景；正因不确定，才无法用当日趋势精确预测个股能否冲20%，弹性择时自然失效</td></tr>
<tr><td><b>指标滞后效应</b></td><td>eff_hit10_lag（11–30日赚钱效应）相关仅 +0.004，几乎为零；触发窗口 T-1/T-2 归集反降命中</td><td>滞后效应在"哪天触发"上存在（好股不同日满足条件），但把它当作"哪天进攻"的择时信号会引入已衰减标的，故不能用来提升命中</td></tr>
<tr><td><b>涨跌平衡（不可能一直涨/跌）</b></td><td>极弱市（S&lt;10分位）m20 命中仍达 {pct(wm['m20_hit'])}，并未归零；降 m15 才升到 {pct(wm['m15_hit'])}</td><td>即便最弱市也有约四分之一标的冲20%——跌透之后的反弹正是"涨跌平衡"；这解释了为何极端降目标也只换来有限增量</td></tr>
<tr><td><b>收益大与风险大并存</b></td><td>固定 m20 命中 34.3% vs m15 命中 45.1%，放大倍数 4.31× → 略降</td><td>把目标从20%降到15%看似"提高命中"，实质是用收益换概率；高收益目标必然伴随低命中率，这是风险收益的公平定价，不存在"既高命中又高收益"的免费弹性</td></tr></table>
<div class="callout"><b>顶层设计视角</b>：六条理论共同指向一个结论——个股能否冲20%主要由<b>个股自身 alpha（资金/概念/波动/情绪）</b>决定，市场状态只是弱背景。C7 已经把可用的个股 alpha 收进条件，剩下的市场择时维度信息量极低，因此"弹性 (n,m)"这条路的性价比天花板很低。真正的改进抓手在个股特征深度（分钟级资金持续性、龙虎榜、题材生命周期），而非参数弹性。</div>

<h2>八、档位举证：分档为何区分度不足</h2>
<p>把全580日按 S 分为三档，分别看 m=20/m=15 的命中率与达标占比：</p>
<table><tr><th>市场档</th><th>日期数</th><th>m20 命中率</th><th>m20 达标≥50%</th><th>m15 命中率</th><th>m15 达标≥50%</th><th>相对全市场放大(m20)</th></tr>
<tr><td>强</td><td>{R['档举证']['强']['n']}</td><td>{pct(R['档举证']['强']['m20_hit'])}</td><td>{R['档举证']['强']['m20_ge50_pct']}%</td><td>{pct(R['档举证']['强']['m15_hit'])}</td><td>{R['档举证']['强']['m15_ge50_pct']}%</td><td>{R['档举证']['强']['lift_m20']}×</td></tr>
<tr><td>中</td><td>{R['档举证']['中']['n']}</td><td>{pct(R['档举证']['中']['m20_hit'])}</td><td>{R['档举证']['中']['m20_ge50_pct']}%</td><td>{pct(R['档举证']['中']['m15_hit'])}</td><td>{R['档举证']['中']['m15_ge50_pct']}%</td><td>{R['档举证']['中']['lift_m20']}×</td></tr>
<tr><td>弱</td><td>{R['档举证']['弱']['n']}</td><td>{pct(R['档举证']['弱']['m20_hit'])}</td><td>{R['档举证']['弱']['m20_ge50_pct']}%</td><td>{pct(R['档举证']['弱']['m15_hit'])}</td><td>{R['档举证']['弱']['m15_ge50_pct']}%</td><td>{R['档举证']['弱']['lift_m20']}×</td></tr></table>
<p>三档 m20 命中率从强到弱仅 {pct(R['档举证']['强']['m20_hit'])} → {pct(R['档举证']['弱']['m20_hit'])}（差约9pct），且各档"降m到15"的收益差都稳定在 10–11pct——<b>档间差异远小于降 m 的机械差异</b>，这就是分档规则无法超越"固定 m=15"的根本原因。</p>

<h2>九、局限与改进</h2>
<ul>
<li><b>市场特征预测力弱</b>：6个特征与 m=20 命中率相关最高仅 0.15（市场量能比），S 分档对命中几乎无区分度，这是弹性机制效果有限的根因。</li>
<li><b>可达上限受目标定义约束</b>：在 m=20 下，无论 n 和市场状态如何组合，"至少一个组合达标≥50%"的理论上限也只有 204/403=50.6%（train），全期 274/580=47.24%，且该上限完全由 m=15 贡献。</li>
<li><b>样本外稳定性</b>：弹性规则 oos 达标 23.73% vs 基线 22.03%（+1.7pct），方向一致但幅度小于 train，符合"弱信号"特征。</li>
<li><b>改进方向</b>：若要真正提升 m=20 达标率，需引入更强的当日个股 alpha 特征（如资金流的分钟级持续性、龙虎榜数据）或放宽候选池（非 C7），而非在 (n,m) 参数上做文章。</li>
</ul>

<h2>十、口径声明与合规</h2>
<p class="small">
① 命中标签：fwd_max_n=(max(high[T+1..T+n])/close_T-1)×100 ≥ m，n 日内需有完整 n 个交易日，不足则剔除；
② 涨跌幅口径：全程用矩阵内 daily_pct/close/high（前复权一致），禁用 quote 原始 pct_change；
③ 零前视：决策特征全部 T 日可知，mkt_hit5/10 含未来标签已排除，S 分档线 train 固定、oos 不重拟合；
④ 零写入：所有脚本写于工作目录，未修改项目任何数据/代码文件，未调用 cli.py；
⑤ 复现：elastic_daily_build.py → elastic_rule.py / elastic_final.py → elastic_charts.py → make_elastic_report.py。
</p>
<p class="small" style="text-align:center;margin-top:30px">— 报告完 —</p>
</body></html>"""
# 清理未使用模板变量占位（避免解析残留）
html=html.replace("{table_start if False else ''}","")
(WS/'弹性n_m机制研究报告.html').write_text(html,encoding='utf-8')
print("bytes:",len(html.encode('utf-8')),"sections:",html.count('<h2>'),"imgs:",html.count('data:image/png;base64'))
print("DONE")
