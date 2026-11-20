# -*- coding: utf-8 -*-
"""验证龙头 hover 浮层改造：
1) JS 语法（node --check）
2) HTML 结构：leaderBox/leaderBtn/leaderPop/leaderCount 存在；#status 仍在
3) JS 不再把龙头写进 #status（setStatus 调用不含"龙头"），改为调用 v1RenderLeaderPop
4) v1RenderLeaderPop 用 DOM 安全渲染、按 score 降序、含 name+score
5) CSS 有 :hover 显示浮层 + z-index 高于 toolbar
6) 后端接口未改（leader_concepts 数据源仍来自 queries/concept.py）
"""
import re, subprocess
from pathlib import Path
PROJ = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
FE = PROJ / "frontend"
ok = True
def chk(c, m):
    global ok
    print(("OK  " if c else "FAIL") + " " + m, flush=True)
    if not c: ok = False

# 1) JS 语法
node = r"C:\Program Files\nodejs\node.exe"
if not Path(node).exists():
    node = "node"
r = subprocess.run([node, "--check", str(FE / "js" / "concept_view1.js")],
                   capture_output=True, text=True)
chk(r.returncode == 0, "concept_view1.js node --check (rc=%d %s)" % (r.returncode, r.stderr.strip()[:120]))

# 2) HTML 结构
html = (FE / "concept.html").read_text(encoding="utf-8")
for ident in ["leaderBox", "leaderBtn", "leaderPop", "leaderCount", "status"]:
    chk('id="%s"' % ident in html, "concept.html 含 #" + ident)
chk('class="leader-box"' in html and 'class="leader-pop"' in html, "龙头按钮框+浮层容器结构在")

# 3) JS：龙头不再进 #status，改为渲染浮层
js = (FE / "js" / "concept_view1.js").read_text(encoding="utf-8")
chk("function v1RenderLeaderPop" in js, "定义 v1RenderLeaderPop")
chk("v1RenderLeaderPop(leaders)" in js and "v1RenderLeaderPop([])" in js, "成功/异常路径均调用浮层渲染")
# setStatus 那段调用不含"龙头"
m = re.search(r"setStatus\(`天梯.*?`\s*\n\s*\+?\s*`?\(C7", js, re.S)
seg = js[js.find("setStatus(`天梯"):js.find("setStatus(`天梯")+120]
chk("龙头" not in seg, "#status 文案已移除龙头")
chk("'龙头：'" not in js and '"龙头："' not in js, "代码里已无旧的 '龙头：' 状态文案")

# 4) 浮层渲染细节：DOM 安全 + 降序 + name/score
fn = js[js.find("function v1RenderLeaderPop"):js.find("function v1RenderLeaderPop")+1400]
chk("replaceChildren" in fn and "createElement" in fn, "用 DOM API 渲染（非 innerHTML 拼字符串，防注入）")
chk("sort((a, b)" in fn and "-x[\"score\"]" not in fn and "Number(b.score)" in fn, "按 score 降序排序")
chk("leader-pop-name" in fn and "leader-pop-score" in fn, "每项含概念名 + score")
chk("toFixed(4)" in fn, "score 保留4位小数")
chk("sort" in fn, "前端再排序兜底（后端已降序）")

# 5) CSS hover + z-index
css = (FE / "css" / "concept.css").read_text(encoding="utf-8")
chk(".leader-box:hover .leader-pop" in css and "display: block" in css, "CSS hover 显示浮层")
chk("z-index: 400" in css, "浮层 z-index 高于 toolbar(200)")
chk("leader-pop-item" in css and "leader-pop-score" in css, "浮层条目样式齐")

# 6) 后端未改：数据源仍来自 concept.py 的 leader_concepts
qsrc = (PROJ / "queries" / "concept.py").read_text(encoding="utf-8")
chk('"leader_concepts": leader_concepts' in qsrc and "score>=0.8" in qsrc, "后端 leader_concepts 数据源原样（score>=0.8 降序）")

print("VERIFY_LEADER_HOVER=" + ("ALL_OK" if ok else "HAS_FAILURE"), flush=True)
