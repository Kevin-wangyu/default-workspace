import json
from pathlib import Path
WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
D = json.loads((WS/"report_data.json").read_text(encoding="utf-8"))
print("keys", list(D.keys()))
print("grade_summary", D["grade_summary"])
print("baseline train", D["baseline"]["train"]["10"]["merge"], "oos", D["baseline"]["oos"]["10"]["merge"])
print("monthly n", len(D["monthly_base"]))
print()
for k, v in D["recommended"].items():
    rp = v["replay"]
    print("===", k)
    print("  label:", v["label"])
    print("  all_pool:", rp["all_pool"])
    print("  restricted_pool:", rp["restricted_pool"])
    print("  daily n=", len(rp["daily"]), "first", rp["daily"][0]["date"], "last", rp["daily"][-1]["date"])
    print("  hit10_dates:")
    for r in rp["hit10_dates"]:
        print("    ", r)
    print("  hit5_dates:")
    for r in rp["hit5_dates"]:
        print("    ", r)
    print("  train/oos daily counts:",
          sum(1 for r in rp["daily"] if r["split"]=="train"),
          sum(1 for r in rp["daily"] if r["split"]=="oos"))
print()
print("=== templates_stability ===")
for s in D["templates_stability"]:
    print("  %-24s tr10=%.3f iv10=%.3f oos10=%.3f | tr5=%.3f oos5=%.3f d75=%.3f" % (
        s["name"], s["train10"], s["iv10"], s["oos10"], s["train5"], s["oos5"], s["d75"]))
print()
print("=== high_days ===")
for r in D["high_days"]:
    print("  ", r)
print()
print("=== stock_scan keys ===", list(D["stock_scan"].keys()))
sc = D["stock_scan"]
# print top12 by best lift10
items = []
for k, v in sc.items():
    if isinstance(v, dict):
        items.append((k, v.get("best_lift10", v.get("lift10", 0)), v.get("best_b", None), v.get("q10", None)))
items.sort(key=lambda x: -x[1] if x[1] else 0)
print("top by lift:")
for it in items[:14]:
    print("  ", it)
print()
print("sample stock_scan scrplus_90:", json.dumps(sc.get("scrplus_90"), ensure_ascii=False)[:600])
