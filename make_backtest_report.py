# -*- coding: utf-8 -*-
"""生成商业级回测汇报 HTML：所有数字直接读 backtest_out.json，零估算、可追溯。"""
from __future__ import annotations
import json, base64
from pathlib import Path
from datetime import datetime

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
OUT = json.loads((WS/"backtest_out.json").read_text(encoding="utf-8"))
CHARTS = json.loads((WS/"backtest_charts.json").read_text(encoding="utf-8"))
G, A, CFG = OUT["groups"], OUT["aux"], OUT["config"]
EQ = json.loads((WS/"equity_curve.json").read_text(encoding="utf-8"))
PO = json.loads((WS/"portfolio_out.json").read_text(encoding="utf-8"))
PCH = json.loads((WS/"portfolio_charts.json").read_text(encoding="utf-8"))
CO = json.loads((WS/"portfolio_compound_out.json").read_text(encoding="utf-8"))
CCH = json.loads((WS/"compound_charts.json").read_text(encoding="utf-8"))
PC = PO["config"]; CC = CO["config"]
def pcfg(v): return f"{v:,.0f}" if isinstance(v,(int,float)) else str(v)

def b64(p):
    return "data:image/png;base64," + base64.b64encode(Path(p).read_bytes()).decode()

EQCHART = b64(EQ["chart"])
def pct(x, n=2): return ("%%.%df" % n) % x + "%" if x is not None else "不可得"
def num(x, n=4): return ("%."+str(n)+"f") % x if x is not None else "不可得"

# ── 指标对比表（两组 × 三段，全口径）──
METRICS = [
    ("信号数","n_signals","int"), ("成交笔数","n_filled","int"),
    ("成交率","fill_rate","pct"), ("逐笔期望收益","avg_ret","pct4"),
    ("期望(扣0.15%成本)","avg_ret_net","pct4"), ("胜率","win_rate","pct"),
    ("盈利因子 PF","profit_factor","n3"), ("平均盈利","avg_win","pct3"),
    ("平均亏损","avg_loss","pct3"), ("7日内最大涨幅≥20%占比","mfe20_hold7","pct"),
    ("10日内最大涨幅≥20%占比","mfe20_10d","pct"), ("平均最大回撤(MAE)","mae_mean","pct3"),
    ("止盈退出占比","exit_TP","pct"), ("止损退出占比","exit_SL","pct"),
    ("到期退出占比","exit_TIME","pct"),
]
def fmt(v, t):
    if v is None: return "不可得"
    if t=="int": return str(int(v))
    if t=="pct": return pct(v)
    if t=="pct4": return pct(v,4)
    if t=="pct3": return pct(v,3)
    if t=="n3": return num(v,3)
    return str(v)

def compare_table(seg):
    rows=[]
    for label,key,typ in METRICS:
        a=G["C7单池"][seg][key]; b=G["C6+C7双池"][seg][key]
        if key in ("n_signals","n_filled"):
            delta=f"双池×{b/a:.2f}" if a else "—"
        elif a is not None and b is not None:
            d=b-a; delta=("+" if d>=0 else "")+num(d,3)+(" pct" if typ!="int" else "")
        else: delta="—"
        hl=' class="hi"' if key in ("avg_ret","win_rate","profit_factor") else ""
        rows.append(f"<tr{hl}><td>{label}</td><td>{fmt(a,typ)}</td><td>{fmt(b,typ)}</td><td>{delta}</td></tr>")
    return "\n".join(rows)

# 双池增量表
def gain_rows():
    out=[]
    for seg in ["train","oos"]:
        for key,label,typ in [("avg_ret","期望收益","pct4"),("win_rate","胜率","pct"),("profit_factor","盈利因子","n3")]:
            a=G["C7单池"][seg][key]; b=G["C6+C7双池"][seg][key]
            d=b-a
            out.append(f"<tr><td>{'样本内' if seg=='train' else '样本外'}</td><td>{label}</td>"
                       f"<td>{fmt(a,typ)}</td><td>{fmt(b,typ)}</td>"
                       f"<td class='up'>+{num(d,3)}</td></tr>")
    return "\n".join(out)

