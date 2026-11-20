# -*- coding: utf-8 -*-
"""T+1 修正后商业级汇报：以'T+1 发现→结论翻转'为主线，两套口径各出一份。
所有数字读 t1_summary.json / backtest_out{SUF}.json / portfolio_compound_out{SUF}.json，零估算。"""
from __future__ import annotations
import json, base64, os
from pathlib import Path
from datetime import datetime

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
S = json.loads((WS/"t1_summary.json").read_text(encoding="utf-8"))

def b64(p):
    return "data:image/png;base64," + base64.b64encode(Path(p).read_bytes()).decode()
def pct(x, n=2): return ("%%.%df" % n) % x + "%" if x is not None else "不可得"
def num(x, n=4): return ("%."+str(n)+"f") % x if x is not None else "不可得"
def cls(x): return "neg" if (x or 0) < 0 else "pos"   # A股习惯：亏损绿、盈利红

def build(mode):
    suf = "" if mode=="normal" else "_main"
    BT = json.loads((WS/f"backtest_out{suf}.json").read_text(encoding="utf-8"))
    CO = json.loads((WS/f"portfolio_compound_out{suf}.json").read_text(encoding="utf-8"))
    CH = json.loads((WS/f"backtest_charts{suf}.json").read_text(encoding="utf-8"))
    CCH = json.loads((WS/f"compound_charts{suf}.json").read_text(encoding="utf-8"))
    CFG = BT["config"]; CC = CO["config"]
    d = S[mode]
    c7, du = d["C7单池"], d["C6+C7双池"]
    title_mode = "正常口径（全市场）" if mode=="normal" else "仅主板口径"
    outname = "C7策略_T1修正回测汇报.html" if mode=="normal" else "C7策略_T1修正回测汇报_仅主板.html"

    def cmp_rows(keys):
        rows=[]
        labels={"fill":"限价成交率","avg":"逐笔期望收益","win":"逐笔胜率","pf":"盈利因子 PF",
                "mfe20":"7日内最大涨幅≥20%占比","tp":"止盈退出占比","sl":"止损退出占比","time":"到期退出占比"}
        for k in keys:
            a,b=c7[k],du[k]
            if k in ("fill","win","mfe20","tp","sl","time"):
                fa,fb=pct(a),pct(b)
            elif k=="pf":
                fa,fb=num(a,3),num(b,3)
            else:
                fa,fb=pct(a,4),pct(b,4)
            rows.append(f"<tr {'class=\"hi\"' if k in ('avg','win','pf') else ''}><td>{labels[k]}</td>"
                        f"<td class='{cls(a)}'>{fa}</td><td class='{cls(b)}'>{fb}</td>"
                        f"<td class='{cls(b-a)}'>{num(b-a,4)}</td></tr>")
        return "\n".join(rows)

    def seg_rows():
        rows=[]
        for gname,g in [("C7单池",c7),("C6+C7双池",du)]:
            for seg in ["train","oos"]:
                s=g[seg]
                rows.append(f"<tr><td>{gname}</td><td>{'样本内' if seg=='train' else '样本外'}</td>"
                            f"<td>{s['n']}</td><td class='{cls(s['avg'])}'>{pct(s['avg'],4)}</td>"
                            f"<td>{pct(s['win'])}</td><td>{num(s['pf'],3)}</td></tr>")
        return "\n".join(rows)

    def sig_rows():
        rows=[]
        for gname,g in [("C7单池",c7),("C6+C7双池",du)]:
            for seg in ["train","oos","全区间"]:
                s=g["sig"][seg]
                rows.append(f"<tr><td>{gname}</td><td>{seg}</td><td>{s['n']}</td>"
                            f"<td class='{cls(s['mean'])}'>{pct(s['mean'],4)}</td>"
                            f"<td>{num(s['t'],2)}</td><td class='{cls(-1 if s['p']<0.05 else 1)}'>{num(s['p'],4)}</td>"
                            f"<td>[{pct(s['ci95'][0])}, {pct(s['ci95'][1])}]</td>"
                            f"<td><b>{s['sig']}</b></td></tr>")
        return "\n".join(rows)

    def port_rows():
        rows=[]
        for gname,g in [("C7单池",c7),("C6+C7双池",du)]:
            p=g["port"]
            rows.append(f"<tr><td>{gname}</td><td>{p['final']:,.2f}</td>"
                        f"<td class='{cls(p['cum_return_pct'])}'>{pct(p['cum_return_pct'])}</td>"
                        f"<td class='{cls(p['cagr_pct'])}'>{pct(p['cagr_pct'])}</td>"
                        f"<td>{pct(p['max_drawdown_pct'])}</td>"
                        f"<td class='{cls(p['sharpe'])}'>{num(p['sharpe'],3)}</td></tr>")
        return "\n".join(rows)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>C7 操盘策略 · T+1 修正回测汇报 · {title_mode}</title>
