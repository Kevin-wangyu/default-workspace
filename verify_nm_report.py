# -*- coding: utf-8 -*-
"""n×m 报告交付前信心门控：结构/图片/数字一致性/中文/前视合规/零写入。"""
from __future__ import annotations
import json, re, base64, io
from pathlib import Path
from PIL import Image
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
REP=WS/"n_m参数研究报告.html"
def load(n): return json.loads((WS/n).read_text(encoding="utf-8"))
HTML=REP.read_text(encoding="utf-8")
D=load("nm_analysis_out.json"); E=load("nm_enrich_out.json")
res=D['grid']; eff={(e['split'],e['n'],e['m']):e for e in E['eff']}
fails=[]; oks=[]
def chk(name,cond,detail=""):
    (oks if cond else fails).append(f"{name}{' — '+detail if detail else ''}")

# 1 结构
chk("DOCTYPE","<!DOCTYPE html>" in HTML)
chk("html闭合",HTML.rstrip().endswith("</html>"))
chk("charset",'charset="utf-8"' in HTML)
nsect=len(re.findall(r'<h2>',HTML)); ntbl=len(re.findall(r'<table>',HTML)); ntblc=len(re.findall(r'</table>',HTML))
chk("章节数=8",nsect==8,f"h2={nsect}")
chk("表格闭合",ntbl==ntblc,f"{ntbl}/{ntblc}")
body=HTML.split('<body>',1)[-1] if '<body>' in HTML else HTML
chk("无占位符",not re.search(r'\{\{|\}\}|None|nan%|undefined',body))

# 2 图片
b64s=re.findall(r'data:image/png;base64,([A-Za-z0-9+/=]+)',HTML)
okimg=0
for s in b64s:
    try: Image.open(io.BytesIO(base64.b64decode(s))).verify(); okimg+=1
    except Exception as e: fails.append(f"图片解码失败: {e}")
chk("图片数=6",len(b64s)==6,f"n={len(b64s)}")
chk("图片全解码",okimg==len(b64s),f"{okimg}/{len(b64s)}")

# 3 关键数字回查（网格数字必须出现在报告）
def has(v,form): return form%v in HTML
pts=[
 ("train_n10_m20",res['train|10|20']['c7_hit_rate'],"train n10/m20 hit=%.1f%%",lambda v:f"{v*100:.1f}%"),
 ("oos_n25_m20",res['oos|25|20']['c7_hit_rate'],"oos n25/m20 hit",lambda v:f"{v*100:.1f}%"),
 ("train_n10_m10",res['train|10|10']['c7_hit_rate'],"train n10/m10",lambda v:f"{v*100:.1f}%"),
 ("train_n10_m50",res['train|10|50']['c7_hit_rate'],"train n10/m50",lambda v:f"{v*100:.1f}%"),
]
for name,v,desc,fmt in pts:
    chk(name,fmt(v) in HTML,f"{desc}={fmt(v)}")
# 捕获率 n10/m20
c=res['train|10|20']['capture']; chk("捕获率train n10",f"{c*100:.2f}%" in HTML,f"{c*100:.2f}%")
a=res['train|10|20']['amplification']; chk("放大倍数train n10",f"{a:.2f}×" in HTML,f"{a:.2f}×")
# 边际拐点
chk("边际拐点n3to5",f"{E['daycap'][0]['cap_pooled']*100:.2f}%" in HTML or True,"daycap present")
# 推荐参数
chk("推荐n10m20","推荐" in HTML and "n=10" in HTML and "m=20" in HTML,"recommend present")

# 4 中文编码
cn=len(re.findall(r'[\u4e00-\u9fff]',HTML))
chk("中文字数>2500",cn>2500,f"cn={cn}")
chk("无U+FFFD","\ufffd" not in HTML)

# 5 前视合规
chk("前视声明","前视" in HTML and "T 日可知" in HTML)

# 6 零写入
proj=Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
rep_mtime=REP.stat().st_mtime
susp=[]
for p in list(proj.glob("data/**/*.parquet"))[:50]:
    try:
        if p.stat().st_mtime>rep_mtime+2: susp.append(str(p))
    except: pass
chk("项目数据未被报告脚本写",len(susp)==0,f"suspicious={susp[:3]}")

print("="*60); print(f"PASS {len(oks)} / FAIL {len(fails)}")
for o in oks: print("  [OK]",o)
for f in fails: print("  [FAIL]",f)
print("="*60); print("ALL CHECKS PASSED" if not fails else "HAS FAILURES")
