# concept.html 选股逻辑改造说明（概念交集选股 → C7 策略选股）

> 交付日期：2026-11-20　｜　项目：stockDisplay　｜　口径来源：C7操盘策略落地方案.html（规则1.1/5.1）、弹性n_m机制研究报告.html

---

## 一、改动点总览（7 个代码文件，零数据文件改动）

| # | 文件 | 改动性质 | 内容 |
|---|------|---------|------|
| 1 | `queries/c7_picks.py` | **新增** | C7 选股核心：从项目原始 parquet 实时重算九条件 + 综合分排序（规则1.1）+ 连续在池（规则5.1）；内存 lru_cache |
| 2 | `main.py` | 追加端点 | 新增 `GET /api/concept/c7_picks`（`:100-113`），保留原 `date_top10` 等所有端点 |
| 3 | `frontend/js/concept_view1.js` | 数据源替换 | V1 列表数据源 `data.intersection_picks` → `c7_picks` 端点；默认排序键 `importance_index` → `c7_score`；18 列 → 14 列；跳转携带 streak 参数 |
| 4 | `frontend/concept.html` | 文案 | 标题"概念交集选股 TOP40" → "C7 策略选股 · 综合分↓ · 连池标注"（`:114`） |
| 5 | `frontend/css/concept.css` | 追加覆盖 | 14 列 grid、综合分色阶、连池整行高亮/徽标/星标（文件末尾追加，不改原样式） |
| 6 | `frontend/index.html` | 追加元素 | 详情页增加 `<span id="c7DetailBadge">`（`:status` 行） |
| 7 | `frontend/js/boot.js` + `frontend/css/style.css` | 追加 | 详情页读取 `c7/streak` 参数并显示连池徽标 + 样式 |

**零数据文件改动**：未覆盖/清空/删除任何 parquet。原 `data/concept_picks/`（概念交集榜缓存，26960 行/34 文件）完整保留。

---

## 二、替换前后对照

| 维度 | 替换前（概念交集选股） | 替换后（C7 策略选股） |
|------|----------------------|----------------------|
| 选股逻辑 | 三榜（归成比/涨跌幅/涨停数）并集，按 importance_index 排 TOP40 | C7 九条件筛选，当日全部满足即入选，按 c7_score 排序 |
| 数据源 | `data/concept_picks/` 预计算 parquet | 项目原始 parquet 实时重算（`quote`/`daily_pct`/`concept_date`/`_tops_cache`） |
| 后端 | `get_concept_date_top10()` 返回 `intersection_picks` | 新增 `get_c7_picks()` → `/api/concept/c7_picks` |
| 默认排序 | importance_index（重要性指数） | c7_score（综合分，规则1.1） |
| 列数/字段 | 18 列（含 4 单 + 4 个 fwd 未来字段） | 14 列（含综合分/连池/波动/龙头）；**剔除全部 fwd_* 未来字段** |
| 特殊标注 | 无 | 连池≥2日：整行高亮 + "连N日"徽标 + 名称★（规则5.1） |
| 未来信息 | 列表曾展示 fwd_5d/10d/20d/30d | **零未来字段**（API 返回 19 字段，验证无 `fwd`） |
| 缓存 | 落盘日分区 parquet | 纯内存 lru_cache（稳定日），零落盘 |

**三榜/天梯不受影响**：`date_top10` 与 `limit_up_ladder` 端点、三榜渲染、天梯榜、牛熊状态栏等其余功能完全保留；仅 V1 结果列表换了数据源。

---

## 三、排序与标注的界面呈现

**规则1.1 排序（综合分）**
- 公式：`c7_score = z(vol20) + z(ret_5d) + z(turnover_rate)`，z 用 train 全样本基准常数固定（一次确定、不随数据漂移）；**禁用 main_net_norm 排序**（研究证明双期反向 -5.7/-23.4pct）。
- 呈现：列表默认按综合分降序，列名蓝色高亮 + "综合分"表头可点击切换升降序；前 50% 行分数橙色加粗（top-half 对应操盘策略的 top50% 优选区）。
- 其余可选排序列：代码/名称/概念数/连池/换手/波动/5日涨/涨停20/资金强度/龙头概念（点表头排序，null 排最后）。

