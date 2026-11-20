# -*- coding: utf-8 -*-
"""交付前信心门控：结构/图片解码/数字一致性/中文/可复现声明。"""
from __future__ import annotations
import json, re, base64, io
from pathlib import Path
from PIL import Image

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
RP = WS/"C7策略_单池vs双池回测汇报.html"
html = RP.read_text(encoding="utf-8")
OUT = json.loads((WS/"backtest_out.json").read_text(encoding="utf-8"))
G, A = OUT["groups"], OUT["aux"]
checks=[]
def ck(name, ok, info=""):
    checks.append((name, bool(ok), info))

# 1 结构
ck("doctype", html.lstrip().lower().startswith("<!doctype html>"))
ck("html_close", html.rstrip().endswith("</html>"))
ck("charset", 'charset="utf-8"' in html)
n_h2 = html.count("<h2>")
ck("sections>=6", n_h2>=6, f"h2={n_h2}")
n_tbl = html.count("<table")
ck("tables>=4", n_tbl>=4, f"tables={n_tbl}")
# 占位符检查须先剥离base64图片数据（其中随机含XXX等子串，非真实占位符）
body_nob64 = re.sub(r"data:image/png;base64,[A-Za-z0-9+/=]+", "", html[html.find("<body"):])
ck("no_placeholder", not re.search(r"\{\{|\}\}|None|nan%|TODO|XXX|待填", body_nob64))

# 2 图片解码
imgs = re.findall(r'data:image/png;base64,([A-Za-z0-9+/=]+)', html)
ck("imgs==6", len(imgs)==6, f"n={len(imgs)}")
for i, b in enumerate(imgs):
    try:
        im=Image.open(io.BytesIO(base64.b64decode(b))); im.verify()
        ck(f"img{i+1}_decode", True, f"{im.size}")
    except Exception as e:
        ck(f"img{i+1}_decode", False, str(e))

# 3 关键数字一致性（从JSON取数，检查报告文本含该值）
def present(v, n=None):
    if v is None: return False
    s = f"%.{n}f"%v if n is not None else str(v)
    return s in html
def pcts(v,n=2): return present(v,n)
KEY = [
 ("c7_train_ret", G["C7单池"]["train"]["avg_ret"],4),
 ("c7_oos_ret", G["C7单池"]["oos"]["avg_ret"],4),
 ("dual_train_ret", G["C6+C7双池"]["train"]["avg_ret"],4),
 ("dual_oos_ret", G["C6+C7双池"]["oos"]["avg_ret"],4),
 ("c7_all_ret", G["C7单池"]["全区间"]["avg_ret"],4),
 ("dual_all_ret", G["C6+C7双池"]["全区间"]["avg_ret"],4),
 ("c7_train_wr", G["C7单池"]["train"]["win_rate"],2),
 ("c7_oos_wr", G["C7单池"]["oos"]["win_rate"],2),
 ("dual_oos_wr", G["C6+C7双池"]["oos"]["win_rate"],2),
 ("c7_train_pf", G["C7单池"]["train"]["profit_factor"],3),
 ("c7_oos_pf", G["C7单池"]["oos"]["profit_factor"],3),
 ("c7_sig", G["C7单池"]["全区间"]["n_signals"],None),
 ("dual_sig", G["C6+C7双池"]["全区间"]["n_signals"],None),
 ("c7_fill", G["C7单池"]["全区间"]["n_filled"],None),
 ("dual_fill", G["C6+C7双池"]["全区间"]["n_filled"],None),
 ("streak2_dual", A["C6+C7双池"]["streak2"]["avg_ret"],2),
]
for nm,v,n in KEY:
    ck("num_"+nm, present(v,n) if n is not None else (str(int(v)) in html), f"v={v}")

# 4 中文与合规声明
body = html[html.find("<body"):]
cjk = len(re.findall(r"[\u4e00-\u9fff]", body))
ck("chinese>=2500", cjk>=2500, f"cjk={cjk}")
ck("no_U+FFFD", "\ufffd" not in html)
ck("no_write_claim", ("不可得" in html) and ("组合层" in html))
ck("reproducible_claim", "132/132" in html and "SHA256" in html)
ck("date_range", CFG_OK := (OUT["config"]["D0"] in html and OUT["config"]["D1"] in html))

npass=sum(1 for _,ok,_ in checks if ok); ntot=len(checks)
print(f"回测报告验证: {npass}/{ntot} PASSED")
for nm,ok,info in checks:
    if not ok: print("  FAIL", nm, info)
print("VERIFY_REPORT=" + ("ALL_OK" if npass==ntot else "HAS_FAIL"))
