# -*- coding: utf-8 -*-
"""导出报告内嵌图供肉眼抽检 + 项目目录零写入合规复核。"""
from __future__ import annotations
import re, base64, json
from pathlib import Path
from datetime import datetime

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
PROJ = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
t = (WS / "选股条件研究报告.html").read_text(encoding="utf-8")
imgs = re.findall(r'data:image/png;base64,([A-Za-z0-9+/=]+)', t)
for i in (0, 1, 3, 6):
    out = WS / f"chart_preview_{i+1}.png"
    out.write_bytes(base64.b64decode(imgs[i]))
    print("exported", out.name, out.stat().st_size // 1024, "KB")

print("\n=== 项目目录零写入复核（可能被写入的落盘点 mtime）===")
targets = [
    "logs/cli_audit.log", "logs/etl.log",
    "data/_tops_cache/v1/bars.parquet", "data/_tops_cache/v1/meta.parquet",
    "data/trading_calendar.parquet", "data/market_amount.parquet",
    "data/concept_meta.parquet", "data/concept_picks",
]
for rel in targets:
    p = PROJ / rel
    if p.exists():
        m = datetime.fromtimestamp(p.stat().st_mtime)
        flag = "SUSPICIOUS" if m.date() >= datetime(2026, 11, 12).date() else "untouched"
        print(f"  {rel}: mtime={m:%Y-%m-%d %H:%M:%S}  {flag}")
    else:
        print(f"  {rel}: NOT EXISTS")
print("\n=== 工作目录产物清单 ===")
for f in sorted(WS.iterdir()):
    if f.is_file():
        print(f"  {f.name}  {f.stat().st_size/1024:.0f} KB")
