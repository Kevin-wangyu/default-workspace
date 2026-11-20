# concept_picks 停用 与 c7_pool 计算提速 —— 改动说明

日期：2026-11-20　｜　项目：`D:\Users\KFish\Desktop\Code\github-app\stockDisplay`

> 缘起：线上 serve 日志 `16:09:03 [c7_pool] 计算 1036 行耗时 44.4s（buffer 81 日）`，同时 `16:09:04/05` 仍在跑 `concept_picks` / `c7_picks` 月合并。用户要求：①取消 concept_picks 更新（概念交集已停用）；②优化 c7_pool 单日 44s 的计算。

---

## 一、结论速览

| 项 | 改动前 | 改动后 | 证据 |
| --- | --- | --- | --- |
| 概念交集选股更新 | serve 每次启动补最新日 picks + 月合并重建 | **完全停止生成**，历史 parquet 保留 | serve.py / startup/archive.py 已移除跳过；验证 5 项 PASS |
| c7_pool 单日计算（buffer 81，本机同负载 A/B） | 110.55s | **3.14s（35×）** | verify_buffer81.log，行数均 1067 |
| c7_pool 单日计算（buffer 30，本机 A/B） | 16.70s | **1.19s（14×）** | verify_perf_and_picks.log |
| 输出口径 | — | **24 字段逐字段零差异** | 目标日 3 只逐股比对 max_abs=0 |

> 注：用户日志里的 44.4s 与我本机复现的 110s 绝对值不同（机器负载 / threads / 数据已推进到 11-20 所致），但**同机同负载 A/B 的加速比 14×~35× 可信**，口径零差异。

---

## 二、改动 1：取消 concept_picks 更新

### 逐条核对：谁在更新 concept_picks

| 更新来源 | 位置 | 处理 |
| --- | --- | --- |
| ① 补最新日交集 | `serve.py` 原「补最新日期的 picks」块：`_get_tops_and_scores(d)` → `_build_intersection_picks(...)` → `_save_picks_cache(d, picks)` | **移除** |
| ② 月合并重建 | `startup/archive.py::maybe_rebuild_month_archive()` 遍历 `KINDS`（含 `concept_picks`），每月重建 compact | **加 `skip_kinds={"concept_picks"}` 跳过** |

### 前端不消费（确认零破坏）

`grep intersection_picks` 在 `frontend/**/*.js` **无任何匹配**；`concept_view1.js:594/628` 只请求 `/api/concept/date_top10`（龙头/三榜）与 `/api/concept/c7_picks`（策略池）。移除更新不影响界面。

- `queries/concept.py::get_concept_date_top10` 仍返回 `intersection_picks`（读历史缓存），前端不用即不显示——**保留该端点行为不动**，历史数据照常可读。
- 手动脚本 `scripts/precompute.py`、`recompute_picks.py`、`recompute_target.py`、`cli.py` 中的交集选股代码**保留**：它们不是 serve 运行时、不自动执行，且"禁止删除原文件"约束下不动。

### 衔接方式

- `serve.py` 顶部 import 移除 `_get_tops_and_scores / _build_intersection_picks / _save_picks_cache`（`CONCEPT_PICKS_DIR` 保留，证据见脚本零删除检查）。
- `_tops_cache` 增量补更新（`rebuild_tops_cache`）**保留**——龙头概念 score 仍依赖它，与交集选股无关。
- C6/C7 策略池更新块（serve.py:139-148）**保留不动**。

---

## 三、改动 2：c7_pool 计算提速

### 耗时定位依据（哪一步慢、慢在何处）

数据驱动的逐步定位，不靠猜：

| 实验 | 结果 | 结论 |
| --- | --- | --- |
| 分段：`base+st` 窗口特征单独跑 | **0.2s**（172590 行） | 窗口特征不是瓶颈 |
| 分段：逐 CTE count | st 0.26s / lead 0.16s / feat 0.37s / st7 0.58s / **concepts 0.21s**（count(*) 触发列裁剪，假象） | count 会裁掉昂贵列，需 SELECT * 实测 |
| 受控实验 A/B/C | 基线 13.9s；**concepts 置空 0.98s**；fwd 置 NULL 16.6s（无改善） | **唯一瓶颈 = concepts CTE** |
| EXPLAIN ANALYZE | Total Time 22.19s，HASH_GROUP_BY（DISTINCT unnest）主导 | 印证 |

