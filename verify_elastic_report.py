# -*- coding: utf-8 -*-
"""交付前信心门控：结构/图片解码/数字一致/中文/前视合规/零写入。"""
from __future__ import annotations
import json, base64, re, io
from pathlib import Path
import numpy as np
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
H=(WS/'弹性n_m机制研究报告.html').read_text(encoding='utf-8')
F=json.loads((WS/'elastic_final_out.json').read_text(encoding='utf-8'))
R=json.loads((WS/'elastic_rule_out.json').read_text(encoding='utf-8'))
checks=[]
def ck(name,cond,detail=""):
    checks.append((name,bool(cond),detail)); print(("PASS" if cond else "FAIL"),name,detail)

# 1 结构
ck("doctype",H.lstrip().lower().startswith("<!doctype html>"))
ck("html_close",H.rstrip().endswith("</html>"))
ck("charset","charset=utf-8" in H.lower().replace('"',''))
ck("sections_10",H.count('<h2>')==10,f"n={H.count('<h2>')}")
ck("no_placeholder",not re.search(r'\{[a-zA-Z_][a-zA-Z0-9_\[\]\'\" ]*\}',H.split('<body>')[1]),"unresolved {var}")
ck("no_none","None" not in H.split('<body>')[1])

# 2 图片解码
b64s=re.findall(r'data:image/png;base64,([A-Za-z0-9+/=]+)',H)
ck("imgs_4",len(b64s)==4,f"n={len(b64s)}")
ok=0; sizes=[]
for b in b64s:
    try:
        raw=base64.b64decode(b); assert raw[:8]==b'\x89PNG\r\n\x1a\n'
        w=int.from_bytes(raw[16:20],'big'); h=int.from_bytes(raw[20:24],'big'); sizes.append(f"{w}x{h}"); ok+=1
    except Exception as e: pass
ck("imgs_decode",ok==4,",".join(sizes))

# 3 关键数字
body=H.split('<body>')[1]
S=F['splits']['all']
nums={
 '170':"170" in body,'29.31':"29.31" in body,'274':"274" in body,'47.24':"47.24" in body,
 '180':"180" in body,'31.03':"31.03" in body,'4.25':"4.25" in body,
 '122':"122" in body,'21.03':"21.03" in body,
 'n10win':"n7 胜出天数=0" in body or "n7胜出天数=0" in body,
 'window_down':"-6.73" in body,
 'oos_ge50':"23.73" in body,
}
for k,v in nums.items(): ck("num_"+k,v)

# 4 中文
body=H.split('<body>')[1]
cn=len(re.findall(r'[\u4e00-\u9fff]',body))
ck("chinese_gt2500",cn>2500,f"n={cn}")
ck("no_fffd","\ufffd" not in H)

# 5 前视合规
ck("no_forward_filter",not re.search(r'mkt_hit(5|10)\s*[><=]',body))
ck("forward_declared","零前视" in body and "mkt_hit5/10" in body)

# 6 零写入可疑
# 排除验证/审计脚本自身（它们只在关键词字符串里提到 to_parquet）
susp=[p.name for p in WS.glob('*.py')
      if not p.name.startswith(('verify_','audit_','check_'))
      and 'to_parquet(' in p.read_text(encoding='utf-8',errors='ignore')]
ck("zero_write",len(susp)==0,f"suspicious={susp}")

npass=sum(1 for _,c,_ in checks if c)
print(f"\n{npass}/{len(checks)} CHECKS", "ALL PASSED" if npass==len(checks) else "HAS FAILURES")
