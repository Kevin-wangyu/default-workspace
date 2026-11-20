# -*- coding: utf-8 -*-
"""T+1 两套汇报验证：结构/图片/数字一致/旧结论清除/两套独立/三要素/成本不可得。只读，不改报告。"""
from __future__ import annotations
import json, re, base64, io
from pathlib import Path
from PIL import Image

WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
S = json.loads((WS/"t1_summary.json").read_text(encoding="utf-8"))
FILES = {
    "normal": WS/"C7策略_T1修正回测汇报.html",
    "main": WS/"C7策略_T1修正回测汇报_仅主板.html",
}
def pct(x,n=2): return ("%%.%df"%n)%x+"%"
def num(x,n=4): return ("%."+str(n)+"f")%x

results=[]
def chk(cond, label, detail=""):
    results.append((bool(cond), label, detail))

for mode,f in FILES.items():
    chk(f.exists(), f"[{mode}] 报告存在", str(f))
    if not f.exists():
        continue
    html = f.read_text(encoding="utf-8")
    d = S[mode]; c7=d["C7单池"]; du=d["C6+C7双池"]

    # 1 结构
    chk(html.lstrip().lower().startswith("<!doctype html"), f"[{mode}] DOCTYPE")
    chk(html.rstrip().endswith("</html>"), f"[{mode}] html闭合")
    chk('charset="utf-8"' in html, f"[{mode}] UTF-8声明")
    n_h2 = len(re.findall(r"<h2>", html))
    chk(n_h2>=8, f"[{mode}] 章节数>=8", f"实际{n_h2}")
    chk("\ufffd" not in html, f"[{mode}] 无U+FFFD乱码")

    # 2 图片解码（9张：bt1-6 + ce1-3）
    imgs = re.findall(r"data:image/png;base64,([A-Za-z0-9+/=]+)", html)
    ok_img=0
    for b in imgs:
        try:
            im=Image.open(io.BytesIO(base64.b64decode(b))); im.verify(); ok_img+=1
        except Exception:
            pass
    chk(len(imgs)>=9 and ok_img==len(imgs), f"[{mode}] 图片全解码", f"{ok_img}/{len(imgs)}")

    # 3 关键数字与 t1_summary 一致
    for gname,g in [("C7",c7),("双池",du)]:
        chk(pct(g["avg"],4) in html, f"[{mode}] {gname}期望匹配", pct(g["avg"],4))
        chk(pct(g["win"]) in html, f"[{mode}] {gname}胜率匹配", pct(g["win"]))
        chk(num(g["pf"],3) in html, f"[{mode}] {gname}PF匹配", num(g["pf"],3))
        chk(f"{g['port']['final']:,.2f}" in html, f"[{mode}] {gname}终值匹配", f"{g['port']['final']:,.2f}")
    chk(f"{c7['sameday']}" in html and f"{du['sameday']}" in html, f"[{mode}] 当日回转=0数字")
    chk(num(du["sig"]["全区间"]["p"],4) in html, f"[{mode}] 双池全区间p值匹配", num(du["sig"]["全区间"]["p"],4))

    # 4 旧结论清除（这些是上一版建立在正期望上的断言，T+1后必须消失）
    banned=["逐项吻合","值得按双池配置落地","全部提升且方向一致","样本内显著、样本外证据不足的统计判定不变",
            "复利终值远高于不复利","C7 1450笔","均为正，方向一致"]
    for b in banned:
        chk(b not in html, f"[{mode}] 旧结论已清除: {b[:12]}")

    # 5 T+1 新主线存在
    for kw in ["T+1","当日回转","撮合","显著为负","不可得"]:
        chk(kw in html, f"[{mode}] 新主线关键词: {kw}")

    # 6 三要素可查
    for kw in ["初始资金","资金分配规则","单票仓位上限","最大同时持仓"]:
        chk(kw in html, f"[{mode}] 三要素可查: {kw}")

    # 7 无未替换占位符（剥离 base64 后检查，图片流里可能含 nan 字符）
    clean = re.sub(r"data:image/png;base64,[A-Za-z0-9+/=]+", "[IMG]", html)
    for ph in ["{suf}","{SUF}","{D0}","{D1}","None%","nan","NaN"]:
        chk(ph not in clean, f"[{mode}] 无占位符: {ph}")

# 8 两套独立性：normal 的期望串不应出现在 main 的独有数字位置（各自数字不同）
hn=FILES["normal"].read_text(encoding="utf-8")
hm=FILES["main"].read_text(encoding="utf-8")
chk(pct(S["normal"]["C7单池"]["avg"],4)=="-0.5784%", "normal C7期望核对", pct(S["normal"]["C7单池"]["avg"],4))
chk(pct(S["main"]["C7单池"]["avg"],4)=="-0.7035%", "main C7期望核对", pct(S["main"]["C7单池"]["avg"],4))
chk(pct(S["normal"]["C7单池"]["avg"],4) not in hm, "[独立性] normal期望串不在main")
chk(pct(S["main"]["C7单池"]["avg"],4) not in hn, "[独立性] main期望串不在normal")
chk("仅主板口径" in hm and "正常口径（全市场）" in hn, "[独立性] 口径标题区分")

passed=sum(1 for ok,_,_ in results if ok)
total=len(results)
print(f"VERIFY_T1_REPORT {passed}/{total}")
for ok,label,detail in results:
    if not ok:
        print(f"  FAIL: {label} {detail}")
print("ALL_OK" if passed==total else "HAS_FAILURE")