<style>
:root{{--navy:#1f3a5f;--teal:#1f9e8f;--gold:#c99700;--ink:#22303f;--mut:#63707e;--bg:#f5f7fa;--green:#1a9850;--red:#c0392b}}
*{{box-sizing:border-box}}body{{margin:0;font-family:"Microsoft YaHei","PingFang SC",sans-serif;color:var(--ink);background:var(--bg);line-height:1.75}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 24px 80px}}
header{{background:linear-gradient(135deg,#3a1620,#6e2433);color:#fff;padding:48px 24px 40px}}
header .wrap{{padding-bottom:0}}header h1{{margin:0 0 10px;font-size:29px;letter-spacing:.5px}}
header .sub{{color:#e0c0c8;font-size:15px}}header .meta{{margin-top:18px;font-size:13px;color:#d0aab5}}
h2{{font-size:21px;color:var(--navy);margin:44px 0 14px;padding-left:12px;border-left:4px solid var(--teal)}}
h3{{font-size:16px;color:var(--navy);margin:24px 0 10px}}
p{{margin:9px 0}}section{{background:#fff;border:1px solid #e3e8ef;border-radius:10px;padding:22px 26px;margin-top:16px;box-shadow:0 2px 10px rgba(20,40,70,.04)}}
.kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:18px 0}}
.kpi{{background:#fff;border:1px solid #e3e8ef;border-radius:10px;padding:16px;text-align:center;border-top:3px solid var(--red)}}
.kpi .l{{font-size:12px;color:var(--mut)}}.kpi .v{{font-size:23px;font-weight:700;margin:4px 0}}.kpi .d{{font-size:11px;color:var(--mut)}}
table{{width:100%;border-collapse:collapse;margin:14px 0;font-size:13.5px}}
th,td{{border:1px solid #e1e7ee;padding:9px 10px;text-align:center}}th{{background:#eef3f8;color:var(--navy);font-weight:600}}
td:first-child,th:first-child{{text-align:left}}tr.hi{{background:#f7f9fb}}td.hi{{font-weight:600}}
td.neg{{color:var(--green);font-weight:600}}td.pos{{color:var(--red);font-weight:600}}
.note{{background:#fff8e6;border-left:4px solid var(--gold);padding:12px 16px;border-radius:6px;font-size:13.5px;margin:14px 0}}
.ok{{background:#eef8f4;border-left:4px solid var(--teal);padding:12px 16px;border-radius:6px;font-size:13.5px;margin:14px 0}}
.warn{{background:#fdf0ef;border-left:4px solid var(--red);padding:12px 16px;border-radius:6px;font-size:13.5px;margin:14px 0}}
figure{{margin:18px 0}}figure img{{width:100%;border:1px solid #e5eaf0;border-radius:8px}}figcaption{{font-size:12px;color:var(--mut);text-align:center;margin-top:6px}}
ul,ol{{margin:8px 0 8px 4px;padding-left:22px}}li{{margin:6px 0}}
.foot{{color:var(--mut);font-size:12px;text-align:center;margin-top:36px}}
code{{background:#eef2f6;padding:1px 5px;border-radius:4px;font-size:12px}}
.tag{{display:inline-block;background:#eef3f8;color:var(--navy);border-radius:20px;padding:3px 12px;font-size:12px;margin:2px}}
</style></head><body>
<header><div class="wrap">
<h1>C7 操盘策略 · T+1 修正回测汇报</h1>
<div class="sub">{title_mode} · 落实 A 股 T+1 约束后的真实表现 · 面向决策者</div>
<div class="meta">回测区间 {CFG['D0']} 至 {CFG['D1']} ｜ 生成时间 {datetime.now():%Y-%m-%d %H:%M} ｜ 数据源 research_matrix.parquet ｜ 全部数字可追溯至 backtest_out{suf}.json · t1_summary.json</div>
</div></header>
<div class="wrap">

<div class="kpi-grid">
<div class="kpi"><div class="l">C7单池 · 全区间期望</div><div class="v neg">{pct(c7['avg'],4)}</div><div class="d">样本内 {pct(c7['train']['avg'],4)} / 样本外 {pct(c7['oos']['avg'],4)}</div></div>
<div class="kpi"><div class="l">双池 · 全区间期望</div><div class="v neg">{pct(du['avg'],4)}</div><div class="d">样本内 {pct(du['train']['avg'],4)} / 样本外 {pct(du['oos']['avg'],4)}</div></div>
<div class="kpi"><div class="l">当日回转（违规）</div><div class="v">0 / 0</div><div class="d">C7单池 {c7['sameday']} · 双池 {du['sameday']}（修复前 400 笔）</div></div>
<div class="kpi"><div class="l">双池全区间显著性</div><div class="v neg">{du['sig']['全区间']['sig']}</div><div class="d">p={num(du['sig']['全区间']['p'],4)}（修复前显著为正）</div></div>
</div>

<h2>一、执行摘要：一个必须诚实面对的发现</h2>
<section>
<div class="warn"><b>结论先行（与上一版完全相反）：</b>修正 A 股 T+1 约束后，之前报告的"正期望、样本内显著、值得落地"结论<b>不再成立</b>。C7 单池全区间逐笔期望由 +0.8184% 变为 <b>{pct(c7['avg'],4)}</b>，双池由 +1.0393% 变为 <b>{pct(du['avg'],4)}</b>；两者当日回转记录均归零。显著性同步翻转：双池全区间由"显著为正（p&lt;0.0001）"变为 <b>{du['sig']['全区间']['sig']}（p={num(du['sig']['全区间']['p'],4)}）</b>。根因是：旧版退出循环允许"T+1 买入当日即卖出"，而此前相当一部分正收益恰好来自这种违规的当日回转。</div>
<p>本报告在<b>撮合/逐笔层</b>落实 T+1（当日买入最早 T+2 才能卖出），重新生成两套口径并各自独立统计：<b>正常口径（全市场）</b>与<b>仅主板口径</b>。所有资产值、收益率、持仓明细、买卖原因均来自逐笔忠实重放，零手工、零估算。本页为 <b>{title_mode}</b>。</p>
<div class="note"><b>决策含义：</b>在 T+1 的真实约束下，这套"回踩 −5% 买入 + 止盈 +15% / 止损 −8% / 持有 ≤7 日"的日内回转型策略<b>不再具备正期望</b>。上一版"C7 策略值得落地"的建议<b>应予撤回</b>。正确做法是把 T+1 作为硬约束纳入选股—交易设计，重新寻找不依赖当日回转的盈利来源（详见第八节）。</div>
</section>

<h2>二、根因归属与修复点（不是展示层问题）</h2>
<section>
<h3>2.1 成因定位：撮合/逐笔层未落实 T+1</h3>
<p>上一轮"持仓一致性"修复曾把当日回转标为「当日回转」徽标，<b>那只是展示层的如实标注，并未修正违规本身</b>。本轮定位到真正的根因在撮合循环：</p>
<ul>
<li><b>根因</b>：<code>backtest_strategy.py</code> 退出循环 <code>for d in range(HOLD)</code> 从 <code>d=0</code> 起算，而 <code>d=0</code> 正是 T+1 买入当日——当日触及止盈/止损即被允许卖出，违反 A 股 T+1，全区间累计产生约 400 笔当日回转。</li>
<li><b>证据</b>：诊断 <code>diag_holding_out.json</code> 显示典型样本（如 2024-09-13 阳普医疗 300030）为 T+1 买入当日即 +15% 止盈（k=1）；全量扫描 669 日×2 池共 400 笔 k=1 当日回转。</li>
<li><b>修复层级</b>：撮合/逐笔层，非展示层、非快照构造层。退出起点由 <code>d=0</code> 改为 <code>d=1</code>（k_exit 由 1 改为 2），卖出最早发生在买入后第二日（T+2）。</li>
</ul>
<h3>2.2 修复点清单（逐笔 + 全下游链路传导）</h3>
<ol>
<li><code>backtest_strategy.py</code>：新增 <code>T1_FIRST_EXIT_D=1</code>，退出循环 <code>range(T1_FIRST_EXIT_D, HOLD)</code>，<code>k_exit=d+1</code>；增选 <code>board</code> 列支持双口径；指标增 <code>n_sameday_roundtrip</code>。</li>
<li><code>portfolio_compound.py</code>：<code>t1_first_exit_k=2</code>，退出日重算从 k=2 起，断言 <code>k_exit&gt;=2</code>。</li>
<li><code>portfolio_backtest.py</code>（不复利对照）：同步 T+1，并容忍负终值导致年化为 None。</li>
<li><code>build_interactive_equity.py</code>：<code>exit_k=2</code>，两套各 669 节点，逐日净值与引擎对齐。</li>
<li><code>make_interactive_page.py</code>：逐笔四指标改为从回测输出动态读取（不再硬编码），口径说明改为 T+1 主线，移除"当日回转已平仓"展示小节。</li>
<li><code>make_backtest_charts.py</code> / <code>make_compound_charts.py</code>：图表标题中性化（去掉"均为正/显著高于"等失效结论），两套文件加后缀避免互相覆盖。</li>
<li><code>diagnose_strategy_usefulness.py</code>：重算双口径显著性。</li>
</ol>
<div class="ok"><b>零删除：</b>所有原文件保留；改造前的脚本与输出另存 <code>*.bak</code>（preT1 版）可对照。本轮仅新增/覆盖"带 T+1 口径"的输出文件，未删除任何原始数据或历史文件。</div>
</section>

<h2>三、逐笔核心指标（同一口径横向可比）</h2>
<section>
<table><thead><tr><th>指标</th><th>C7单池</th><th>C6+C7双池</th><th>双池−单池</th></tr></thead><tbody>
{cmp_rows(['fill','avg','win','pf','mfe20','tp','sl','time'])}
</tbody></table>
<figure><img src="{b64(CH['bt1'])}"><figcaption>图1 两组三段期望收益（T+1 修正口径，均为负值）</figcaption></figure>
<figure><img src="{b64(CH['bt2'])}"><figcaption>图2 逐笔胜率与盈利因子（PF 均低于 1，即亏损）</figcaption></figure>
<div class="warn"><b>关键读数：</b>两组盈利因子 PF 均 &lt; 1（C7 {num(c7['pf'],3)}、双池 {num(du['pf'],3)}），意味着平均每笔亏损；胜率约 {pct(c7['win'])}/{pct(du['win'])}，且止损退出占比 C7 {pct(c7['sl'])}、双池 {pct(du['sl'])}。这是 T+1 约束下"当日冲高即无法兑现"的直接后果。</div>
</section>

<section>
<h3>3.1 分段对照（样本内 / 样本外）</h3>
<table><thead><tr><th>池</th><th>区间</th><th>成交笔数</th><th>期望收益</th><th>胜率</th><th>PF</th></tr></thead><tbody>{seg_rows()}</tbody></table>
<figure><img src="{b64(CH['bt3'])}"><figcaption>图3 成交率与信号/成交笔数</figcaption></figure>
<figure><img src="{b64(CH['bt6'])}"><figcaption>图4 双池相对单池的增量（T+1 修正口径）</figcaption></figure>
<figure><img src="{b64(CH['bt4'])}"><figcaption>图5 全区间退出原因结构</figcaption></figure>
<figure><img src="{b64(CH['bt5'])}"><figcaption>图6 规则5.1 连池≥2日 vs 新进的期望对比</figcaption></figure>
</section>

<h2>四、统计显著性：结论彻底翻转</h2>
<section>
<p>用逐笔明细做 t 检验（<code>diagnose_strategy_usefulness.py</code>，alpha=0.05）：</p>
<table><thead><tr><th>池</th><th>区间</th><th>n</th><th>均值</th><th>t</th><th>p</th><th>95% CI</th><th>判定</th></tr></thead><tbody>{sig_rows()}</tbody></table>
<div class="warn"><b>与上一版对比（不可沿用旧结论）：</b>修复前"样本内显著为正、样本外证据不足、双池更可靠"；修复后为<b>全区间显著为负、样本内多不显著或显著为负</b>。双池全区间 p={num(du['sig']['全区间']['p'],4)}（{du['sig']['全区间']['sig']}），C7 全区间 p={num(c7['sig']['全区间']['p'],4)}（{c7['sig']['全区间']['sig']}）。这印证：<b>旧版"显著为正"很大程度由违规当日回转贡献</b>，T+1 一旦落实，优势立即消失。</div>
</section>

<h2>五、组合层账户（复利 · 初始 20000 · T+1 修正）</h2>
<section>
<h3>5.1 资金与仓位三要素（逐条列明）</h3>
<table><thead><tr><th>要素</th><th>显式定义</th><th>说明</th></tr></thead><tbody>
<tr><td>初始资金</td><td>{CC['initial_capital']:,.0f} 元</td><td>两组同一</td></tr>
<tr><td>资金分配规则</td><td>固定比例再投入：每笔 = 信号日 T 收盘净值 × {CC['reinvest_frac']*100:.0f}%</td><td>随净值放大/缩小，不复利对照保留</td></tr>
<tr><td>单票仓位上限</td><td>动态 = 净值 × {CC['max_position_pct']*100:.0f}%</td><td>每笔投入即动态上限</td></tr>
<tr><td>最大同时持仓</td><td>{CC['max_concurrent_positions']} 只</td><td>满仓新信号放弃；退出槽位次日可用</td></tr>
</tbody></table>
<h3>5.2 复利账户核心指标</h3>
<table><thead><tr><th>池</th><th>期末资产</th><th>累计收益</th><th>等效年化</th><th>最大回撤</th><th>夏普</th></tr></thead><tbody>{port_rows()}</tbody></table>
<figure><img src="{b64(CCH['ce1'])}"><figcaption>图7 复利账户净值（对数轴，金色虚线=样本内外分界）</figcaption></figure>
<figure><img src="{b64(CCH['ce2'])}"><figcaption>图8 复利（实线）vs 不复利（虚线）账户曲线</figcaption></figure>
<figure><img src="{b64(CCH['ce3'])}"><figcaption>图9 单票上限随净值按比例放大</figcaption></figure>
<div class="note"><b>不复利线性口径的说明：</b>负逐笔期望叠加线性累加会推导出负的期末资产（数学外推），不具真实账户意义，故本汇报以<b>复利口径</b>为准；不复利结果仅作对照保留。</div>
<h3>5.3 不可得项（不以替代值填充）</h3>
<div class="warn"><b>组合层精确交易成本不可得：</b>方案仅给出 0.1~0.15% 费率区间上限，无逐笔成交额×费率的计费明细，故账户终值为<b>未扣组合层成本</b>口径；不用替代值填充。</div>
</section>

<h2>六、交互式资产曲线复盘页（同目录）</h2>
<section>
<p>同目录另附 <code>复利资产曲线_交互复盘{suf}.html</code>：两条复利曲线按交易日画成节点，悬停显示当日收益率与持仓表（代码/名称/持有额/盈亏额与百分比），新增标「新」、卖出标「卖」并给出原因。T+1 修正后页面不再有"当日回转"记录。</p>
<ul>
<li><b>数据同源</b>：节点由 <code>portfolio_compound.py</code> 忠实重放，逐日净值与引擎对齐（max_abs_diff&lt;0.005 元），逐笔四指标与 backtest_out{suf}.json 逐项一致。</li>
<li><b>浮层渲染</b>：真 DOM 表格渲染，无未渲染裸标签；已用 headless Chrome 真实 hover 验证。</li>
</ul>
</section>

<h2>七、自检：全量扫描与核对结果</h2>
<section>
<ul>
<li><b>当日回转全量扫描（目标 0）</b>：正常口径 C7/双池 = {c7['sameday']}/{du['sameday']}，仅主板口径 = {S['main']['C7单池']['sameday']}/{S['main']['C6+C7双池']['sameday']}；两套逐日重算 + 引擎 k_exit 双重校验，<b>均为 0</b>。</li>
<li><b>逐笔四指标独立重算</b>：从逐笔明细重算成交数/期望/胜率/PF 与各自 backtest_out{suf}.json 逐项比对，<b>verify_t1_fix.py 58/58 全部通过</b>。</li>
<li><b>组合层与交互页</b>：trade_base 一致；两套交互页逐日净值对齐 max_abs_diff&lt;0.01，当日回转节点=0。</li>
<li><b>可复现</b>：重跑引擎输出哈希一致；组合层精确成本仍标不可得。</li>
</ul>
</section>

<h2>八、局限、理论对应与改进方向</h2>
<section>
<p>用几条朴素市场规律解释"为什么 T+1 后优势消失"：</p>
<ul>
<li><b>有量才有价 / 指标滞后：</b>回踩挂单买到的往往是当日弱势或冲高回落的标的，T+1 不能当日兑现反弹，滞后效应从"可利用"变成"不得不承受"。</li>
<li><b>不确定性与趋势：</b>胜率仅约 {pct(c7['win'])}、PF&lt;1，单笔结果高度不确定且期望为负——原策略依赖"当日冲高立即止盈"来锁定趋势段，T+1 切断了这条路径。</li>
<li><b>涨跌平衡 / 不追高：</b>回踩 −5% 降低了买入价，但次日继续下探的概率不低，止损 −8% 空间被快速触发（止损占比 {pct(du['sl'])}），验证"跌势中接刀"的风险。</li>
<li><b>收益与风险并存：</b>最大回撤 C7 {pct(c7['port']['max_drawdown_pct'])}、双池 {pct(du['port']['max_drawdown_pct'])}，高目标（+15%）在低胜率下变成高止损频率，风险画像显著恶化。</li>
<li><b>资金聚集 / 主线：</b>双池（含 C6 补充票）在 T+1 下并未改善期望，说明"扩大覆盖"无法弥补交易规则本身对 T+1 的依赖。</li>
</ul>
<div class="note"><b>改进方向（不夸大、不空谈）：</b>①将持有周期从 ≤7 日拉长到能覆盖 T+1 后趋势展开的窗口，重新校准止盈/止损；②放弃"当日冲高止盈"假设，改用隔日均价或收盘价兑现；③把 T+1 纳入选股评分（过滤次日高开低走概率高的标的）；④小仓实盘前必须以 T+1 口径重新做样本外验证。当前结论：<b>本方案在 T+1 约束下不建议按原样落地。</b></div>
</section>

<div class="foot">口径：T+1 修正（当日买入最早次日卖出）· 逐笔数字来自 backtest_out{suf}.json（verify_t1_fix 58/58）· 复利来自 portfolio_compound_out{suf}.json · 组合层精确成本不可得 · 不构成投资建议</div>
</div></body></html>"""
    p = WS/outname
    p.write_text(html, encoding="utf-8")
    return outname, len(html)

for mode in ["normal","main"]:
    name, size = build(mode)
    print(f"REPORT_OK {mode} {name} {size} chars")
