import pyarrow.parquet as pq
from pathlib import Path
PROJ=Path(r"D:\Users\KFish\Desktop\Code\github-app\stockDisplay")
# 项目原生 concept_picks 的 matched_concepts 类型
for base in [PROJ/"data"/"concept_picks", PROJ/"data_compact"/"concept_picks"]:
    if base.exists():
        fs=list(base.glob("trade_date=*/part.parquet")) or list(base.glob("*.parquet"))
        if fs:
            sch=pq.read_schema(fs[0])
            print("concept_picks", base.name, "matched_concepts=", str(sch.field("matched_concepts").type) if "matched_concepts" in sch.names else "MISSING")
# c7_picks 空分区的列
c7=PROJ/"data"/"c7_picks"
emp=[p for p in c7.glob("trade_date=*/part.parquet") if "matched_concepts" not in pq.read_schema(p).names]
print("EMPTY_PARTITIONS=", [p.parent.name for p in emp], "cols=", pq.read_schema(emp[0]).names if emp else [])
