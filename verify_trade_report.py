# -*- coding: utf-8 -*-
"""操盘策略报告交付前验证：结构/图片解码/关键数字/中文/前视合规/零写入。"""
from __future__ import annotations
import json, re, base64, io
from pathlib import Path
from PIL import Image
WS=Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
p=WS/'C7操盘策略落地方案.html'
h=p.read_text(encoding='utf-8')
checks=[]
def ck(name,cond,detail=''):
    checks.append((name,bool(cond),detail));print(('[OK] ' if cond else '[FAIL] ')+name+('  '+detail if detail else ''))

# 1 结构
ck('doctype',h.lstrip().lower().startswith('<!doctype html>'))
ck('html闭合',h.rstrip().endswith('</html>'))
ck('charset', '<meta charset="utf-8">' in h)
secs=len(re.findall(r'<h2>',h));ck('章节数>=8',secs>=8,f'h2={secs}')
ck('无占位符',not re.search(r'\{\{|\}\}|\bNone\b|TODO|待填',h[h.find('<body>'):]))
ck('div平衡',h.count('<div')==h.count('</div>'),f"{h.count('<div')}/{h.count('</div>')}")
ck('table平衡',h.count('<table')==h.count('</table>'),f"{h.count('<table')}/{h.count('</table>')}")

# 2 图片解码
imgs=re.findall(r'data:image/png;base64,([^"\' ]+)',h)
ok=0;sizes=[]
for b in imgs:
    try:
        data=base64.b64decode(b);im=Image.open(io.BytesIO(data));im.verify();ok+=1;sizes.append(im.size)
    except Exception as e:print(' img fail',e)
ck('图5张全解码',len(imgs)==5 and ok==5,f'{ok}/{len(imgs)} sizes={sizes[:2]}')

# 3 关键数字
TP=json.loads((WS/'trade_path_profile.json').read_text(encoding='utf-8'))
nums=['35.05%','28.44%','32.99%','27.15%','+2.47%','1.07%','0.32%','-1.31%','-0.94%','31.8%','29.3%','23.42%']
for n in nums:
    ck('数字 '+n, n in h)
# 前视/成本/双期声明
for kw in ['零写入','零前视','train','oos','不含未来信息','扣成本']:
    ck('口径声明 '+kw,kw in h)

# 4 中文
cn=sum(1 for c in h if '\u4e00'<=c<='\u9fff')
ck('中文字数>2500',cn>2500,f'cn={cn}')
ck('无乱码', '\ufffd' not in h)

# 5 零写入：报告脚本不含项目写操作
proj_w=['to_parquet','to_csv','_append_tops_cache','setup_logging','rebuild']
script=(WS/'make_trade_report.py').read_text(encoding='utf-8')
susp=[w for w in proj_w if w in script]
ck('报告脚本无项目写入',not susp,f'suspicious={susp}')

print('\n=== 汇总 ===')
fail=[c for c in checks if not c[1]]
print(f'{len(checks)-len(fail)}/{len(checks)} PASSED' + ('  ALL CHECKS PASSED' if not fail else f'  FAILED: {[c[0] for c in fail]}'))
