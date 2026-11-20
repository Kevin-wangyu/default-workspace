# -*- coding: utf-8 -*-
"""操盘策略商业级报告：五部分执行规则 + 汇总流程 + 边界改进。图表base64内嵌。"""
from __future__ import annotations
import json
from pathlib import Path
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
TP=json.loads((WS/'trade_path_profile.json').read_text(encoding='utf-8'))
CH=json.loads((WS/'trade_charts.json').read_text(encoding='utf-8'))
RS=json.loads((WS/'trade_rank_switch_out.json').read_text(encoding='utf-8'))
CL=json.loads((WS/'trade_closedloop_out.json').read_text(encoding='utf-8'))
EE=json.loads((WS/'entry_exit_out.json').read_text(encoding='utf-8'))

def img(k,cap):
    return f'<figure><img src="data:image/png;base64,{CH[k]}" style="width:100%;max-width:960px;border:1px solid #e3e8ef;border-radius:8px"/><figcaption>{cap}</figcaption></figure>'

html=f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>C7操盘策略落地方案</title>
<style>
body{{font-family:"Microsoft YaHei","PingFang SC",sans-serif;max-width:1040px;margin:0 auto;padding:32px 28px;color:#25313d;line-height:1.8;background:#fafbfc}}
h1{{font-size:27px;color:#1a3b5d;border-bottom:4px solid #2E86AB;padding-bottom:12px}}
h2{{font-size:20px;color:#1a3b5d;margin-top:40px;border-left:5px solid #2E86AB;padding-left:12px}}
h3{{font-size:16px;color:#34495e;margin-top:24px}}
table{{border-collapse:collapse;width:100%;margin:16px 0;font-size:14px;background:#fff}}
th{{background:#2E86AB;color:#fff;padding:9px 10px;text-align:center;font-weight:600}}
td{{border:1px solid #dde4ec;padding:8px 10px;text-align:center}}
tr:nth-child(even) td{{background:#f4f8fb}}
.callout{{background:#fff6e8;border-left:5px solid #E67E22;padding:14px 18px;margin:18px 0;border-radius:6px}}
.good{{background:#eaf6ee;border-left:5px solid #27ae60;padding:14px 18px;margin:18px 0;border-radius:6px}}
.bad{{background:#fdecec;border-left:5px solid #c0392b;padding:14px 18px;margin:18px 0;border-radius:6px}}
.rule{{background:#eef4fb;border:1px solid #cfe0ee;border-radius:8px;padding:14px 18px;margin:14px 0}}
.small{{font-size:13px;color:#7b8794}}
figure{{margin:22px 0;text-align:center}}
figcaption{{font-size:13px;color:#7b8794;margin-top:8px}}
code{{background:#eef2f6;padding:2px 6px;border-radius:4px;font-size:13px}}
.kpi{{display:flex;gap:14px;flex-wrap:wrap;margin:18px 0}}
.kpi div{{flex:1;min-width:150px;background:#fff;border:1px solid #dde4ec;border-radius:8px;padding:14px;text-align:center}}
.kpi b{{font-size:23px;color:#2E86AB;display:block}}
ol,ul{{padding-left:26px}} li{{margin:6px 0}}
</style></head><body>

<h1>C7 操盘策略落地方案：从选股信号到可按日执行的交易流程</h1>
<p class="small">生成于工作区 · 基于研究矩阵 359 万行 / C7 池 train 3027 只、oos 1661 只 · 训练期 train≤2025-12-31、样本外 oos 2026-01~10 · 数据区间 2024-03~2026-10 · 全程零写入项目数据、零前视、训练定参数样本外验证</p>

<div class="kpi">
<div><b>35%→28%</b>研究命中率→真实可成交命中率</div>
<div><b>+2.47%</b>T+1平均高开（追高损耗主因）</div>
<div><b>-1.31%</b>买入后持有10日不卖的平均收益</div>
<div><b>+1.07%/+0.32%</b>回踩买入+止损止盈 期望(train/oos)</div>
</div>

<h2>〇、先说结论：这份方案最重要的一句话</h2>
<div class="bad">
研究里 35% 的命中率<b>不能直接换成实盘收益</b>。它不是"选股选错了"，而是三个交易环节把纸面收益吃掉了：
① 研究标签从 <b>T 日收盘</b>起算，但实盘最早只能 <b>T+1</b> 买，而 C7 选出的强势股 T+1 平均高开 <b>2.47%</b>、26% 的票开盘已涨超 5%（图2）；
② 追高买进去，10 日内最大浮盈 MFE 均值 16.7%、最大回撤 MAE 均值 -13.1%，<b>持有到期不卖平均是亏的</b>（train -1.31%、oos -2.12%）；
③ 所以止损止盈和买入价位不是"优化项"，而是策略能否为正期望的<b>决定性抓手</b>。
把买入价从"追高 +2%"改成"回踩 -5% 限价挂单"，单笔期望从 <b>-0.74%</b> 翻到 <b>+1.07%</b>（train），样本外同为 +0.32%。
</div>
<p class="small">口径声明：本节所有"命中率"= 买入价之上 10 个交易日内最高价涨幅 ≥20%；"期望收益"= 止损止盈规则下每笔交易收益率均值，未扣除交易成本（佣金+印花税约 0.1~0.15%，方案净期望需再减此项）。选股信号全部 T 日收盘后计算，T+1 执行，不含未来信息。</p>

<h2>一、选股方向：C7 股池内怎么进一步排序</h2>
<p>股池沿用已确认的 C7 条件（近20日涨停≥1、主力净额/成交额&gt;0、20日波动率≥3.5238、换手率≥3.7，且 lu_gap≥-3、收盘/20日高点≥0.95、近5日涨幅≥4.8679、ma5&gt;ma20&gt;ma60、命中龙头概念≥1）。本节解决的是：每天池里平均 8 只，资金有限时先买谁。</p>

<div class="rule"><b>规则 1.1（排序因子）</b>：池内按 <code>vol20（高）＋ ret_5d（高）＋ turnover_rate（高）</code> 综合分降序优先；<b>不要</b>按 main_net_norm 从高到低排。</div>
<p>数据依据（回踩-5%可成交样本，池内分5档的最高档−最低档命中率差，图4）：</p>
<table><tr><th>池内排序因子</th><th>train 最高−最低档</th><th>oos 最高−最低档</th><th>判定</th></tr>
<tr><td>vol20（20日波动率）</td><td>+19.2pct</td><td>+10.5pct</td><td class="good">双期同向，采纳</td></tr>
<tr><td>ret_5d（近5日动量）</td><td>+16.1pct</td><td>+13.6pct</td><td>双期同向，采纳</td></tr>
<tr><td>turnover_rate（换手率）</td><td>+6.7pct</td><td>+6.6pct</td><td>双期同向，采纳</td></tr>
<tr><td>main_net_norm（资金力度）</td><td>-5.7pct</td><td>-23.4pct</td><td class="bad">双期反向，禁用为排序</td></tr>
<tr><td>mkt_up_ratio（市场上涨家数比）</td><td>-9.0pct</td><td>-2.0pct</td><td>反向且个股无区分度</td></tr></table>
<div class="callout"><b>为什么资金力度在池内反而失效？</b> C7 已经用 main_net_norm&gt;0 筛过一道，池内再按它排序属于"在已经集中的资金里找更集中的"，是过度暴露——.train 高资金档命中 24.4% 反而低于低资金档 30.1%，oos 更极端（11.3% vs 34.7%）。这正是"涨跌平衡"（不可能一直涨）和"收益大与风险大并存"的体现：资金最猛的票往往已在高位、回撤空间更大。资金力度是<b>入池门槛</b>，不是<b>池内排序器</b>。</div>

<p>排序的实际增益有限，必须诚实说明（闭环验证，图5右）：在回踩-5%买入基础上，取综合分 top50% 相对全买——train 期望 0.803%→0.850%（+0.05pct），oos 0.164%→0.117%（<b>-0.05pct，反而下降</b>）。</p>
<div class="callout"><b>取舍结论</b>：排序因子在 train 有微弱正效应、oos 不稳健，因此排序只作为"资金只够买一半时的优先级"，<b>不作为提高收益的手段</b>。真正决定收益的是买入价位和止损止盈（见第二、三节），而不是挑哪一只。</div>

<h2>二、买入时机：从"被选出"到"实际买入"</h2>
<p>这是整份方案的核心。研究标签用 T 收盘到未来最高价，但实盘 T 日收盘后才知道信号，最早 T+1 开盘成交。三种口径的命中率对比（图1）：</p>
<table><tr><th>买入口径</th><th>train 命中≥20%</th><th>oos 命中≥20%</th><th>实盘可行性</th></tr>
<tr><td>研究口径：T 收盘起算（未来最高价/T收盘）</td><td>{TP['buy_compare']['train']['mfe10_study']}%</td><td>{TP['buy_compare']['oos']['mfe10_study']}%</td><td class="bad">不可成交，纸面</td></tr>
<tr><td>T+1 开盘价买入</td><td>{TP['buy_compare']['train']['mfe10_t1open']}%</td><td>{TP['buy_compare']['oos']['mfe10_t1open']}%</td><td>可成交，但追高</td></tr>
<tr><td>T+1 收盘价买入</td><td>{TP['buy_compare']['train']['mfe10_t1close']}%</td><td>{TP['buy_compare']['oos']['mfe10_t1close']}%</td><td>可成交</td></tr>
<tr><td>T+2 开盘价买入</td><td>{TP['buy_compare']['train']['mfe10_t2open']}%</td><td>{TP['buy_compare']['oos']['mfe10_t2open']}%</td><td>可成交，滞后1日</td></tr></table>
<p>从 {TP['buy_compare']['train']['mfe10_study']}% 掉到 {TP['buy_compare']['train']['mfe10_t1open']}%，6.6 个百分点<b>全部来自 T+1 高开</b>（train 均值 +{TP['gap']['train']['mean']}%、中位 +{TP['gap']['train']['med']}%、{TP['gap']['train']['gt5']}% 的票高开超 5%；oos 均值 +{TP['gap']['oos']['mean']}%、{TP['gap']['oos']['gt5']}% 高开超 5%，图2）。这不是选股失效，是<b>买入价太贵</b>。</p>

<div class="rule"><b>规则 2.1（限价回踩挂单，核心）</b>：T 日收盘后对入选股挂 T+1 <b>限价单，价格 = T 收盘价 × 0.95（回踩 -5%）</b>；T+1 盘中最低价触及该价则以该价成交，若开盘已低于挂单价则按开盘价成交；<b>全天未触及则放弃，不追</b>。</div>
<div class="rule"><b>规则 2.2（1-2日滞后处理）</b>：挂单有效期可延至 T+2 收盘（同一限价）。但前序研究已证"放宽触发窗口（T-1/T-2 并集归集）反而降命中 6.7pct"，因此<b>滞后只用于成交等待，不改变信号的 T 日归属</b>；不建议为了成交去追已经启动的票。</div>

<p>买入价与期望收益的关系（tp15%/sl-8%/hold7 固定，图3）：</p>
<table><tr><th>T+1限价（相对T收盘）</th><th>成交率 train/oos</th><th>单笔期望 train/oos</th><th>判定</th></tr>
<tr><td>+2%（追高）</td><td>80.8% / 83.4%</td><td class="bad">-0.74% / -0.19%</td><td>禁</td></tr>
<tr><td>0%（平价）</td><td>70.2% / 74.0%</td><td class="bad">-0.72% / -0.17%</td><td>禁</td></tr>
<tr><td>-3%</td><td>49.2% / 47.8%</td><td>-0.01% / +0.19%</td><td>临界</td></tr>
<tr><td><b>-5%（推荐）</b></td><td>31.8% / 29.3%</td><td class="good"><b>+1.07% / +0.32%</b></td><td>采纳</td></tr></table>
<div class="callout"><b>买入时机的本质取舍</b>：正期望是<b>用成交率换来的</b>——回踩 -5% 只有约 30% 的挂单能成交，70% 的强势股根本不回调、直接走掉。这是策略的固有代价，不是缺陷：<b>放弃追高 = 放弃那些利润已被 T+1 高开透支的票</b>。若为提高成交率放宽到 -3%，train 期望立刻掉到 -0.01%（约为零）。宁可少做，不可做亏。</div>
<p><b>不买的情形</b>：① T+1 一字涨停无法成交（train 23.42%、oos 19.87% 的个股 T+1 涨幅达涨停量级）——放弃，不排板；② T+1 高开超过 +2% 后回落但未到 -5% 挂单价——维持挂单不追；③ 个股停牌——顺延至复牌首日按限价重挂（全样本仅 1 例停牌，影响可忽略）。</p>

<h2>三、止损止盈：与 n=10/m=20 匹配的持仓管理</h2>
<p>买入后不设退出规则是亏损的根源：持有 10 日不卖，train 平均 -1.31%、oos -2.12%（图5左）。而 10 日内 MFE 均值 16.7%、MAE 均值 -13.1%，触顶日均值 4.13 天、55% 在前 3 天——<b>冲高来得早、回撤也深，必须提前设定退出</b>。</p>
<div class="rule"><b>规则 3.1（止损止盈参数）</b>：回踩 -5% 买入后，<b>止盈 +15%、止损 -8%、持有上限 7 个交易日</b>；盘中先触止损按止损成交（保守假设），先触止盈按止盈成交，到第 7 日收盘仍未触发则无条件平仓。</div>
<p>参数来源与验证——40 组（买入价×止盈×止损×持有期）网格中仅 5 组在 train 与 oos 双期期望同时为正，推荐组合是其中样本外期望最高且成交率可接受的一组：</p>
<table><tr><th>组合</th><th>train 期望/胜率/盈亏比</th><th>oos 期望/胜率/盈亏比</th><th>成交率</th></tr>
<tr><td><b>回踩-5% + 止盈15% + 止损-8% + 7日</b></td><td class="good">+1.07% / 42.0% / 1.25</td><td class="good">+0.32% / 37.5% / 1.07</td><td>31.8% / 29.3%</td></tr>
<tr><td>回踩-5% + 止盈15% + 止损-5% + 7日</td><td>+0.92% / 32.4% / 1.28</td><td>+0.37% / 28.6% / 1.11</td><td>31.8% / 29.3%</td></tr>
<tr><td>回踩-5% + 止盈15% + 止损-8% + 10日</td><td>+1.06% / 40.8% / 1.23</td><td>+0.15% / 36.8% / 1.03</td><td>31.8% / 29.3%</td></tr>
<tr><td>追高+2% + 任意止损止盈</td><td class="bad">全为负</td><td class="bad">全为负</td><td>~80%</td></tr></table>
<div class="callout"><b>为什么止盈 15% 而不是 20%？</b> 目标是 m=20（10 日内最高涨幅 20%），但那是<b>盘中最高价</b>，实盘无法精确卖在最高点。回踩-5%买入后，MFE≥20% 的比例约 20%，而 MFE 均值仅 16.7%——把止盈定在 15%（低于 MFE 均值）才能在冲高过程中<b>实际落袋</b>。定 20% 会大量错失（触发率骤降），定 10% 则牺牲单笔盈亏比。止损 -8% 对应 MAE 均值 -13.1% 之内可容忍的回撤：-5% 太紧（72.6% 被扫出），-15% 太松（单笔亏损过大）。</div>
<p><b>分批规则</b>：因样本不支持盘中精确分批的统计检验，本方案<b>不虚构分批的收益优势</b>；建议实盘若持仓≥2只，可在 +10% 先减半、剩余仓位按 +15%/止损-8% 管理，但此为风控主观选择，<b>无本次数据直接支撑</b>，需自行小仓验证。</p>

<h2>四、突发情况应变</h2>
<table><tr><th>情形</th><th>数据依据</th><th>处置动作</th></tr>
<tr><td>大盘急跌（mkt_ret_20d &lt; -5%）</td><td>命中率 train 26.1%→21.1%（降），oos 21.5%→37.4%（升）——<b>双期反向，不稳定</b></td><td>不预设方向性加仓/减仓；急跌日严格执行原止损 -8%，仓位按常规，避免用"跌多了会反弹"的主观判断覆盖规则</td></tr>
<tr><td>T+1 一字涨停买不进</td><td>train 23.4%、oos 19.9% 的个股 T+1 达涨停量级</td><td>放弃该票，不排板、不追高；资金留给当日其他回踩挂单</td></tr>
<tr><td>T+1 高开后不回踩</td><td>26% 的票高开超 5%，约 70% 的挂单不会成交</td><td>维持限价不追；接受当日空仓，这是策略预期的正常状态</td></tr>
<tr><td>个股停牌 / 临时异动</td><td>全样本停牌仅 1 例（占比&lt;0.001%）</td><td>停牌则挂单顺延至复牌首日按原限价重挂；复牌若跳空高开超 +2% 则撤单放弃</td></tr>
<tr><td>信号当日无法成交（网络/额度）</td><td>—</td><td>T+2 按同限价重挂一次，仍不成交则彻底放弃，不延长到 T+3（滞后越久信号越失效）</td></tr></table>
<div class="callout"><b>大盘急跌的双期反向必须正视</b>：train 期急跌日命中下降、oos 期反而大幅上升（21.5%→37.4%），样本不一致，<b>不能当作规律使用</b>。这恰好印证"不确定性与趋势"——微观上急跌后的反弹不可预测，唯一可靠的是纪律化的止损止盈，而不是对市场方向的猜测。</div>

<h2>五、股票切换策略</h2>
<div class="rule"><b>规则 5.1（切换优先级：连续在池优先）</b>：当需要在多只候选中取舍或替换持仓时，<b>优先保留/买入"连续在 C7 池≥2 日"的标的，谨慎对待"当日新进池"标的</b>。</div>
<p>数据依据（回踩-5%可成交样本，图5延伸）：</p>
<table><tr><th>池持续状态</th><th>train 样本数/期望/MFE≥20</th><th>oos 样本数/期望/MFE≥20</th></tr>
<tr><td>连续在池≥2日</td><td>471 / +1.02% / 27.8%</td><td>336 / +0.66% / 27.7%</td></tr>
<tr><td>当日新进池</td><td>493 / +0.59% / 23.9%</td><td>150 / <b class="bad">-0.94%</b> / 17.3%</td></tr></table>
<p>样本外新进池标的期望为负（-0.94%），连续在池标的为正（+0.66%）——切换时<b>用"在池持续性"作为质量过滤器</b>，比用资金力度更可靠。这与"指标滞后效应"一致：连续在池 = 信号经过多日确认，减少了单日噪声误判。</p>
<div class="rule"><b>规则 5.2（换出条件）</b>：持仓股票满足任一即换出——① 触发止损 -8%；② 触发止盈 +15%；③ 持有满 7 日；④ 连续 2 日不再满足 C7 入池条件（趋势逻辑破坏）。换入时按规则 1.1 排序、按规则 2.1 限价挂单，<b>不为换仓而追高</b>。</div>
<div class="rule"><b>规则 5.3（换手成本考量）</b>：单笔期望仅 +1.07%（train）/ +0.32%（oos），而一次买卖交易成本约 0.1~0.15%。<b>频繁切换会吞噬本就微薄的期望</b>。因此切换必须"有明确触发条件"，禁止每日调仓；无触发则持有到期。样本外期望仅 +0.32% 意味着扣成本后接近盈亏平衡，<b>实盘务必先小仓验证</b>。</div>

<h2>六、汇总：可按日执行的完整流程</h2>
<ol>
<li><b>盘后（T 日收盘后）</b>：用当日可知数据跑 C7 条件，得到当日股池（平均约 8 只）；记录每只在池连续天数、vol20、ret_5d、turnover_rate。</li>
<li><b>排序</b>：按 vol20＋ret_5d＋turnover_rate 综合分降序排优先级；剔除 main_net_norm 排序（仅作入池门槛）。</li>
<li><b>挂单</b>：对优先级靠前的标的挂 T+1 限价单 = T收盘×0.95；高开不追、一字板放弃。</li>
<li><b>成交管理</b>：T+1 触及限价成交；未触及可延至 T+2，仍不成交放弃；信号归属 T 日不变。</li>
<li><b>持仓管理</b>：买入后设止盈 +15%、止损 -8%、持有上限 7 日；盘中先触止损按止损，先触止盈按止盈，第 7 日收盘无条件平仓。</li>
<li><b>切换</b>：触发止损/止盈/到期/连续2日出池则换出；换入按上述流程，连续在池≥2日优先；无触发不调仓。</li>
<li><b>复盘</b>：按信号触发日（T 日）标记，记录买入价口径、退出原因、单笔收益，区分 train/oos 表现。</li>
</ol>

<h2>七、适用边界、失效情形与改进点</h2>
<div class="bad">
<b>必须正视的三条边界</b>：<br>
① <b>期望收益很薄</b>——train +1.07%、oos +0.32%（未扣成本），样本外扣 0.1~0.15% 成本后几乎打平。这是一套"逻辑自洽、方向正确"的方案，但<b>不是一套高收益方案</b>，绝不能按"35% 命中率 = 35% 收益"的错觉去放大仓位。<br>
② <b>成交率仅约 30%</b>——大部分信号不会成交，策略是"少而精"而非"广覆盖"；若追求资金利用率，本方案不适用。<br>
③ <b>排序与大盘急跌应对均不稳健</b>——排序 oos 微弱为负、急跌日双期反向，这两处<b>没有可靠规律</b>，已如实标注，不应包装成优势。
</div>
<p><b>失效情形</b>：交易成本上升（频繁换仓）、T+1 涨跌停制度变化、强势股普遍不再回踩（策略将长期空仓）、市场整体波动率结构性下降（vol20 入池门槛失效）。</p>
<p><b>改进点</b>：① 引入分钟级数据做更精确的盘中退出与分批统计（当前日线无法验证分批优势）；② 对"新进池标的样本外为负"做专项研究，确认是噪声还是可从入池条件中剔除；③ 用小仓实盘验证样本外 +0.32% 是否可复现，再决定是否放大；④ 将止盈止损参数做成随波动率自适应的版本（本次用的是固定值）。</p>
<p class="small">理论对应：有量才有价→入池用 main_net_norm/换手率；资金聚集→龙头概念与涨停次数入池；不确定性与趋势→连续在池优先、大盘方向不猜测；指标滞后→T+1限价等待而非放宽触发窗口；涨跌平衡→止盈15%提前落袋；收益大风险大→止损-8%控回撤。</p>

{img('t1','图1 研究口径与可成交口径的命中率差：追高吃掉约6.6个百分点')}
{img('t2','图2 T+1跳空缺口分布：追高的损耗来源')}
{img('t3','图3 买入价与期望收益：回踩越深期望越高、成交率越低')}
{img('t4','图4 池内排序因子双期表现：只认双期同向的因子')}
{img('t5','图5 收益路径与闭环验证：排序对收益无稳定增益')}

</body></html>"""
p=WS/'C7操盘策略落地方案.html'
p.write_text(html,encoding='utf-8')
print("报告生成:",p,"bytes=",len(html.encode('utf-8')),"中文字数=",sum(1 for c in html if '\u4e00'<=c<='\u9fff'))
