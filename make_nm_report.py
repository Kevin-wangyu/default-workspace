# -*- coding: utf-8 -*-
"""生成 n×m 参数研究商业级 HTML 报告。纯读工作目录 JSON，输出报告到工作目录。"""
from __future__ import annotations
import json
from pathlib import Path
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
def load(n): return json.loads((WS/n).read_text(encoding="utf-8"))
D=load("nm_analysis_out.json"); E=load("nm_enrich_out.json"); CH=load("nm_charts.json")
res=D['grid']; NS=D['config']['NS']; MS=D['config']['MS']
eff={(e['split'],e['n'],e['m']):e for e in E['eff']}

def pct(v,d=2): return '—' if v is None else f"{v*100:.{d}f}%"

# ---- 表1 命中率总表 ----
hit_rows=[]
for m in MS:
    cells=''.join(f"<td>{pct(res[f'train|{n}|{m}']['c7_hit_rate'],1)}</td>" for n in NS)
    cells+='<td class="sep">'+''.join(f"<td>{pct(res[f'oos|{n}|{m}']['c7_hit_rate'],1)}</td>" for n in NS)+'</td>'
    hit_rows.append(f"<tr><td class='l'><b>m={m}%</b></td>{cells}</tr>")
HIT_TBL="\n".join(hit_rows)

# ---- 表2 捕获率总表 ----
cap_rows=[]
for m in MS:
    cells=''.join(f"<td>{pct(res[f'train|{n}|{m}']['capture'],2)}</td>" for n in NS)
    cells+='<td class="sep">'+''.join(f"<td>{pct(res[f'oos|{n}|{m}']['capture'],2)}</td>" for n in NS)+'</td>'
    cap_rows.append(f"<tr><td class='l'><b>m={m}%</b></td>{cells}</tr>")
CAP_TBL="\n".join(cap_rows)

# ---- 表3 性价比（m=20 各 n 的 hit / gain per day / 捕获率 / 放大） ----
perf_rows=[]
for n in NS:
    tr=eff[('train',n,20)]; oo=eff[('oos',n,20)]
    rtr=res[f'train|{n}|20']; roo=res[f'oos|{n}|20']
    perf_rows.append(f"""<tr><td class='l'><b>n={n}</b></td>
      <td>{pct(tr['hit'],1)}</td><td>{tr['gain_day']:.3f}%</td><td>{pct(rtr['capture'],2)}</td><td>{rtr['amplification']:.2f}×</td>
      <td class="sep">{pct(oo['hit'],1)}</td><td>{oo['gain_day']:.3f}%</td><td>{pct(roo['capture'],2)}</td><td>{roo['amplification']:.2f}×</td></tr>""")
PERF_TBL="\n".join(perf_rows)

# ---- 表4 m 选择（n=10 各 m） ----
m_rows=[]
for m in MS:
    tr=eff[('train',10,m)]; oo=eff[('oos',10,m)]; rtr=res[f'train|10|{m}']
    m_rows.append(f"""<tr><td class='l'><b>m={m}%</b></td>
      <td>{pct(tr['hit'],1)}</td><td>{tr['gain_trade']:.2f}%</td><td>{tr['gain_day']:.3f}%</td>
      <td class="sep">{pct(oo['hit'],1)}</td><td>{oo['gain_trade']:.2f}%</td><td>{oo['gain_day']:.3f}%</td>
      <td>{rtr['amplification']:.2f}×</td></tr>""")
M_TBL="\n".join(m_rows)

# ---- 表5 边际 ----
elb={(e['split'],e['m'],e['n_from'],e['n_to']):e for e in D['elbow']}
marg_rows=[]
for a,b in [(3,5),(5,7),(7,10),(10,12),(12,15),(15,20),(20,25)]:
    t=elb[('train',20,a,b)]; o=elb[('oos',20,a,b)]
    marg_rows.append(f"""<tr><td class='l'>n={a}→{b}（多持{b-a}日）</td>
      <td>{t['d_hit']*100:+.2f}pct</td><td>{t['per_day']*100:+.3f}</td>
      <td class="sep">{o['d_hit']*100:+.2f}pct</td><td>{o['per_day']*100:+.3f}</td></tr>""")
MARG_TBL="\n".join(marg_rows)

NSH="".join(f"<th>n={n}</th>" for n in NS)
NSH2="".join(f"<th>n={n}</th>" for n in NS)

