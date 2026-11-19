# -*- coding: utf-8 -*-
"""零写入合规取证 + 图像像素级质量抽检（替代肉眼，因本模型无图像输入）。"""
from __future__ import annotations
import re, base64, io, json
from pathlib import Path
from datetime import datetime
from collections import Counter
from PIL import Image

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
PROJ = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")

print("=== A. 图像像素级质量抽检（7张内嵌图）===")
t = (WS / "选股条件研究报告.html").read_text(encoding="utf-8")
imgs = re.findall(r'data:image/png;base64,([A-Za-z0-9+/=]+)', t)
for i, b in enumerate(imgs):
    im = Image.open(io.BytesIO(base64.b64decode(b))).convert("RGB")
    a = __import__("numpy").asarray(im)
    # 非近白像素占比（内容密度）
    nonwhite = float((a.min(axis=2) < 245).mean())
    # 颜色丰富度（量化到 32 级后的独立色数）
    q = (a // 32 * 32).reshape(-1, 3)
    ncolors = len({tuple(x) for x in q[::137]})
    # 深色文字/线条像素占比（字形渲染佐证）
    dark = float((a.max(axis=2) < 110).mean())
    # 横向色带数量（是否有分面/多子图结构：按行统计非白方差突变）
    row_nw = (a.min(axis=2) < 245).mean(axis=1)
    bands = int(((row_nw[1:] - row_nw[:-1]) > 0.10).sum())
    ok = (im.size[0] >= 1200 and im.size[1] >= 560 and nonwhite > 0.05
          and ncolors > 25 and dark > 0.002)
    print(f"  chart{i+1}: {im.size[0]}x{im.size[1]} nonwhite={nonwhite:.3f} "
          f"colors={ncolors} dark={dark:.4f} bands={bands} -> {'OK' if ok else 'CHECK'}")

print("\n=== B. 我方脚本写操作全文审计 ===")
writes = []
for f in sorted(WS.glob("*.py")):
    s = f.read_text(encoding="utf-8", errors="replace")
    hits = [kw for kw in ["to_parquet", "to_csv", ".write_text", ".write_bytes",
                          "open(", "subprocess", "os.system", "rebuild",
                          "_append_tops_cache", "setup_logging", "mkdir("]
            if kw in s]
    # 只关心会写「项目目录」的：排除写工作目录的产物
    proj_ref = "stockDisplay" in s or "PROJ" in s or "PROJ_DIR" in s
    print(f"  {f.name}: keywords={hits} proj_path_ref={proj_ref}")
    if "to_parquet" in s:
        for ln, line in enumerate(s.splitlines(), 1):
            if "to_parquet" in line:
                writes.append((f.name, ln, line.strip()))
print("  --- to_parquet 落点逐行 ---")
for w in writes:
    print(f"   {w[0]}:{w[1]}  {w[2]}")

print("\n=== C. 项目侧可疑文件精确取证 ===")
sus = ["logs/etl.log", "data/_tops_cache/v1/bars.parquet",
       "data/_tops_cache/v1/meta.parquet", "data/market_amount.parquet",
       "data/concept_picks"]
for rel in sus:
    p = PROJ / rel
    if p.is_dir():
        fs = sorted(p.glob("**/*"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]
        print(f"  [DIR] {rel}")
        for x in fs:
            m = datetime.fromtimestamp(x.stat().st_mtime)
            print(f"     {x.name}  {m:%Y-%m-%d %H:%M:%S}  {x.stat().st_size} B")
    elif p.exists():
        m = datetime.fromtimestamp(p.stat().st_mtime)
        print(f"  {rel}  {m:%Y-%m-%d %H:%M:%S}  {p.stat().st_size} B")
        if rel.endswith(".log"):
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            print("     --- tail 12 ---")
            for ln in lines[-12:]:
                print("     ", ln[:180])
print("\n=== D. etl.log 中 16:00–16:20 的记录 ===")
p = PROJ / "logs/etl.log"
if p.exists():
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if re.search(r"2026-11-12 16:(0|1)\d", ln):
            print("  ", ln[:200])
