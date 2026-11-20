# -*- coding: utf-8 -*-
import json
D=json.load(open(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace\interactive_equity_data.json",encoding="utf-8"))
for tag in ["c7","dual"]:
    nodes=D["pools"][tag]["nodes"]
    n=[x for x in nodes if x["date"]=="2024-09-13"][0]
    print("="*50,tag,"2024-09-13")
    print("持仓:")
    for h in n["holdings"]:
        print("  ",h["code"],h["name"],"is_new",h["is_new"],"held_days",h["held_days"])
    print("卖出:")
    for s in n["sells"]:
        print("  ",s["code"],s["name"],s["reason"])
    prev=[x for x in nodes if x["date"]=="2024-09-12"][0]
    print("09-12持仓:",[(h["code"],h["name"]) for h in prev["holdings"]])