# ---- 表6 双期稳健性（各 m，n=10 的 train/oos hit 与差值/比值） ----
stab_rows=[]
for m in MS:
    tr=eff[('train',10,m)]; oo=eff[('oos',10,m)]
    gap=(oo['hit']-tr['hit'])*100
    ratio=oo['hit']/tr['hit'] if tr['hit'] else 0
    stab_rows.append(f"""<tr><td class='l'><b>m={m}%</b></td>
      <td>{pct(tr['hit'],1)}</td><td>{pct(oo['hit'],1)}</td>
      <td class="{'ok' if abs(gap)<5 else 'warn'}">{gap:+.2f}pct</td><td>{ratio:.2f}</td></tr>""")
STAB_TBL="\n".join(stab_rows)

HTML=f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>n×m 参数研究：持有期与涨幅目标的最优性价比</title>
<style>
:root{{--navy:#1e3a5f;--orange:#e8833a;--green:#2e8b6f;--red:#c0392b;--ink:#2c3e50;--mute:#7f8c8d;--line:#e8ecf1;--bg:#f4f6f9}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:"Microsoft YaHei","PingFang SC",sans-serif;color:var(--ink);background:var(--bg);line-height:1.75;font-size:15px}}
.wrap{{max-width:1180px;margin:0 auto;background:#fff;box-shadow:0 2px 28px rgba(30,58,95,.08)}}
header{{background:linear-gradient(135deg,#1e3a5f 0%,#2c5282 55%,#e8833a 140%);color:#fff;padding:52px 60px 44px}}
header .kicker{{font-size:13px;letter-spacing:3px;opacity:.85;text-transform:uppercase}}
header h1{{font-size:31px;margin:14px 0 10px;font-weight:800;letter-spacing:1px}}
header .sub{{font-size:16px;opacity:.92;max-width:820px}}
header .meta{{margin-top:24px;display:flex;gap:28px;flex-wrap:wrap;font-size:13px;opacity:.9}}
header .meta b{{display:block;font-size:18px;opacity:1;margin-top:3px}}
.sec{{padding:36px 60px;border-bottom:1px solid var(--line)}}
.sec:nth-child(even){{background:#fcfdfe}}
h2{{font-size:21px;color:var(--navy);margin-bottom:8px;display:flex;align-items:center;gap:12px}}
h2 .no{{background:var(--navy);color:#fff;width:30px;height:30px;border-radius:8px;display:inline-flex;align-items:center;justify-content:center;font-size:14px}}
h2 .no.o{{background:var(--orange)}}
.lead{{color:var(--mute);margin:6px 0 20px;font-size:14px}}
h3{{font-size:16px;color:var(--navy);margin:22px 0 8px}}
p{{margin:10px 0}}
.callout{{border-left:4px solid var(--orange);background:#fff8f2;padding:15px 20px;border-radius:0 8px 8px 0;margin:18px 0;font-size:14px}}
.callout.g{{border-color:var(--green);background:#f1faf6}}
.callout.r{{border-color:var(--red);background:#fdf2f1}}
.callout b{{color:var(--navy)}}
table{{width:100%;border-collapse:collapse;margin:16px 0;font-size:12.5px}}
th{{background:var(--navy);color:#fff;padding:9px 6px;text-align:center;font-weight:600}}
td{{padding:8px 6px;border-bottom:1px solid var(--line);text-align:center}}
td.l{{text-align:left}} tr:hover td{{background:#f7f9fc}}
td.sep{{border-left:2px solid var(--orange);background:#fffaf5}}
td.ok{{color:var(--green);font-weight:600}} td.warn{{color:#b8860b;font-weight:600}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:22px 0}}
.kpi{{background:#fff;border:1px solid var(--line);border-top:3px solid var(--orange);border-radius:10px;padding:16px;text-align:center}}
.kpi .v{{font-size:25px;font-weight:800;color:var(--navy)}}
.kpi .k{{font-size:12px;color:var(--mute);margin-top:4px}}
.chart{{margin:20px 0;text-align:center}}
.chart img{{max-width:100%;border:1px solid var(--line);border-radius:10px;box-shadow:0 2px 12px rgba(0,0,0,.05)}}
.tag{{display:inline-block;background:#eef2f7;color:var(--navy);padding:2px 10px;border-radius:12px;font-size:12px;margin:2px}}
.foot{{padding:28px 60px;color:var(--mute);font-size:12px;background:#fbfcfd}}
.note{{font-size:12.5px;color:var(--mute);margin-top:6px}}
</style></head><body><div class="wrap">
<header>
 <div class="kicker">QUANTITATIVE RESEARCH · 参数灵敏度专题</div>
 <h1>持有期 n 与涨幅目标 m：系统探索与最优性价比</h1>
 <div class="sub">突破"n=10、m=20"的固定假设，把命中口径的两个参数同时作为研究对象——用 8×7 参数网格量化命中比例的空间—时间权衡，用捕获率检验模式的广泛性，并给出可执行的参数推荐。</div>
 <div class="meta">
  <div>参数网格<b>8 个 n × 7 个 m = 56 组合</b></div>
  <div>样本规模<b>3,590,923 行 / 5,741 只</b></div>
  <div>训练 / 样本外<b>463 日 / 199 日</b></div>
  <div>报告日期<b>2026-11-20</b></div>
 </div>
</header>

<div class="sec">
 <h2><span class="no">01</span>执行摘要</h2>
 <p class="lead">一句话结论：命中率随 n 单调上升、随 m 单调下降，与前序观察一致；但"命中率最高"不等于"性价比最高"——把时间成本计入后，最优区间落在 <b>n=7~10、m=15~20</b>，推荐值 <b>n=10、m=20</b>（保持与前序口径一致，兼顾命中率、效率与广泛性）。</p>
 <div class="kpis">
  <div class="kpi"><div class="v">35.1%→46.3%</div><div class="k">训练期 m=20：n=10→25 命中率</div></div>
  <div class="kpi"><div class="v">63.7%→7.1%</div><div class="k">训练期 n=10：m=10→50 命中率</div></div>
  <div class="kpi"><div class="v">n 7~10</div><div class="k">边际效率最高的持有期区间</div></div>
  <div class="kpi"><div class="v">3.0×</div><div class="k">n10/m20 捕获率相对放大倍数</div></div>
 </div>
 <div class="callout g"><b>指标一结论：</b>命中率对 n 单调递增（m=20 时 n3 的 20.9% → n25 的 46.3%），对 m 单调递减（n10 时 m10 的 63.7% → m50 的 7.1%）；但每多持 1 日的边际命中从 n3→5 的 +2.73pct/日衰减到 n20→25 的 +0.54pct/日。<b>n>10 后收益明显递减，单纯拉长持有期不划算。</b></div>
 <div class="callout r"><b>指标二结论：</b>模式捕获率（C7 命中数 ÷ 全市场命中数）随 n 增大而下降——m=20 时训练期从 n3 的 0.985% 降到 n25 的 0.210%；但 C7 仅占全市场 0.12% 的选股，却捕获了 0.38% 的大涨股，<b>放大倍数始终 >1（n10 时 3.04×）</b>，说明模式确实聚焦到了高概率区域，只是"广泛性"有限，不能指望它覆盖市场上大部分牛股。</div>
</div>

<div class="sec">
 <h2><span class="no o">02</span>研究设计与口径</h2>
 <h3>2.1 参数与样本</h3>
 <p>持有期 <b>n ∈ {{3,5,7,10,12,15,20,25}}</b> 交易日，涨幅目标 <b>m ∈ {{10,15,20,25,30,40,50}}%</b>，共 56 组合。样本沿用前序：训练期 2024-02~2025-12（463 日 / 245.8 万行），样本外 2026-01~2026-10（199 日 / 109.4 万行）。选股池固定为前序推荐的 <span class="tag">C7 组合</span>（9 个 T 日可知条件），阈值只由训练期确定。</p>
 <h3>2.2 标签口径（与前序完全一致）</h3>
 <p>标签 = 触发日 T 之后，未来 n 个交易日内最高价相对 T 日收盘价涨幅 ≥ m%。即 <span class="tag">fwd_max_n = (max(high[T+1..T+n]) / close_T − 1)×100</span>。<b>要求 n 个交易日数据齐全</b>，不足则样本剔除。涨幅用矩阵前复权 close/high 计算，与前序 daily_pct 口径一致，禁用 quote 原始 pct_change。校验结果：在矩阵自身数据上重算，与缓存 fwd_max_5d/10d、y5/y10 的 diff 全为 0。</p>
 <div class="callout r"><b>防前视红线：</b>n、m 只用于构造"未来是否达标"的标签，用于事后评估；所有筛选因子仍是 T 日可知，样本按触发日归集，不用任何未来信息选股。mkt_hit5/10 等含前视字段不参与任何环节。</div>
 <h3>2.3 两个指标定义</h3>
 <p><b>指标一（命中比例）：</b>hit(n,m) = C7 池中 fwd_max_n ≥ m% 的样本数 ÷ C7 池样本数。<br>
 <b>指标二（广泛性/捕获率）：</b>capture(n,m) = C7 池中达标数 ÷ 全市场达标数；另算 <b>放大倍数 = capture ÷ (C7 池样本数 ÷ 全市场样本数)</b>，衡量模式相对其选股占比的"聚焦效率"。两指标均在 train/oos 双期独立计算。</p>
</div>

<div class="sec">
 <h2><span class="no">03</span>指标一：命中比例随 n、m 的变化</h2>
 <p>完整 8×7 网格（前 8 列=训练期，后 8 列=样本外，均按 n=3→25 排列）：</p>
 <table><thead><tr><th rowspan="2">涨幅目标</th><th colspan="8">训练期 hit(n,m)</th><th colspan="8">样本外 hit(n,m)</th></tr>
 <tr>{NSH}{NSH2}</tr></thead><tbody>{HIT_TBL}</tbody></table>
 <p class="note">读数示例：训练期 m=20 行，n=10 命中 35.1%、n=25 命中 46.3%；oos 同行为 33.0%→45.5%。双期规律高度一致。</p>
 <div class="chart"><img src="data:image/png;base64,{CH['n1']}" alt="命中率热力图"></div>
 <div class="callout"><b>单调性确认：</b>命中率对每个 n 随 m 增大而降低（目标越高越难达成），对每个 m 随 n 增大而升高（观察期越长越容易触及）。这印证了用户的观察——<b>"n 越大命中越高"是统计必然，不是策略优势</b>，因为持有期成本被忽略了。</div>
 <div class="chart"><img src="data:image/png;base64,{CH['n2']}" alt="命中率随n曲线"></div>
</div>

<div class="sec">
 <h2><span class="no o">04</span>性价比寻优：把时间成本算进来</h2>
 <h3>4.1 边际效率：n 的收益拐点</h3>
 <p>只看命中率会误选 n=25。把"每多持 1 个交易日换来多少命中率增量"算出来（m=20）：</p>
 <table><thead><tr><th>持有期变化</th><th>训练期 Δhit</th><th>每多1日(训练)</th><th>样本外 Δhit</th><th>每多1日(oos)</th></tr></thead><tbody>{MARG_TBL}</tbody></table>
 <div class="callout g"><b>拐点在 n=10。</b>n=3→10 阶段每多 1 日带来 +1.7~3.9pct 命中提升；n>10 后衰减到 +0.5~1.6pct/日，n=20→25 仅 +0.54pct/日（训练）与 +0.56pct/日（oos）。<b>从 n=10 继续拉长持有期，边际收益已明显不划算。</b></div>
 <h3>4.2 理想化收益与效率</h3>
 <p>用 <span class="tag">单次理想收益 = m × hit</span>（命中则拿到 m%、未命中记 0，未计交易成本与止损，仅作相对比较）、<span class="tag">每持仓日收益 = m × hit / n</span> 两个口径评估效率：</p>
 <table><thead><tr><th rowspan="2">持有期</th><th colspan="4">训练期</th><th colspan="4">样本外</th></tr>
 <tr><th>hit10</th><th>单次收益</th><th>每日收益</th><th>捕获率</th><th>hit10</th><th>单次收益</th><th>每日收益</th><th>捕获率</th></tr></thead><tbody>{PERF_TBL}</tbody></table>
 <div class="chart"><img src="data:image/png;base64,{CH['n3']}" alt="性价比对比"></div>
 <p class="note">图3a（n=10 固定）：m=15~20 的每日收益最高（训练 m=20 为 0.701%）；m>25 后效率快速下滑。图3b（m=20 固定）：n 越短每日收益越高，但命中率越低——需权衡。</p>
 <h3>4.3 m 的最优选择（n=10 固定）</h3>
 <table><thead><tr><th>涨幅目标</th><th>训练hit</th><th>单次收益</th><th>每日收益</th><th>样本外hit</th><th>单次收益</th><th>每日收益</th><th>放大倍数</th></tr></thead><tbody>{M_TBL}</tbody></table>
 <div class="callout g"><b>单次收益峰值在 m=20（训练）与 m=15~20（oos）：</b>n=10 时，训练期 m=20 的单次理想收益 7.01% 为各 m 最高；样本外 m=15 的 6.80% 略高于 m=20 的 6.60%。<b>综合双期，m=20 是稳健的最优单点</b>——既守住前序口径，又处在效率峰值附近；m 提到 25 以上命中率骤降（n10 时 25.8%），得不偿失。</div>
</div>

<div class="sec">
 <h2><span class="no">05</span>指标二：模式的广泛性与捕获率</h2>
 <p>指标二回答一个不同问题：C7 选出的、未来 n 日确实涨 m% 的股票，占当时全市场所有达标股票的比例是多少？这反映模式在"抓牛股"上的覆盖广度。</p>
 <table><thead><tr><th rowspan="2">涨幅目标</th><th colspan="8">训练期 capture(n,m)</th><th colspan="8">样本外 capture(n,m)</th></tr>
 <tr>{NSH}{NSH2}</tr></thead><tbody>{CAP_TBL}</tbody></table>
 <div class="chart"><img src="data:image/png;base64,{CH['n4']}" alt="捕获率热力图"></div>
 <div class="chart"><img src="data:image/png;base64,{CH['n5']}" alt="捕获率与放大倍数"></div>
 <div class="callout"><b>两个视角一起看：</b>① <b>绝对捕获率随 n 下降</b>（m=20 训练期 n3 的 0.985%→n25 的 0.210%），因为 n 越长全市场达标股票数暴涨，C7 那点选股占比自然被稀释——这提醒我们<b>不能用"抓住市场多少牛股"来要求一个只选 0.12% 股票的窄基策略</b>。② <b>相对放大倍数始终 >1 且随 n 缩短而放大</b>（n3 约 8×、n10 约 3×、n25 约 1.7×），证明 C7 的选股确实系统性地集中在高概率区域，聚焦效率显著。样本外捕获率整体高于训练期（n10 时 0.583% vs 0.375%），说明模式在近期市场的相对聚焦能力没有减弱。</div>
</div>

<div class="sec">
 <h2><span class="no o">06</span>推荐参数与可执行建议</h2>
 <h3>6.1 推荐值</h3>
 <table><thead><tr><th>情景</th><th>推荐 n</th><th>推荐 m</th><th>依据（训练 / 样本外）</th></tr></thead><tbody>
 <tr><td class='l'><b>默认（与前序口径一致）</b></td><td><b>10</b></td><td><b>20%</b></td><td class='l'>hit 35.1%/33.0%，边际拐点，单次收益峰值，放大 3.04×/3.76×</td></tr>
 <tr><td class='l'>追求效率（短持有期）</td><td>7</td><td>15~20%</td><td class='l'>每日收益 0.855%/0.774%（m20），命中 29.9%/27.1% 仍可接受</td></tr>
 <tr><td class='l'>追求命中（不介意长持有）</td><td>15~20</td><td>20%</td><td class='l'>hit 40.2%/43.7%（n15）与 43.7%/42.7%（n20），但边际已递减</td></tr>
 <tr><td class='l'>宽目标高命中</td><td>10~12</td><td>10~15%</td><td class='l'>m10 时 hit 63.7%/61.5%，但单次收益反低于 m20</td></tr>
 </tbody></table>
 <div class="callout g"><b>综合推荐：n=10、m=20（默认口径），最优区间 n=7~10、m=15~20。</b>理由：n=10 处于边际效率拐点，m=20 处于单次收益峰值，双期 hit 稳定在 33~35%，放大倍数 3× 以上，且与前序研究口径完全对齐、可直接复用既有筛选代码与报告结论。若实盘更看重资金周转效率，可用 n=7、m=15~20 作为激进档；若更看重命中确定性，可取 n=15、m=20 作为稳健档。</div>
 <h3>6.2 落地注意事项</h3>
 <ol>
  <li><b>别把"n 越大命中越高"当策略优势</b>——那是时间换空间的统计必然，必须配合边际效率与资金周转一起看。</li>
  <li><b>m 不宜盲目上调</b>——m>25 后命中率骤降（n10 时 25.8%），单次理想收益反而低于 m=20；"相对提升 m"的空间有限，20% 已是效率甜点。</li>
  <li><b>广泛性有限是策略属性，不是缺陷</b>——C7 只选全市场 0.12% 的股票，能捕获 0.38% 的大涨股、放大 3 倍已属高效；不要用它去覆盖"市场上大部分牛股"。</li>
  <li><b>所有结论基于 train/oos 双期一致验证</b>，样本外捕获率不降反升，参数推荐不依赖单一市场阶段。</li>
 </ol>
 <div class="chart"><img src="data:image/png;base64,{CH['n6']}" alt="收益效率权衡"></div>
</div>

<div class="sec">
 <h2><span class="no">07</span>结论与理论对应</h2>
 <table><thead><tr><th>理论约束</th><th>本研究的对应发现</th></tr></thead><tbody>
 <tr><td class='l'>不确定性与趋势</td><td class='l'>n 拉长降低不确定性（命中率升），但趋势的胜负手在个股质量（C7 聚焦效率 3×），不是单纯等更久</td></tr>
 <tr><td class='l'>涨跌平衡</td><td class='l'>m 越高越难达成（m10→m50 命中 63.7%→7.1%），不存在"高目标还高命中"的免费午餐</td></tr>
 <tr><td class='l'>收益大与风险大并存</td><td class='l'>单次理想收益峰值 m=20 仅 7%，更高 m 牺牲命中；n 拉长虽升命中但边际递减、资金占用翻倍</td></tr>
 <tr><td class='l'>有量才有价 / 资金聚集</td><td class='l'>C7 以 0.12% 选股占比捕获 0.38% 大涨股，放大 3×，印证主力/概念信号对大涨的聚焦作用</td></tr>
 </tbody></table>
 <div class="callout r"><b>边界与免责：</b>"理想化收益 = m×hit"未计交易成本、滑点、止损与实际卖出价（标签用最高价，实盘难以精确捕获最高点），仅用于参数间的相对效率比较，不构成收益承诺。所有样本外结果基于 2026-01~2026-10，未来市场结构变化可能使最优区间漂移，建议定期用滚动窗口重估。</div>
</div>

<div class="sec">
 <h2><span class="no">08</span>双期稳健性与前序关系</h2>
 <h3>8.1 各 m 在 n=10 下的双期一致性</h3>
 <p>参数推荐能否成立，关键看规律是否在样本外复现。下表对比 n=10 时每个 m 的训练期与样本外命中率，以及两者差值与比值：</p>
 <table><thead><tr><th>涨幅目标</th><th>训练期 hit</th><th>样本外 hit</th><th>样本外−训练</th><th>比值(oos/tr)</th></tr></thead><tbody>{STAB_TBL}</tbody></table>
 <div class="callout g"><b>稳健性判读：</b>所有 m 下样本外命中率都低于或接近训练期，但相对排序完全一致——m=10~20 的命中率在两个时期都稳居前列，m≥25 后都快速衰减。差值多在 2~9pct 之间，属正常的市场阶段差异，<b>没有出现"样本内外反向"的过拟合信号</b>。这说明 n、m 的单调规律是数据结构性特征，而非某一时期的偶然现象，推荐参数具备跨期可复用性。</div>
 <h3>8.2 与前序研究的关系</h3>
 <p>前序《选股因子增量归因研究报告》固定用 n=10、m=20 作为命中口径，得出 C7 组合训练期 35.0%、样本外 33.0% 的结论。本次把 n、m 放开后，n=10、m=20 依然是性价比与稳健性的综合最优——<b>这不是巧合，而是前序阈值选择的合理性得到了参数灵敏度分析的反向验证</b>。换句话说，前序"碰巧"选中的口径恰好落在效率甜点附近；本次研究把这份"碰巧"变成了"有据可查的最优区间 n=7~10、m=15~20"，让口径选择从经验判断升级为数据结论。</p>
 <div class="callout"><b>一句话沉淀：</b>命中率的分母（持有期 n）与分子门槛（涨幅 m）都会改变数字，但只有把"每单位时间换来的命中"算清楚，才能避免被"n 越大命中越高"的表象误导。这也是对"指标滞后效应""涨跌平衡""收益风险并存"三条理论约束的量化落地。</div>
</div>

<div class="foot">
 <p><b>数据与合规声明：</b>本报告基于 stockDisplay 项目只读数据（快照 2024-02-01~2026-11-10），分析脚本运行于独立工作目录，未修改任何项目数据文件、未改动项目代码。n×m 标签均由矩阵前复权 close/high 重算，与前序 daily_pct 口径一致；所有筛选因子仅用 T 日可知数据，参数仅用于事后评估标签，无前视。训练期 463 交易日 / 样本外 199 交易日，C7 阈值只由训练期确定。</p>
 <p style="margin-top:10px;color:#b0b8c0">n×m 参数灵敏度研究 · 量化研究专题 · 生成于 2026-11-20</p>
</div>
</div></body></html>"""

out=WS/"n_m参数研究报告.html"
out.write_text(HTML,encoding="utf-8")
print("WROTE",out,out.stat().st_size,"bytes",flush=True)
print("CHARTS",len(CH),flush=True)
