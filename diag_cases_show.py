# -*- coding: utf-8 -*-
import json
R=json.load(open(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace\diag_holding_out.json",encoding="utf-8"))
for tag,p in R["pools"].items():
    print("="*70);print(tag,p["name"])
    print("A类重复样例(同日同code):")
    for a in p["A"]["items"][:3]:
        print("  日期",a["date"],"重复",a["dup"])
        for h in a["holds"]:
            print("     idx",h["idx"],"code",h["code"],"di_buy",h["di_buy"],
                  "di_exit",h["di_exit"],"k",h["k"],"reason",h["reason"])
    print("B1当日买卖样例:")
    for b in p["B"]["B1_items"][:4]:
        print("  ",b)
    print("阳普医疗300030生命周期:",json.dumps(p["cases"]["阳普医疗_300030_2024-09-13"],ensure_ascii=False))
    print("跨境通002640生命周期:",json.dumps(p["cases"]["跨境通_002640_2024-09-13"],ensure_ascii=False))