**根因**：`concepts` CTE 对整个 buffer 窗口（81 日 × 全市场 ~36 万行/日）执行 `unnest(string_split(concepts,';'))` + `string_agg(DISTINCT ... ORDER BY ...)`，但结果在 `df[df.trade_date.isin(target_dates)]` 里**只留目标日 1~2 只**——其余窗口日的聚合全是白算。这解释了"仅算一日却要 44s"。

### 修复方案

`core/c7_pool_rebuild.py::_pool_sql(win_dates_sql, target_dates_sql)`：
- 新增 `target_dates_sql` 参数；`concepts` CTE 的 `WHERE IN` 从**全窗口**改为**目标日区间**。
- `rebuild_c7_pool` 构造 `target_dates_sql = earliest..latest` 交易日值列表并传入；多目标日时取区间且不遗漏中间日。
- **fwd 保持全窗口**：`RANGE BETWEEN 1 FOLLOWING AND 10 FOLLOWING` 需要未来行，裁掉会把复盘列变 null（对用户"复盘列"需求有害）——最小且安全的裁剪只碰 concepts。
- 日志补打 `concepts 裁到 N 目标日区间`，可核查。

### 提速与口径验证

| 场景 | 修复前 | 修复后 | 加速 | 口径 |
| --- | --- | --- | --- | --- |
| buffer 81（对齐线上日志） | 110.55s | 3.14s | **35×** | rows 均 1067 |
| buffer 30 | 16.70s | 1.19s | **14×** | 目标日 3 行，24 字段 max_abs=0 |
| 最小修复（只裁 concepts） | 11.22s | 1.20s | 9.4× | 文本列/数值列全一致 |

集成测试：`rebuild_c7_pool(dry_run)` 目标 0 天、0.1s；真实调用分区数 651→651（**零删除**）；`INTEGRATION_OK True`。

---

## 四、落点清单（新增/修改，全部明确）

| 落点 | 类型 | 说明 |
| --- | --- | --- |
| `serve.py` | 修改 | 移除交集选股 import + 补最新日 picks 块；保留 c7_pool 更新 |
| `startup/archive.py` | 修改 | 加 `skip_kinds={"concept_picks"}`，serve 月合并跳过交集选股 |
| `core/c7_pool_rebuild.py` | 修改 | `_pool_sql` 加 `target_dates_sql` + concepts 裁剪；`rebuild_c7_pool` 传参 + 日志 |
| `data/concept_picks/**`（历史 parquet） | **不动** | 零删除、零覆盖 |
| `data/c7_picks/**`（派生缓存分区） | 不动（本次只改计算，不重写） | 集成测试确认 651→651 |

---

## 五、验证证据

`verify_perf_and_picks.py` → **13/13 ALL PASSED**：
- py_compile 三模块全过；serve 无交集调用、保留 c7_pool 更新；archive 跳过 concept_picks；`_pool_sql` 新签名生效。
- 提速 14×、目标日行数一致、24 字段零差异。
- c7_picks 分区 651、concept_picks 历史分区 675 均保留（零删除）。

`verify_rebuild_integration.py` → dry_run 0 天 0.1s、真实调用分区 651→651、`INTEGRATION_OK True`。

`verify_buffer81.py` → buffer 81 场景 110.55s → 3.14s（35×）。

---

## 六、局限与说明

1. **绝对值差异**：本机 110s vs 线上 44s 源于负载/数据推进差异，加速比才是可信指标。
2. **buffer 仍偏大**：目标日距数据末尾较远时，`buffered` 会从 buf_start 一直取到末尾（含目标日之后所有日），导致窗口膨胀——这是上次 129s 讨论过的点，本次未再动（force_recent_days 已=0，正常增量只补最新日，窗口=71 日）。若后续需补大量历史空洞日，可考虑把 buffer 上界截到"目标日+10"（fwd 需要），但需另做口径验证。
3. **手动脚本保留**：`scripts/precompute.py` 等交集选股代码未删（非 serve 运行时 + 禁止删除原文件），如要彻底下线需用户另行确认。
4. **未重启 serve**：reload 热加载，用户刷新即可生效；如需立即验证请重启 serve 观察日志不再出现 concept_picks 更新行、c7_pool 耗时降到个位数秒。
