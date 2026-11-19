import json
from pathlib import Path
WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")

R = json.loads((WS/"search_results.json").read_text(encoding="utf-8"))
print("TOP KEYS:", list(R.keys()))
print()
print("=== GRADES DETAIL ===")
for g, items in R["grades"].items():
    print(f"[{g}] n={len(items)}")
    for i, it in enumerate(items):
        print(f"  ({i}) {it['label']}")
        for sp in ["train", "iv", "oos"]:
            e = it[sp]
            print(f"      {sp:5s} 10d merge={e['10']['merge']} pool={e['10']['pool_n']} d75={e['10']['daily75']} hitd={e['10']['hit_days']}/{e['10']['valid_days']} | 5d merge={e['5']['merge']} d75={e['5']['daily75']}")
        print(f"      hit75_dates={it['hit75_dates']}")
print()
print("=== REFINED ORIGIN ===")
for i, rf in enumerate(R["refined"]):
    print(f"  [{i}] from={rf['origin_label'][:90]}")
    print(f"      rule={rf['report']['label']}")
    print(f"      hit75_dates={rf['report']['train_hit75_dates']}")
    print(f"      train_daily10 n_valid={len(rf['report']['train_daily10']['date'])}")
print()
print("=== MONTHLY BASE (first/last) ===")
mb = R["monthly_base"]
print("len", len(mb), "first", mb[0], "last", mb[-1])
print("max hit10", max(mb, key=lambda x: x["hit10"] if x["hit10"] else 0))
print()
print("=== SCAN2 KEYS ===")
S = json.loads((WS/"scan2_out.json").read_text(encoding="utf-8"))
print(list(S.keys()) if isinstance(S, dict) else type(S))
if isinstance(S, dict):
    for k, v in S.items():
        print(" ", k, type(v).__name__, (len(v) if hasattr(v, '__len__') else ''))
        if isinstance(v, list) and v:
            print("     sample:", json.dumps(v[0], ensure_ascii=False)[:300])
        elif isinstance(v, dict):
            print("     subkeys:", list(v.keys())[:15])
