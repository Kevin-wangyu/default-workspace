import json
d = json.load(open("scan_signals_out.json", encoding="utf-8"))
s = d["B_stock_scan"]
for k, v in s.items():
    nb = len(v.get("buckets", []))
    print(k, "n_buckets=", nb, "err=", v.get("error"), "overall=", v.get("overall_hit10"))
print("--- sample close buckets ---")
print(json.dumps(s["close"].get("buckets", [])[:3], ensure_ascii=False))