**规则5.1 标注（连续在池）**
- 口径：`streak = 截至当日连续满足 C7 的交易日数`（按 code 分组、连续段 grp=di-rn 累计）；`streak≥2` 为连续在池。
- 列表呈现：整行橙色渐变高亮 + 左侧橙色竖条 + 连池列 "连N日" 徽标 + 名称后 ★；状态栏显示"连池≥2日 N 只 ★"。
- 详情呈现：点击代码/名称跳转个股详情时 URL 携带 `c7=1&streak=N`，详情页顶部显示"★ C7连续在池 N 日 · 优先关注"徽标。

---

## 四、缓存策略

| 日期类型 | 判定 | 缓存方式 | 失效 |
|---------|------|---------|------|
| 稳定日（距最新交易日 ≥45 交易日） | `_is_stable_date()` 用交易日序号差判定 | `@lru_cache(maxsize=64)` 内存缓存，结果 tuple | 服务重启自然失效；`clear_cache()` 可手动清 |
| 近期日（<45 交易日） | 每请求实时重算 | 不缓存 | 盘中数据更新即时可见 |

设计原则：**零落盘**（不新增/覆盖任何缓存文件，不碰原 concept_picks 数据）、历史稳定日算一次复用避免重复计算、近期日保证新鲜度。

---

## 五、无法直接替换的段及处理

| 段 | 情况 | 处理 |
|----|------|------|
| 概念交集榜 picks 数据 | `_build_intersection_picks` 生成的 `intersection_picks` 已不适合作为选股列表 | **已替换**：V1 列表改读 `/api/concept/c7_picks`；不再使用 `data.intersection_picks` 字段 |
| `get_concept_date_top10` 端点 | 该端点同时承载三榜（top_amount/top_pct/top_limit_up）与市场成交额，是三榜渲染的数据源 | **保留不删**：继续提供三榜数据；其 `intersection_picks` 字段虽仍在返回中，但前端已不再消费，零功能破坏 |
| 原 `data/concept_picks/` 缓存 | 概念交集榜历史预计算结果 | **完整保留**（禁止删除数据）：不清理、不覆盖；与新 C7 内存缓存互不干扰 |
| 缓存失效联动 | 新 C7 从原始 parquet 实时算，无独立缓存文件需同步 | 无需联动；serve 后台数据更新后，近期日自动读新数据，稳定日因历史不再变动而安全 |

---

## 六、验证证据（全部实测通过）

| 验证项 | 方法 | 结果 |
|--------|------|------|
| Python 语法 | `py_compile c7_picks.py main.py` | EXIT=0 |
| API 端点 | TestClient 请求 3 日期（2026-05-08 / 2026-10-30 / 2024-09-27） | HTTP 200；19 字段；无 fwd；综合分降序；连池数 7/0/1 与研究 verify_streak 完全一致 |
| 前端 JS 语法 | `node --check concept_view1.js boot.js` | EXIT=0 / EXIT=0 |
| 数据完整性 | 只读 count 7 个关键数据集 + mtime | quote 3,618,901 / daily_pct 3,613,661 / concept_date 3,478,456 / tops_bars 20,220 / tops_meta 18,665 / concept_picks 26,960 行，文件齐全 |
| 改造标记 | 7 个前端/后端文件关键标记检查 | 全部 OK |
| 综合结论 | — | **INTEGRITY_CHECK=ALL_OK / API_ENDPOINT_TEST=ALL_OK** |

> 说明：serve 后台进程仍在运行（reload 开发模式会热加载 main.py）。本次未重启服务，避免触发任何 rebuild/ETL；端点逻辑已用 TestClient 独立验证。
