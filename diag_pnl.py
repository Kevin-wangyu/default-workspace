# -*- coding: utf-8 -*-
import json
D=json.load(open(r"D:\Users\KFish\Documents\deepseek-harness\default-workspace\interactive_equity_data.json",encoding="utf-8"))
bad_mv=0; bad_pnl=0; ex=[]
for n in D["pools"]["dual"]["nodes"]:
    for h in n["holdings"]:
        d1=abs(h["market_value"]-h["cost"]*(1+h["pnl_pct"]/100))
        d2=abs(h["pnl_amount"]-(h["market_value"]-h["cost"]))
        if d1>0.5:
            bad_mv+=1
            if len(ex)<5: ex.append(("MV",h["cost"],h["market_value"],h["pnl_amount"],h["pnl_pct"],round(d1,3),round(d2,3)))
        if d2>0.5: bad_pnl+=1
print("bad_mv",bad_mv,"bad_pnl",bad_pnl)
for e in ex: print(e)
