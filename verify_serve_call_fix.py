# -*- coding: utf-8 -*-
"""验证 serve.py 调用侧 force_recent_days=0 已生效（闭环：默认值改了，调用方不再覆盖）。"""
import sys, re, py_compile
from pathlib import Path
PROJ = Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
sys.path.insert(0, str(PROJ))
ok = True
def chk(c, m):
    global ok
    print(("OK  " if c else "FAIL") + " " + m, flush=True)
    if not c: ok = False

# 1) serve.py 源码断言：调用 rebuild_c7_pool 时 force_recent_days=0
srv = (PROJ / "serve.py").read_text(encoding="utf-8")
i = srv.find("rebuild_c7_pool(")
j = srv.find("logger.info", i)
blk = srv[i:j] if i >= 0 and j > i else ""
chk("force_recent_days=0" in blk, "serve.py 调用 rebuild_c7_pool 传 force_recent_days=0")
chk("max(10" not in blk, "serve.py 已移除 force_recent_days=max(10,...) 旧调用")

# 2) py_compile
py_compile.compile(str(PROJ / "serve.py"), doraise=True)
py_compile.compile(str(PROJ / "core" / "c7_pool_rebuild.py"), doraise=True)
py_compile.compile(str(PROJ / "core" / "tops_cache.py"), doraise=True)
chk(True, "serve.py / c7_pool_rebuild.py / tops_cache.py py_compile 全通过")

# 3) 模拟 serve 实参的 dry_run
from core.c7_pool_rebuild import rebuild_c7_pool
force_days = max(3, 5)
dry = rebuild_c7_pool(limit_days=max(30, force_days), force_recent_days=0, dry_run=True)
print("   serve 实参 dry_run=", dry, flush=True)
chk(dry.get("days", 0) <= 5, "serve 实参下增量目标日<=5（原来10天→现在1~2天）")

print("VERIFY_SERVE_CALL_FIX=" + ("ALL_OK" if ok else "HAS_FAILURE"), flush=True)
