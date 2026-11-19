import json, io, sys

with open("search_results.json", "r", encoding="utf-8") as f:
    R = json.load(f)

out = []
def p(s=""):
    out.append(str(s))

p("=== CONFIG ===")
p(json.dumps(R["config"], ensure_ascii=False, indent=1))
p()
p("=== BASELINE ===")
p(json.dumps(R.get("baseline", {}), ensure_ascii=False, indent=1))
p()
p("=== GRADES ===")
p(json.dumps(R.get("grades", {}), ensure_ascii=False))
p()

def ev(d):
    if not d:
        return "n/a"
    r = {}
    for k in ["10", "5"]:
        e = d.get(k, {})
        r[k] = "merge=%.4f pool=%s d75=%.3f d50=%.3f hitd=%s valid=%s cov=%.3f lift=%.2f" % (
            e.get("merge", float("nan")), e.get("pool_n"), e.get("daily75", 0),
            e.get("daily50", 0), e.get("hit_days"), e.get("valid_days"),
            e.get("coverage", 0), e.get("lift", 0))
    return r

p("=== TEMPLATES (report: tr / iv / train / oos, 10d & 5d) ===")
for name, blk in R["templates"].items():
    rep = blk.get("report", {})
    p("--- %s (best=%.4f, %.1fs) ---" % (name, blk["search"]["best_score"], blk.get("seconds", 0)))
    p("  RULE: %s" % rep.get("label", ""))
    for sp in ["tr", "iv", "train", "oos"]:
        e = ev(rep.get(sp, {}))
        p("  %-6s 10d: %s" % (sp, e["10"]))
        p("  %-6s  5d: %s" % (sp, e["5"]))
    p("  hit75_dates: %s" % rep.get("train_hit75_dates", []))
    p()

p("=== REFINED / GRADED RULES ===")
# find any top-level keys that are lists of graded rules
for key in R.keys():
    if key in ("config", "templates", "baseline", "grades"):
        continue
    v = R[key]
    p("KEY %s type=%s" % (key, type(v).__name__))
    if isinstance(v, list):
        p("  len=%s" % len(v))
        for i, item in enumerate(v[:30]):
            if isinstance(item, dict):
                p("  [%d] grade=%s rule=%s" % (i, item.get("grade"), item.get("label", "")[:160]))
                rep = item.get("report", item)
                for sp in ["tr", "iv", "train", "oos"]:
                    if sp in rep:
                        e = ev(rep[sp])
                        p("       %-5s 10d %s | 5d %s" % (sp, e["10"], e["5"]))
    elif isinstance(v, dict):
        p("  subkeys=%s" % list(v.keys())[:20])
        p(json.dumps(v, ensure_ascii=False)[:2000])
    p()

with open("search_summary.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("WROTE search_summary.txt lines=", len(out))
