# -*- coding: utf-8 -*-
"""端到端测 /api/concept/c7_picks 端点（TestClient，纯读）。"""
import sys
sys.path.insert(0, r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
for d in ["2026-05-08", "2026-10-30", "2024-09-27"]:
    r = client.get("/api/concept/c7_picks", params={"trade_date": d})
    print(f"\n=== GET /api/concept/c7_picks?trade_date={d} -> HTTP {r.status_code} ===")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("ok") is True
    data, meta = j["data"], j["meta"]
    picks = data["picks"]
    print(f"  strategy={data['strategy']} n={meta['n']} cache={meta['cache']} "
          f"future_info={meta['future_info']}")
    streak2 = [p for p in picks if p["is_streak2"]]
    print(f"  连池≥2日: {len(streak2)} 只 {[p['code'] for p in streak2][:10]}")
    if picks:
        p = picks[0]
        keys = sorted(p.keys())
        print(f"  字段({len(keys)}): {keys}")
        # 无未来信息字段校验
        assert not any("fwd" in k for k in keys), "泄漏未来字段!"
    # 降序校验
    sc = [p["c7_score"] for p in picks]
    assert sc == sorted(sc, reverse=True), "综合分非降序!"
print("\nAPI_ENDPOINT_TEST=ALL_OK")
