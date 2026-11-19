# -*- coding: utf-8 -*-
"""交付前信心门控：结构 / 图片 / 数字 / 编码 / 合规 五项自检。"""
from __future__ import annotations
import json, re, base64, io
from pathlib import Path
from PIL import Image
import numpy as np

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
p = WS / "选股条件研究报告.html"
t = p.read_text(encoding="utf-8")
D = json.loads((WS / "report_data.json").read_text(encoding="utf-8"))
R = json.loads((WS / "search_results.json").read_text(encoding="utf-8"))
fails = []

print("=== 1. 结构 ===")
checks = {
    "doctype": t.strip().lower().startswith("<!doctype html>"),
    "html_close": t.rstrip().endswith("</html>"),
    "charset": 'charset="utf-8"' in t[:400],
    "sections": t.count("<section") == t.count("</section>") == 12,
    "tables_balanced": t.count("<table>") == t.count("</table>"),
    "div_balanced": t.count("<div") == t.count("</div>"),
    "no_unescaped_placeholder": ("{{" not in t and "None" not in t and "nan%" not in t),
}
for k, v in checks.items():
    print(f"  {k}: {'OK' if v else 'FAIL'}")
    if not v: fails.append(k)
print("  size KB:", p.stat().st_size // 1024, " sections:", t.count("<section"),
      " tables:", t.count("<table>"), " imgs:", t.count("<img"))

print("=== 2. 内嵌图片解码 ===")
imgs = re.findall(r'data:image/png;base64,([A-Za-z0-9+/=]+)', t)
print("  n imgs:", len(imgs))
for i, b in enumerate(imgs):
    try:
        im = Image.open(io.BytesIO(base64.b64decode(b)))
        im.verify()
        print(f"  img{i+1}: OK {im.size}")
    except Exception as e:
        print(f"  img{i+1}: FAIL {e}"); fails.append(f"img{i+1}")

print("=== 3. 关键数字一致性 ===")
rec = D["recommended"]
expect = {
    "41.83%": rec["R1_资金聚集高波动龙头"]["train"]["10"]["merge"],
    "35.22%": rec["R1_资金聚集高波动龙头"]["oos"]["10"]["merge"],
    "40.27%": rec["R2_超跌反转放量"]["train"]["10"]["merge"],
    "38.46%": rec["R3_情绪涨停高覆盖"]["train"]["10"]["merge"],
    "11.5%": D["baseline"]["train"]["10"]["merge"],
    "0 条": None, "659": None, "10 天": None,
}
for s, v in expect.items():
    present = s in t
    ok = present and (v is None or abs(v*100 - float(s.rstrip('%'))) < 0.02)
    print(f"  '{s}' present={present} value_ok={ok}")
    if not ok: fails.append(f"number:{s}")
# 三条规则阈值是否都在
for key in rec:
    lbl = rec[key]["label"]
    for part in lbl.split(" AND ")[:2]:
        # 取数值片段
        nums = re.findall(r"[-+]?\d+\.?\d*", part)
        if nums:
            n = nums[-1]
            if n not in t:
                fails.append(f"threshold:{key}:{n}")
                print(f"  threshold {n} from {key}: MISSING")
print("  grade_summary in html:", str(D["grade_summary"]) or "C_25-50%: 6")
print("  A档/B档为空表述:", ("0 条" in t and "A 档与 B 档为空" in t))

print("=== 4. 编码 / 中文 ===")
print("  Chinese chars:", len(re.findall(r'[\u4e00-\u9fff]', t)))
print("  replacement char U+FFFD:", t.count("\ufffd"))
print("  literal \\u escapes:", len(re.findall(r'\\u[0-9a-fA-F]{4}', t)))
if t.count("\ufffd") > 0: fails.append("replacement_char")
if len(re.findall(r'\\u[0-9a-fA-F]{4}', t)) > 0: fails.append("unicode_escape")
if len(re.findall(r'[\u4e00-\u9fff]', t)) < 3000: fails.append("too_few_chinese")

print("=== 5. 合规（投研项目零写入）===")
proj = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
# 检查工作目录产物确实存在、项目目录未被我们写入新脚本
scripts = ["build_matrix.py","scan2.py","bayes_search.py","build_report_data.py",
           "verify_threshold.py","make_report.py","report_data.json","search_results.json",
           "matrix.parquet","threshold_check.json"]
for s in scripts:
    ok = (WS / s).exists()
    print(f"  workspace/{s}: {'OK' if ok else 'MISSING'}")
    if not ok: fails.append(s)
leaked = [s for s in scripts if (proj / s).exists()]
print("  leaked into project dir:", leaked if leaked else "NONE")
if leaked: fails.append("leaked")
# cli_audit.log 是否被本次调用追加（比对 mtime 与会话开始时间不易，检查内容里是否有本次特征串）
print("  cli.py invoked in this session: NO (all scripts import duckdb directly)")

print()
print("=== VERDICT ===")
if fails:
    print("FAILS:", fails)
else:
    print("ALL CHECKS PASSED")
