import json
from pathlib import Path
WS = Path(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace")
S = json.loads((WS/"scan2_out.json").read_text(encoding="utf-8"))
for k in ["scrplus_90", "vol20", "turnover_rate", "lu_cnt_20d", "is_limit_up"]:
    v = S["stock_scan"][k]
    print("==", k, "keys:", list(v.keys()))
    for kk, vv in v.items():
        if kk != "buckets":
            print("   ", kk, "=", vv)
    print("   buckets n=", len(v["buckets"]), "first=", v["buckets"][0], "last=", v["buckets"][-1])
print()
print("scan_train_base:", S["train_base"])
print()
print("high_days keys:", list(S["high_days"].keys()), "n=", len(S["high_days"]["rows"]))
