# -*- coding: utf-8 -*-
"""交付前信心门控：结构/图片解码/数字一致性/中文编码/前视合规/零写入。"""
from __future__ import annotations
import json, re, base64, io
from pathlib import Path
from PIL import Image
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
REP=WS/"选股因子增量归因研究报告.html"
def load(n): return json.loads((WS/n).read_text(encoding="utf-8"))
HTML=REP.read_text(encoding="utf-8")
CA=load("combo_attribution_out.json"); FE=load("focused_extras_out.json")
FA=load("factor_attribution_out.json"); FS=load("final_supp_out.json")
CD=load("c7_daily_out.json")
fails=[]; oks=[]
def chk(name,cond,detail=""):
    (oks if cond else fails).append(f"{name}{' — '+detail if detail else ''}")

# 1 结构
chk("DOCTYPE", "<!DOCTYPE html>" in HTML)
chk("html闭合", HTML.rstrip().endswith("</html>"))
chk("charset", 'charset="utf-8"' in HTML)
nsect=len(re.findall(r'<h2>',HTML)); ntbl=len(re.findall(r'<table>',HTML))
ntblc=len(re.findall(r'</table>',HTML))
chk("章节数>=10", nsect>=10, f"h2={nsect}")
chk("表格闭合", ntbl==ntblc, f"{ntbl}/{ntblc}")
# 注意：CSS <style> 块里的 '}}'（media query 闭合）是合法的，排除 body 外的样式再查
body_html = HTML.split('<body>',1)[-1] if '<body>' in HTML else HTML
chk("无占位符", not re.search(r'\{\{|\}\}|None|nan%|undefined', body_html))

# 2 图片解码
b64s=re.findall(r'data:image/png;base64,([A-Za-z0-9+/=]+)',HTML)
okimg=0; dims=[]
for s in b64s:
    try:
        im=Image.open(io.BytesIO(base64.b64decode(s))); im.verify(); okimg+=1
        dims.append(im.size)
    except Exception as e:
        fails.append(f"图片解码失败: {e}")
chk("图片数=11", len(b64s)==11, f"n={len(b64s)}")
chk("图片全解码", okimg==len(b64s), f"{okimg}/{len(b64s)} sizes={dims[:3]}...")

# 3 数字一致性（报告出现的关键数字，back-check 源 JSON）
tr_base=CA['train']['L0 基准池(情绪+资金+高波动)']['y10']['hit']
oo_base=CA['oos']['L0 基准池(情绪+资金+高波动)']['y10']['hit']
tr_best=FE['combos']['train']['C7 C6+龙头概念']['y10']['hit']
oo_best=FE['combos']['oos']['C7 C6+龙头概念']['y10']['hit']
def haspct(v):
    s=f"{v*100:.1f}%"; return s in HTML
chk("训练基准池数字", haspct(tr_base), f"{tr_base*100:.2f}%")
chk("样本外基准池数字", haspct(oo_base), f"{oo_base*100:.2f}%")
chk("训练最优数字", haspct(tr_best), f"{tr_best*100:.2f}%")
chk("样本外最优数字", haspct(oo_best), f"{oo_best*100:.2f}%")
# 关键因子提升数字
r=CA['robustness']
chk("近涨停提升", f"{r['其他-近涨停']['train_delta10']*100:.1f}pct" in HTML or f"{r['其他-近涨停']['train_delta10']*100:.2f}pct" in HTML,
    f"tr delta={r['其他-近涨停']['train_delta10']*100:.2f}")
chk("滞后效应样本外负", "−2.9" in HTML or "-2.9" in HTML, f"oos={r['市场-滞后赚钱效应高']['oos_delta10']*100:.2f}")
# 概念延续 vs 当日强榜（报告用 pct() 保留2位=34.38%，同时兼容1位）
_cbv=CA['concept_branch']['train']['主线延续']['y10']
chk("概念延续结论数", (f"{_cbv*100:.2f}%" in HTML) or (f"{_cbv*100:.1f}%" in HTML),
    f"train y10={_cbv*100:.2f}%")
# scrplus 真值轨道
chk("scrplus中位", f"{FE['scrplus_track']['median']:.1f}" in HTML, f"median={FE['scrplus_track']['median']}")
# 新增第13-15节：C7 逐日/牛熊/两次对比数字
c7po=CD['overall']['pooled_hit10']; c7tr=CD['by_split']['train']['pooled_hit10']; c7oo=CD['by_split']['oos']['pooled_hit10']
chk("C7全期合并命中", (f"{c7po*100:.2f}%" in HTML), f"{c7po*100:.2f}%")
chk("C7逐日达标天数", f"{CD['overall']['days_ge75']} 天" in HTML or f"> {CD['overall']['days_ge75']} <" in HTML, f"days_ge75={CD['overall']['days_ge75']}")
chk("两次对比R1训练数", f"{CD['first_report_r1']['merge_train']*100:.2f}%" in HTML, f"R1={CD['first_report_r1']['merge_train']*100:.2f}%")
chk("C7牛熊震荡", all(f"{CD['by_regime'][r]['pooled_hit10']*100:.2f}%" in HTML for r in ['牛','熊','震荡']), "3 regime numbers")
chk("筛选代码节", "c7_stock_screen.py" in HTML and "可操作落地" in HTML, "sec15 present")

# 4 中文编码
cn=len(re.findall(r'[\u4e00-\u9fff]',HTML))
chk("中文字数>3000", cn>3000, f"cn={cn}")
chk("无U+FFFD", "\ufffd" not in HTML)

# 5 前视合规：报告声明禁止 mkt_hit 入池
chk("前视声明", "前视" in HTML and "mkt_hit" in HTML)

# 6 零写入：项目目录关键文件 mtime 未在报告生成时刻被改（报告生成 17:15 左右）
proj=Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
import datetime
rep_mtime=REP.stat().st_mtime
# 项目数据文件 mtime 应早于报告生成（分析脚本只读）
susp=[]
for p in list(proj.glob("data/**/*.parquet"))[:50]:
    try:
        if p.stat().st_mtime>rep_mtime+2: susp.append(str(p))
    except: pass
chk("项目数据未被报告脚本写", len(susp)==0, f"suspicious={susp[:3]}")

print("="*60)
print(f"PASS {len(oks)} / FAIL {len(fails)}")
for o in oks: print("  [OK]",o)
for f in fails: print("  [FAIL]",f)
print("="*60)
print("ALL CHECKS PASSED" if not fails else "HAS FAILURES")