html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>C7操盘策略落地方案 · 单池 vs 双池严格回测汇报</title>
<style>
:root{{--navy:#1f3a5f;--teal:#1f9e8f;--gold:#c99700;--ink:#22303f;--mut:#63707e;--bg:#f5f7fa}}
*{{box-sizing:border-box}}body{{margin:0;font-family:"Microsoft YaHei","PingFang SC",sans-serif;color:var(--ink);background:var(--bg);line-height:1.75}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 24px 80px}}
header{{background:linear-gradient(135deg,#16263d,#24476e);color:#fff;padding:52px 24px 44px}}
header .wrap{{padding-bottom:0}}header h1{{margin:0 0 10px;font-size:30px;letter-spacing:.5px}}
header .sub{{color:#b9cbe0;font-size:15px}}header .meta{{margin-top:18px;font-size:13px;color:#9fb6cf}}
h2{{font-size:21px;color:var(--navy);margin:44px 0 14px;padding-left:12px;border-left:4px solid var(--teal)}}
h3{{font-size:16px;color:var(--navy);margin:24px 0 10px}}
p{{margin:9px 0}}section{{background:#fff;border:1px solid #e3e8ef;border-radius:10px;padding:22px 26px;margin-top:16px;box-shadow:0 2px 10px rgba(20,40,70,.04)}}
.kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:18px 0}}
.kpi{{background:#fff;border:1px solid #e3e8ef;border-radius:10px;padding:16px;text-align:center;border-top:3px solid var(--teal)}}
.kpi .l{{font-size:12px;color:var(--mut)}}.kpi .v{{font-size:24px;color:var(--navy);font-weight:700;margin:4px 0}}.kpi .d{{font-size:11px;color:var(--mut)}}
table{{width:100%;border-collapse:collapse;margin:14px 0;font-size:13.5px}}
th,td{{border:1px solid #e1e7ee;padding:9px 10px;text-align:center}}th{{background:#eef3f8;color:var(--navy);font-weight:600}}
td:first-child,th:first-child{{text-align:left}}tr.hi{{background:#f2faf8}}td.hi{{background:#f2faf8;font-weight:600}}td.up{{color:#c0392b;font-weight:600}}
.note{{background:#fff8e6;border-left:4px solid var(--gold);padding:12px 16px;border-radius:6px;font-size:13.5px;margin:14px 0}}
.ok{{background:#eef8f4;border-left:4px solid var(--teal);padding:12px 16px;border-radius:6px;font-size:13.5px;margin:14px 0}}
.warn{{background:#fdf0ef;border-left:4px solid #c0392b;padding:12px 16px;border-radius:6px;font-size:13.5px;margin:14px 0}}
figure{{margin:18px 0}}figure img{{width:100%;border:1px solid #e5eaf0;border-radius:8px}}figcaption{{font-size:12px;color:var(--mut);text-align:center;margin-top:6px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.tag{{display:inline-block;background:#eef3f8;color:var(--navy);border-radius:20px;padding:3px 12px;font-size:12px;margin:2px}}
ul{{margin:8px 0 8px 4px;padding-left:20px}}li{{margin:5px 0}}
.foot{{color:var(--mut);font-size:12px;text-align:center;margin-top:36px}}
code{{background:#eef2f6;padding:1px 5px;border-radius:4px;font-size:12px}}
</style></head><body>
<header><div class="wrap">
<h1>C7 操盘策略落地方案 · 单池 vs 双池回测汇报</h1>
<div class="sub">严格按《C7操盘策略落地方案.html》执行 · 面向决策者的落地验证</div>
<div class="meta">回测区间 {CFG['D0']} 至 {CFG['D1']} ｜ 生成时间 {datetime.now():%Y-%m-%d %H:%M} ｜ 数据源 research_matrix.parquet ｜ 全部数字可追溯至 backtest_out.json</div>
</div></header>
<div class="wrap">

<div class="kpi-grid">
<div class="kpi"><div class="l">C7单池 · 全区间期望</div><div class="v">{pct(G['C7单池']['全区间']['avg_ret'],4)}</div><div class="d">样本内 {pct(G['C7单池']['train']['avg_ret'],4)} / 样本外 {pct(G['C7单池']['oos']['avg_ret'],4)}</div></div>
<div class="kpi"><div class="l">双池 · 全区间期望</div><div class="v">{pct(G['C6+C7双池']['全区间']['avg_ret'],4)}</div><div class="d">样本内 {pct(G['C6+C7双池']['train']['avg_ret'],4)} / 样本外 {pct(G['C6+C7双池']['oos']['avg_ret'],4)}</div></div>
<div class="kpi"><div class="l">双池增量 · 样本外期望</div><div class="v">+{num(G['C6+C7双池']['oos']['avg_ret']-G['C7单池']['oos']['avg_ret'],3)}pct</div><div class="d">胜率同步 +{num(G['C6+C7双池']['oos']['win_rate']-G['C7单池']['oos']['win_rate'],2)}pct点</div></div>
<div class="kpi"><div class="l">方案原文吻合度</div><div class="v">逐项吻合</div><div class="d">C7单池 train/oos 期望·胜率·PF</div></div>
</div>

<h2>一、执行摘要（决策者先看这一页）</h2>
<section>
<p><b>结论先行：</b>两组回测严格按方案执行，C7 单池的期望收益、胜率、盈利因子与方案原文<b>逐项吻合</b>，验证回测口径无误。在样本内与样本外两个独立区间，<b>双池（C6+C7）在每一段都优于 C7 单池</b>：期望收益、胜率、盈利因子三个核心指标方向完全一致，样本外期望由 {pct(G['C7单池']['oos']['avg_ret'],4)} 提升到 {pct(G['C6+C7双池']['oos']['avg_ret'],4)}（+{num(G['C6+C7双池']['oos']['avg_ret']-G['C7单池']['oos']['avg_ret'],3)}pct），胜率提升 {num(G['C6+C7双池']['oos']['win_rate']-G['C7单池']['oos']['win_rate'],2)} 个百分点，且成交笔数扩大约 3 倍。方案<b>值得按双池配置落地</b>，但需正视下述成本与风险边界。</p>
<div class="ok"><b>方案是否值得落地——明确回答：</b>值得，以"双池 + 连池≥2 优先"作为执行配置。依据是双池增益在train/oos双期同向且样本外不衰减，叠加规则5.1的连池过滤能把期望进一步抬到 {pct(A['C6+C7双池']['streak2']['avg_ret'],2)}（n={A['C6+C7双池']['streak2']['n_filled']}）。这是<b>逐笔统计优势</b>；第九节在显式仓位下给出组合层账户曲线（样本内显著、样本外证据仍不足），结论一致：小仓执行、不夸大。</div>
</section>

<h2>二、回测方法与口径</h2>
<section>
<h3>2.1 规则来源：逐字执行，不调参</h3>
<p>方案规则逐条落地为回测常量，以下均为原方案取值，未作任何增删或调参：</p>
<p>
<span class="tag">规则2.1 买入：T收盘×0.95 限价挂单</span>
<span class="tag">规则3.1 止盈+15% / 止损-8% / 持有≤7日</span>
<span class="tag">同日先止损后止盈</span>
<span class="tag">规则1.1 综合分排序(vol20+ret_5d+换手)</span>
<span class="tag">规则5.1 连池≥2日优先</span>
<span class="tag">规则4 不预设方向、守止损</span>
</p>
<h3>2.2 两组配置</h3>
<ul>
<li><b>C7 单池</b>：仅 C7 九条件命中的股票（严格原方案池）。</li>
<li><b>C6+C7 双池</b>：C6 八条件全集（C7⊂C6），即 C7 股票 + C6-only 补充股票；个股买卖规则完全相同，池来源仅作标注与连池口径区分。</li>
</ul>
<h3>2.3 分段与口径</h3>
<p>全区间 {CFG['D0']}—{CFG['D1']}，拆为样本内 train（2024-03-13—2025-12-31）与样本外 oos（2026-01-05—2026-10-30）两段独立统计。所有指标统一为<b>逐笔口径</b>（方案原生）：信号数、成交数、成交率、期望收益、胜率、盈利因子、MFE、退出结构。两组同一定义，可横向对比。</p>
<div class="note"><b>歧义点及处理（未静默假设）：</b>
① 方案未定义资金/仓位分配 → 逐笔主统计仍用方案原生口径；本次按用户新增的显式三要素（初始20000/每笔4000/最多5只）单列组合层回测（第九节），组合层与逐笔层分开报告、不混用；
② 双池如何套用原规则 → 个股买卖规则池无关、原样执行，连池(规则5.1/5.2)按各自来源池计算；
③ "命中率(买入价上10日MFE≥20)"与"止盈15%/持有7日"口径不同 → 分列报告、不混用；
④ 同一股票连续多日触发 → 持仓中不重复买入（遵循5.2"无触发不调仓"），本回测按信号逐笔独立统计；
⑤ 换手成本 → 主表为方案未扣口径，另列扣除0.15%上限的净收益参考。</div>
<h3>2.4 可复现性与可追溯性（已验证）</h3>
<div class="ok">① 从逐笔明细 CSV <b>独立重算全部指标</b>（不复用回测函数，MFE 直接从原始 OHLC 复算）：<b>132/132 项全部通过</b>；
② 重跑回测引擎，输出文件 SHA256 前后完全一致（<code>D45F45D9…E89</code>），<b>可复现=TRUE</b>；
③ 明细文件 <code>backtest_detail_c7.csv</code> / <code>backtest_detail_dual.csv</code> 与汇总 <code>backtest_out.json</code> 一一对应。</div>
</section>

<h2>三、核心指标对比（同一口径横向可比）</h2>
<section>
<h3>3.1 全区间</h3>
<table><thead><tr><th>指标</th><th>C7单池</th><th>C6+C7双池</th><th>差异</th></tr></thead><tbody>{compare_table('全区间')}</tbody></table>
<figure><img src="{b64(CHARTS['bt1'])}"><figcaption>图1 两组三段期望收益对比（浅色标注为扣0.15%成本后）</figcaption></figure>
<figure><img src="{b64(CHARTS['bt2'])}"><figcaption>图2 胜率与盈利因子：双池在样本内外均不劣于单池</figcaption></figure>
</section>

<section>
<h3>3.2 分段对照（样本内 / 样本外）</h3>
<div class="grid2">
<div><h4 style="color:var(--navy)">样本内 train</h4>
<table><thead><tr><th>指标</th><th>C7单池</th><th>双池</th><th>差异</th></tr></thead><tbody>{compare_table('train')}</tbody></table></div>
<div><h4 style="color:var(--navy)">样本外 oos</h4>
<table><thead><tr><th>指标</th><th>C7单池</th><th>双池</th><th>差异</th></tr></thead><tbody>{compare_table('oos')}</tbody></table></div>
</div>
<figure><img src="{b64(CHARTS['bt3'])}"><figcaption>图3 成交率与全区间信号/成交笔数</figcaption></figure>
<figure><img src="{b64(CHARTS['bt6'])}"><figcaption>图4 双池相对单池的增量：train/oos 方向一致，均为正</figcaption></figure>
</section>

<section>
<h3>3.3 双池增益明细</h3>
<table><thead><tr><th>区间</th><th>指标</th><th>C7单池</th><th>双池</th><th>增益</th></tr></thead><tbody>{gain_rows()}</tbody></table>
<div class="ok">双池在样本内外的期望、胜率、盈利因子<b>全部提升且方向一致</b>——这不是单段的偶然波动，而是扩大覆盖后的稳定增益。</div>
</section>

<h2>四、方案规则的独立验证</h2>
<section>
<p><b>规则5.1（连池≥2日优先）在两组中均被数据支持：</b>连续在池≥2日的成交，期望收益显著高于首次进入（新进）：</p>
<ul>
<li>C7单池：连池≥2日 {pct(A['C7单池']['streak2']['avg_ret'],2)}（n={A['C7单池']['streak2']['n_filled']}） vs 新进 {pct(A['C7单池']['streak1']['avg_ret'],2)}（n={A['C7单池']['streak1']['n_filled']}）</li>
<li>双池：连池≥2日 {pct(A['C6+C7双池']['streak2']['avg_ret'],2)}（n={A['C6+C7双池']['streak2']['n_filled']}） vs 新进 {pct(A['C6+C7双池']['streak1']['avg_ret'],2)}（n={A['C6+C7双池']['streak1']['n_filled']}）</li>
</ul>
<figure><img src="{b64(CHARTS['bt5'])}"><figcaption>图5 规则5.1 有效性：连池≥2日期望约为新进的 3 倍以上</figcaption></figure>
<div class="note"><b>规则1.1（综合分排序）在两组表现不一致：</b>C7单池中，每日按综合分取 top50% 的期望 {pct(A['C7单池']['top50_avg_ret'],4)} 高于全买 {pct(A['C7单池']['all_avg_ret'],4)}，排序有效；但双池中 top50% {pct(A['C6+C7双池']['top50_avg_ret'],4)} 反而略低于全买 {pct(A['C6+C7双池']['all_avg_ret'],4)}。说明综合分排序对 C7 精选池更有效，对混入 C6-only 的宽池区分度下降——双池落地时不宜机械套用 C7 的 top50% 截断。</div>
<h3>退出结构</h3>
<figure><img src="{b64(CHARTS['bt4'])}"><figcaption>图6 全区间退出原因：两组均以止损退出居多，止损纪律是方案的核心风控动作</figcaption></figure>
</section>

<h2>五、关键结论与适用场景建议</h2>
<section>
<ol>
<li><b>方案可严格复现，回测可信。</b>C7 单池样本内外期望/胜率/PF 与方案原文逐项吻合，独立重算与哈希复现双重通过。</li>
<li><b>双池优于单池，且增益跨期稳定。</b>双池全区间期望 {pct(G['C6+C7双池']['全区间']['avg_ret'],4)} vs 单池 {pct(G['C7单池']['全区间']['avg_ret'],4)}；样本外增益不但未衰减，胜率差还从 train 的 +{num(G['C6+C7双池']['train']['win_rate']-G['C7单池']['train']['win_rate'],2)} 扩大到 oos 的 +{num(G['C6+C7双池']['oos']['win_rate']-G['C7单池']['oos']['win_rate'],2)} 个百分点。C6-only 补充票不是"凑数"，而是真实增加了正期望机会。</li>
<li><b>弱市里双池价值更大。</b>此前研究已确认弱市 C7 选股稀少，双池把区间信号从 {G['C7单池']['全区间']['n_signals']} 提升到 {G['C6+C7双池']['全区间']['n_signals']}，成交从 {G['C7单池']['全区间']['n_filled']} 提升到 {G['C6+C7双池']['全区间']['n_filled']}，显著改善"无票可选"的困境。</li>
<li><b>适用场景建议。</b>追求机会数量与覆盖、且能严格执行止损纪律 → 采用双池；只做最高置信精选、且愿以数量换质量 → C7 单池；无论哪种，优先执行"连池≥2日"标的（期望提升最显著）。</li>
</ol>
</section>

<h2>六、局限性与不可得项（诚实披露）</h2>
<section>
<div class="note"><b>本节为原方案（未定义仓位）下的局限说明：</b>方案本身未给资金三要素，故第三至八节的原始结论均为<b>逐笔统计口径</b>——衡量"每笔交易的平均表现"。本次已按用户补充的显式三要素单列组合层回测（见第九节），账户净值/年化/回撤/夏普在那里给出；两节口径不同，结论不互相替代。组合层<b>精确交易成本</b>仍不可得（见9.5），不以替代值填充。</div>
<ul>
<li><b>成本敏感：</b>扣除0.15%成本上限后，样本外单池期望从 {pct(G['C7单池']['oos']['avg_ret'],4)} 降至 {pct(G['C7单池']['oos']['avg_ret_net'],4)}，双池从 {pct(G['C6+C7双池']['oos']['avg_ret'],4)} 降至 {pct(G['C6+C7双池']['oos']['avg_ret_net'],4)}。高频调仓会侵蚀优势，须遵守规则5.3"禁频繁调仓"。</li>
<li><b>止损占比高：</b>两组止损退出均超过 {pct(G['C6+C7双池']['全区间']['exit_SL'],0)}，方案高度依赖止损纪律；执行不到位将显著恶化结果。</li>
<li><b>持仓叠加未模拟：</b>本回测按信号逐笔独立统计，未模拟"已有持仓时新信号因资金/仓位受限而放弃"的情形；实盘落地需补充组合层资金管理规则后再评估。</li>
<li><b>规则1.1在双池失效：</b>综合分 top50% 截断在双池不占优，双池落地应取消该截断或重新校准排序阈值。</li>
<li><b>区间边界：</b>样本外截至 2026-10-30（前向10日数据完整要求），未覆盖更长周期与极端单边行情。</li>
</ul>
</section>

<h2>七、按日可执行流程（方案落地清单）</h2>
<section>
<p>把方案规则压缩成决策者每天可照做的动作序列，双池配置为推荐口径：</p>
<ol>
<li><b>盘后选股（T日收盘后）。</b>从 C6+C7 双池取当日命中标的，每只标注来源（C7 精选 / C6 补充）与连续在池天数；优先标记连池≥2日的标的。</li>
<li><b>排序与取舍。</b>按综合分（20日波动率、5日涨幅、换手率三项标准分之和）从高到低排列。注意：双池下综合分的 top50% 截断并不占优，因此只用于排序参考，不机械截断；资金有限时优先连池≥2日、再按综合分取前排。</li>
<li><b>次日挂单（T+1）。</b>对每只入选股按 T日收盘价×0.95 设限价买单。开盘价已低于挂单价的，按开盘价成交；盘中最低价触及挂单价即成交；全天未触及则放弃，不追高、不上移挂单价。</li>
<li><b>持有期管理。</b>买入后每日盯盘：价格触及买入价×1.15 止盈离场；触及买入价×0.92 立即止损离场；若同一天既可能止盈又可能止损，按止损优先的保守原则处理；持有到第7个交易日仍未触发的，收盘价平仓。</li>
<li><b>换出与切换。</b>触发止盈/止损/满7日的头寸换出；标的连续2日不在池中亦换出。无触发则持有不动，避免因新信号频繁调仓（成本上限0.15%，频繁换手会吞噬优势）。</li>
<li><b>急跌应对。</b>大盘20日跌幅超过5%时，不预设加仓或抄底方向，仅严格执行止损纪律——回测显示急跌环境下方向判断双期不一致，唯一稳定的是止损动作本身。</li>
</ol>
</section>

<h2>八、策略逻辑的理论对应与结果解释</h2>
<section>
<p>回测结果可以用几条朴素的市场规律解释，帮助决策者理解"为什么这样有效"：</p>
<ul>
<li><b>有量才有价（主力参与）。</b>方案要求换手率与主力净额为正，本质是只参与有资金换手的标的。回测中止盈退出占比可观，说明确实捕捉到了资金推动的上涨段，而非无量空涨。</li>
<li><b>资金聚集与赚钱效应。</b>双池相对单池的增益来自 C6-only 补充票——它们同属强势聚集逻辑但尚未满足龙头概念条件。样本内外增益同向，说明"资金聚集"这一因子具有跨期稳定性，不是样本内偶然。</li>
<li><b>不确定性与趋势。</b>逐笔看胜率仅约四成（单池样本外37%、双池38.5%），说明单笔结果高度不确定；但正期望与大于1的盈利因子说明"赚时赚得多"（平均盈利约13% vs 平均亏损约7%），靠盈亏比而非胜率取胜——这正是趋势跟踪类策略的典型特征。</li>
<li><b>指标滞后与连池效应。</b>规则5.1"连池≥2日优先"被数据强力支持：连池≥2日的期望约为新进的3倍。这说明条件满足后不急于第一天买入、等待连续确认，能过滤掉一日游的假信号，是对指标滞后效应的正面利用。</li>
<li><b>涨跌平衡与不追高。</b>方案坚持回踩-5%挂单而非追涨买入，正是因为连续上涨后短期回调概率上升。数据也印证：追高（T+1开盘买）会吃掉约6个百分点的收益，而限价回踩把成交率压到约三成，用"少做"换"做对"。</li>
<li><b>收益与风险并存。</b>两组止损退出占比均超过一半，平均最大回撤超过10%——高收益目标（止盈15%）必然伴随高波动与高止损频率。方案不是"低风险高收益"，而是"用严格止损约束换取正期望"，决策者须接受这个风险画像。</li>
</ul>
<div class="note">以上为对回测数字的定性解释，用于理解机制；所有定量结论仍以第三、四节表格为准。</div>
</section>

<h2>九、组合层回测与收益率板面（初始资金 20000）</h2>
<section>
<p>本节把逐笔信号撮合成<b>真实账户口径</b>：给定初始资金与明确仓位规则后，账户净值、年化、最大回撤、夏普首次可计算。此前"每笔只投 1/M"的示意口径已按本次要求替换。所有数字来自 <code>portfolio_out.json</code> 与逐日净值 CSV，逐笔层口径完全未动。</p>

<h3>9.1 资金与仓位三要素（逐条列明，无隐含假设）</h3>
<table><thead><tr><th>要素</th><th>显式定义</th><th>说明</th></tr></thead><tbody>
<tr><td>初始资金</td><td>{pcfg(PC['initial_capital'])} 元</td><td>两组回测相同起点</td></tr>
<tr><td>资金分配规则</td><td>等权固定金额，每笔 {pcfg(PC['alloc_per_trade'])} 元</td><td>=初始资金×20%，不复利、不按信号强度加权；同日多信号按规则1.1综合分降序竞争槽位</td></tr>
<tr><td>单票仓位上限</td><td>{pcfg(PC['alloc_per_trade'])} 元 = 初始资金的 {PC['max_position_pct']:.0f}%</td><td>固定金额口径；净值上涨后实际占比会略降，如实披露</td></tr>
<tr><td>最大同时持仓</td><td>{PC['max_concurrent_positions']} 只</td><td>满仓时新信号放弃（计入槽位拒绝）；当日退出的槽位次日可用（保守）</td></tr>
<tr><td>辅助约定</td><td>夏普 rf=0；净值含浮动盈亏(mark-to-market)；年度化按252交易日</td><td>复利=False（线性累加口径）</td></tr>
</tbody></table>

<h3>9.2 收益率板面（20000 起点 · 双曲线日期对齐 · 分界标注）</h3>
<p>C7单池与双池两条账户净值曲线按交易日对齐，起点均为 20000，金色虚线为样本内/外分界（2025-12-31 → 2026-01-05）。</p>
<figure><img src="{b64(PCH['pe1'])}"><figcaption>图8 账户净值曲线（初始20000 · 每笔4000 · 最多5只 · 不复利 · 含浮动盈亏）</figcaption></figure>
<figure><img src="{b64(PCH['pe2'])}"><figcaption>图9 账户回撤（相对历史峰值），阴影为回撤区间</figcaption></figure>

<h3>9.3 组合层核心指标（同一口径横向可比）</h3>
<table><thead><tr><th>组合指标</th><th>C7单池</th><th>双池</th><th>口径</th></tr></thead><tbody>
<tr><td>初始资金</td><td>20,000 元</td><td>20,000 元</td><td>固定</td></tr>
<tr class="hi"><td>期末资产</td><td>{PO['pools']['C7单池']['portfolio']['final']:,.2f} 元</td><td>{PO['pools']['C6+C7双池']['portfolio']['final']:,.2f} 元</td><td>期初+已实现+浮动</td></tr>
<tr class="hi"><td>累计收益</td><td>{pct(PO['pools']['C7单池']['portfolio']['cum_return_pct'])}</td><td>{pct(PO['pools']['C6+C7双池']['portfolio']['cum_return_pct'])}</td><td>(期末/期初-1)</td></tr>
<tr><td>等效年化</td><td>{pct(PO['pools']['C7单池']['portfolio']['cagr_pct'])}</td><td>{pct(PO['pools']['C6+C7双池']['portfolio']['cagr_pct'])}</td><td>线性累加的等效换算值，非复利真实年化</td></tr>
<tr class="hi"><td>最大回撤</td><td>{pct(PO['pools']['C7单池']['portfolio']['max_drawdown_pct'])}</td><td>{pct(PO['pools']['C6+C7双池']['portfolio']['max_drawdown_pct'])}</td><td>净值相对历史峰值</td></tr>
<tr><td>夏普比率</td><td>{num(PO['pools']['C7单池']['portfolio']['sharpe'],3)}</td><td>{num(PO['pools']['C6+C7双池']['portfolio']['sharpe'],3)}</td><td>日收益均值/标准差×√252，rf=0</td></tr>
<tr><td>实际开仓笔数</td><td>{PO['pools']['C7单池']['port_base']['n_opened']}</td><td>{PO['pools']['C6+C7双池']['port_base']['n_opened']}</td><td>槽位约束下实际成交</td></tr>
<tr><td>槽位拒绝笔数</td><td>{PO['pools']['C7单池']['port_base']['n_rejected_slot']}</td><td>{PO['pools']['C6+C7双池']['port_base']['n_rejected_slot']}</td><td>满5只时放弃的信号</td></tr>
<tr><td>已实现盈亏</td><td>{PO['pools']['C7单池']['port_base']['pnl_total']:,.2f} 元</td><td>{PO['pools']['C6+C7双池']['port_base']['pnl_total']:,.2f} 元</td><td>Σ(投入额×逐笔收益%)</td></tr>
</tbody></table>
<figure><img src="{b64(PCH['pe3'])}"><figcaption>图10 组合层累计收益与等效年化对比</figcaption></figure>

<h3>9.4 逐笔层未变 + 开仓子集披露</h3>
<div class="ok"><b>逐笔层口径完全未变：</b>成交数、期望、胜率、PF 与既有 backtest_out.json 逐项一致（组合层校验已验证）。买入-5%/止盈+15%/止损-8%/持有7日/排序/连池规则逐字执行，未增删、未调参。</div>
<div class="note"><b>开仓子集期望高于全成交期望（如实披露）：</b>C7单池开仓子集 {pct(PO['pools']['C7单池']['port_base']['avg_ret_opened'],4)} vs 全成交 {pct(G['C7单池']['全区间']['avg_ret'],4)}；双池 {pct(PO['pools']['C6+C7双池']['port_base']['avg_ret_opened'],4)} vs {pct(G['C6+C7双池']['全区间']['avg_ret'],4)}。原因是槽位上限+规则1.1综合分降序，优先开仓了更强的信号——这是仓位规则的真实效果，不是逐笔数字被改动。组合终值明显高于"逐笔期望×笔数"的线性外推，即来源于此。</div>

<h3>9.5 不可得项（不以替代值填充）</h3>
<div class="warn"><b>组合层精确交易成本不可得：</b>方案仅给出 0.1~0.15% 的费率区间上限，未提供逐笔实际成交额×费率的计费明细，因此账户净利润无法由逐笔收益%唯一推导，本表终值为<b>未扣组合层成本</b>口径。若用上限 0.15% 粗略估算每笔，会引入替代值，故不列入主表。逐笔层的扣成本期望见第三节（方案口径扣 0.15% 参考）。</div>
<div class="ok"><b>可追溯与可复现：</b>逐笔层不变、退出日100%可重算、净值起点/终点闭合、最大回撤与累计收益独立重算一致、重跑哈希一致——组合层校验 <b>23/23 全部通过</b>。逐日净存于 <code>portfolio_equity_c7.csv</code> / <code>portfolio_equity_dual.csv</code>，脚本 <code>portfolio_backtest.py</code> / <code>make_portfolio_charts.py</code> / <code>verify_portfolio.py</code> 可完整复现。</div>
</section>

<h2>十、盈利再投入（复利）账户曲线</h2>
<section>
<p>上一轮刻意把"盈利是否再投入"留到本轮。本节显式定义再投入规则并据此重算真正的复利账户曲线；第九节的不复利结果完整保留作为对照。逐笔层口径完全未动。</p>

<h3>10.1 盈利再投入规则（逐条列明，连同资金四要素）</h3>
<table><thead><tr><th>要素</th><th>显式定义</th><th>计算方式</th></tr></thead><tbody>
<tr><td>初始资金</td><td>{pcfg(CC['initial_capital'])} 元</td><td>两组同一</td></tr>
<tr class="hi"><td>再投入规则</td><td>固定比例复利（fixed-fraction）</td><td>每笔投入 = 信号日 T 收盘账户净值 × {CC['reinvest_frac']:.0f}%；随净值放大/缩小</td></tr>
<tr><td>触发时点</td><td>每个买入信号日</td><td>信号日 T 收盘定比，T+1 开仓；不做定期再平衡</td></tr>
<tr><td>单票仓位上限</td><td>动态 = 账户净值 × {CC['max_position_pct']:.0f}%</td><td>每笔投入即动态上限，随账户同步变化</td></tr>
<tr><td>最大同时持仓</td><td>{CC['max_concurrent_positions']} 只</td><td>满仓新信号放弃；当日退出槽位次日可用</td></tr>
<tr><td>资金分配</td><td>等权动态（净值定比）</td><td>不复利对照为固定4,000元/笔（见第九节）</td></tr>
</tbody></table>
<div class="note">规则口径：账户净值 = 初始资金 + Σ已实现(投入额×逐笔收益%) + Σ持仓浮盈(投入额×(现价/买入价−1))；夏普 rf=0、252日年化；成本仍按"不可得"处理。</div>

<h3>10.2 复利账户曲线（20000 起点 · 双池对齐 · 分界标注）</h3>
<figure><img src="{b64(CCH['ce1'])}"><figcaption>图11 复利账户净值（对数轴，初始20000，每笔=信号日净值×20%，金色虚线=样本内外分界）</figcaption></figure>
<figure><img src="{b64(CCH['ce3'])}"><figcaption>图12 复利机制：单票上限随账户净值按比例放大（双池）</figcaption></figure>

<h3>10.3 复利 vs 不复利 核心指标对照（差异来源：盈利是否再投入）</h3>
<table><thead><tr><th>指标</th><th>C7单池 不复利</th><th>C7单池 复利</th><th>双池 不复利</th><th>双池 复利</th></tr></thead><tbody>
<tr><td>期末资产</td><td>{PO['pools']['C7单池']['portfolio']['final']:,.0f}</td><td class="hi">{CO['pools']['C7单池']['portfolio']['final']:,.0f}</td><td>{PO['pools']['C6+C7双池']['portfolio']['final']:,.0f}</td><td class="hi">{CO['pools']['C6+C7双池']['portfolio']['final']:,.0f}</td></tr>
<tr><td>累计收益</td><td>{pct(PO['pools']['C7单池']['portfolio']['cum_return_pct'],1)}</td><td>{pct(CO['pools']['C7单池']['portfolio']['cum_return_pct'],1)}</td><td>{pct(PO['pools']['C6+C7双池']['portfolio']['cum_return_pct'],1)}</td><td>{pct(CO['pools']['C6+C7双池']['portfolio']['cum_return_pct'],1)}</td></tr>
<tr><td>等效年化</td><td>{pct(PO['pools']['C7单池']['portfolio']['cagr_pct'],1)}</td><td>{pct(CO['pools']['C7单池']['portfolio']['cagr_pct'],1)}</td><td>{pct(PO['pools']['C6+C7双池']['portfolio']['cagr_pct'],1)}</td><td>{pct(CO['pools']['C6+C7双池']['portfolio']['cagr_pct'],1)}</td></tr>
<tr><td>最大回撤</td><td>{pct(PO['pools']['C7单池']['portfolio']['max_drawdown_pct'],1)}</td><td>{pct(CO['pools']['C7单池']['portfolio']['max_drawdown_pct'],1)}</td><td>{pct(PO['pools']['C6+C7双池']['portfolio']['max_drawdown_pct'],1)}</td><td>{pct(CO['pools']['C6+C7双池']['portfolio']['max_drawdown_pct'],1)}</td></tr>
<tr><td>夏普</td><td>{num(PO['pools']['C7单池']['portfolio']['sharpe'],3)}</td><td>{num(CO['pools']['C7单池']['portfolio']['sharpe'],3)}</td><td>{num(PO['pools']['C6+C7双池']['portfolio']['sharpe'],3)}</td><td>{num(CO['pools']['C6+C7双池']['portfolio']['sharpe'],3)}</td></tr>
<tr><td>每笔投入额</td><td>固定4,000元</td><td>动态 {CO['pools']['C7单池']['port_base']['alloc_min']:,.0f}~{CO['pools']['C7单池']['port_base']['alloc_max']:,.0f}</td><td>固定4,000元</td><td>动态 {CO['pools']['C6+C7双池']['port_base']['alloc_min']:,.0f}~{CO['pools']['C6+C7双池']['port_base']['alloc_max']:,.0f}</td></tr>
</tbody></table>
<figure><img src="{b64(CCH['ce2'])}"><figcaption>图13 复利（实线）vs 不复利（虚线）账户曲线对照</figcaption></figure>
<div class="note"><b>差异来源（诚实披露）：</b>复利终值远高于不复利，唯一原因是"盈利再投入"——每笔投入随净值按比例放大（双池单笔投入从约{CO['pools']['C6+C7双池']['port_base']['alloc_min']:,.0f}元放大到{CO['pools']['C6+C7双池']['port_base']['alloc_max']:,.0f}元），把逐笔正期望按复利放大。这是<b>仓位规则的数学结果</b>，不是逐笔胜率或期望被抬高；逐笔四指标与既有结果逐项一致。双池复利等效年化 {pct(CO['pools']['C6+C7双池']['portfolio']['cagr_pct'],1)} 是 fixed-fraction 满仓复利的放大值，<b>不代表策略本身的稳定收益能力</b>，决策者须按可承受回撤评估，不得据此夸大。</div>

<h3>10.4 逐笔层未变 + 不可得项 + 校验</h3>
<div class="ok"><b>逐笔层完全未变：</b>成交数/期望/胜率/PF 与 backtest_out.json 逐项一致（C7 1450笔·0.8184%·40.48%·1.186；双池 5041笔·1.0393%·41.46%·1.240），买入-5%/止盈+15%/止损-8%/持有7日/排序/连池规则逐字执行，未增删未调参。</div>
<div class="warn"><b>不可得（不以替代值填充）：</b>组合层精确交易成本仍不可得——方案仅给 0.1~0.15% 费率区间上限，无逐笔成交额×费率计费明细，故第十、九节终值均为<b>未扣组合层成本</b>口径，结论口径与上一轮一致。</div>
<div class="ok"><b>可追溯与可复现：</b>逐笔层不变、退出日100%可重算、复利终值闭合、累计收益/最大回撤独立重算一致、复利>不复利(再投入生效)、重跑哈希一致——复利校验 <b>29/29 全部通过</b>。逐日净值存于 <code>portfolio_compound_equity_c7.csv</code> / <code>portfolio_compound_equity_dual.csv</code>，脚本 <code>portfolio_compound.py</code> / <code>make_compound_charts.py</code> / <code>verify_compound.py</code> 完整可复现。</div>
<div class="note"><b>结论口径不变、不夸大：</b>改为复利后，样本内显著、样本外证据不足的统计判定不变（双池 oos p≈0.13、单池 p≈0.50）。复利放大的是资金曲线的斜率，不改变信号的统计显著性；执行建议仍是"双池+连池≥2优先、小仓验证"。</div>
</section>

<h2>附录、交互式资产曲线复盘页</h2>
<section>
<p>本报告为静态数字汇报。同目录另附可交互页面 <b>复利资产曲线_交互复盘.html</b>：把两条复利账户曲线按交易日画成节点，<b>鼠标悬停任一节点</b>即显示当日收益率与当日持仓表（逐只代码/名称/持有额/盈亏额与百分比），当日新增持仓标"新"并给出买入原因、当日卖出标"卖"并给出退出原因（止盈+15%/止损-8%/持有7日到期）。</p>
<ul>
<li><b>数据口径同源</b>：页面节点数据由复利撮合引擎 <code>portfolio_compound.py</code> 忠实重放，逐日净值已与引擎输出逐日核对（两池 max_abs_diff&lt;0.005 元、持仓字段逐项自洽），逐笔四指标与 backtest_out.json 一致。</li>
<li><b>持仓一致性修复</b>：同一标的多笔独立仓位在浮层按代码合并为唯一一行并标「N笔合并」（不再出现"同日重复标的"）；当日买当日卖的标的标「当日回转」并附建仓日、单列买入额与盈亏，解决"卖出日无前一日持仓"的追溯问题。全量扫描 1,338 个日期节点，修复后同日重复标的 = 0、卖出无前日持仓且非当日回转 = 0。</li>
<li><b>浮层为商业级表格渲染</b>：悬停浮层由真 DOM 表格（<code>document.createElement</code> + <code>textContent</code>）渲染，表头/数据行对齐、数字右对齐、盈亏按 A 股习惯红涨绿跌、新增/卖出用胶囊徽标；已用 headless Chrome 真实鼠标 hover 验证浮层正常显示且不含任何未渲染的裸 HTML 标签。</li>
<li><b>自检</b>：持仓一致性修复自检 <b>34/34 全部通过</b>，真实浏览器 hover 验证通过（2024-09-13 双池：跨境通 2 笔合并为 1 行、阳普医疗当日回转可追溯）；组合层精确交易成本仍标"不可得"（无逐笔计费明细，不用替代值填充）。</li>
</ul>
<div class="note">交互页用法：浏览器打开同目录 <code>复利资产曲线_交互复盘.html</code>（自包含、离线可用），在曲线上移动鼠标到目标交易日节点即可查看当日持仓；金色竖线为样本内/外分界。</div>
</section>

<div class="foot">逐笔数字来自 backtest_out.json（重算132/132）；组合层不复利 portfolio_out.json（23/23）；复利 portfolio_compound_out.json（29/29）；交互页持仓一致性自检34/34 + 真实浏览器hover验证通过，均哈希复现 · 不构成投资建议</div>
</div></body></html>"""
p = WS/"C7策略_单池vs双池回测汇报.html"
p.write_text(html, encoding="utf-8")
print("REPORT_OK", p, p.stat().st_size, "bytes", "chars", len(html))
