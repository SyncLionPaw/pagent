# JobBench 评测报告 — deepseek-v4-flash 两 harness × 两 split 横向对比

生成时间：2026-08-13
被评模型：`deepseek-v4-flash`（同一选手模型贯穿全部四组）
数据来源：`dataset/{easy,main}/*/task*/eval_result/eval_{harness}/deepseek-v4-pro_judge.json`

本报告覆盖四个组合（两 harness × 两 split 的笛卡尔积）：

| harness | 说明 | eval_result 目录名 |
|---|---|---|
| **OpenCode** | 官方同款 harness，headless `run` 子命令，本地源码 `job-bench-eval/opencode/` | `eval_deepseek-v4-flash` |
| **pagentv4** | 本仓库 inplace 模式，`CodeRunner + InplaceBackend`，入口 `src/pagentv4/adapters/jobbench_runner.py` | `eval_pagentv4-deepseek-v4-flash` |

两 harness 用**同一选手模型（deepseek-v4-flash）、同一裁判（deepseek-v4-pro，temperature=0）**，只差 harness 与 split 两个变量，因此可以直接横向对比。

## 与官方 leaderboard 的口径差异

官方 leaderboard（<https://job-bench.github.io/#leaderboard>）跑在 OpenCode 上，裁判用 **Grok 4.3**。本报告裁判用 **deepseek-v4-pro**（与选手同厂，评分偏松）。因此本报告全部分数**只作内部参考，不能与官方榜直接横比**。多语言对比图见 `jobbench_leaderboard_{en,zh,ja}.png`，图中本仓库两条 bar 用暖色和 `*` 标注了这一差异。

---

## 一、四组合总览

| 组合 | 题数 | macro（%）| micro（%）| 中位 | 标准差 | 最高 | ≥0.8 | <0.5 | 零分 |
|---|---|---|---|---|---|---|---|---|---|
| easy / OpenCode | 63 | 73.1 | 75.5 | 0.781 | 0.217 | 1.00 | 26 | 9 | 0 |
| easy / pagentv4 | 63 | **76.8** | **80.0** | **0.816** | 0.218 | 1.00 | **34** | 8 | 0 |
| main / OpenCode | 65 | 37.6 | 36.6 | 0.368 | 0.200 | 0.86 | 1 | 47 | 2 |
| main / pagentv4 | 65 | **39.9** | **38.2** | **0.405** | 0.240 | **1.00** | **5** | 43 | 2 |

- **micro**：所有 rubric 权重之和加权（总分 / 满分）。
- **macro**：按任务等权平均 normalized_score。
- 说明：micro 的分母（满分）按各组合自己判分产出的 rubric 计，两 harness 个别任务的满分不完全相等（判分时偶发极少数 criterion 未解析），所以 micro 用各自分母、macro 用逐任务归一，二者交叉印证。

### 两句话结论

1. **split 决定难度量级**：Easy → Main，同一模型同一裁判掉约 37 分（macro 73→38），近四分之三 Main 任务在及格线以下。同职业在 Main 上普遍腰斩，瓶颈来自任务的专业深度。
2. **同 split 下 pagentv4 略优于 OpenCode**：Easy 上 pagentv4 macro 高 3.7 分、micro 高 4.5 分；Main 上 pagentv4 macro 高 2.3 分、micro 高 1.6 分，且 Main 上 pagentv4 有 5 个任务≥0.8（含 1 个满分）而 OpenCode 只有 1 个。

---

## 二、Main split 榜单定位（leaderboard 只看 Main）

官方榜单只统计 Main split。把本仓库两条 harness 插进官方 Main 榜（裁判口径不同，仅示意）：

- **pagentv4 = 38.2**，落在 GPT-5.5（38.3）与 Claude Sonnet 4.6（36.6）之间。
- **OpenCode = 36.6**，与 Claude Sonnet 4.6 并列。

多语言对比图：

- 英文：`jobbench_leaderboard_en.png`
- 中文：`jobbench_leaderboard_zh.png`
- 日文：`jobbench_leaderboard_ja.png`

三张图数据同源，来自 `jobbench_scores.json` 的 `main/OpenCode` 与 `main/pagentv4` 的 micro 分，由 `plot_jobbench_leaderboard.py` 生成。

---

## 三、harness 横向对比（同题逐一 diff）

同一 split 内两 harness 跑的是同一批任务，可逐题比 normalized_score。

| split | 同题数 | pagentv4 胜 | OpenCode 胜 | 平 |
|---|---|---|---|---|
| easy | 63 | **34** | 14 | 15 |
| main | 65 | **28** | 25 | 12 |

Easy 上 pagentv4 优势明显（34 胜 14）；Main 上两者接近（28 胜 25），说明难题上 harness 差异被模型能力上限压缩。

### Main 上 pagentv4 领先最多的任务

| Δ(pg−oc) | OpenCode | pagentv4 | 职业 / 任务 |
|---|---|---|---|
| +0.47 | 0.16 | 0.62 | human_resources_specialists/task1 |
| +0.43 | 0.40 | 0.83 | technical_writers/task3 |
| +0.42 | 0.48 | 0.91 | technical_writers/task1 |
| +0.27 | 0.45 | 0.73 | statisticians/task2 |
| +0.27 | 0.35 | 0.62 | medical_and_health_services_managers/task1 |

### Main 上 OpenCode 领先最多的任务

| Δ(pg−oc) | OpenCode | pagentv4 | 职业 / 任务 |
|---|---|---|---|
| −0.34 | 0.86 | 0.52 | mechanical_engineering_technicians/task3 |
| −0.24 | 0.32 | 0.09 | sociology_teachers_postsecondary/task1 |
| −0.18 | 0.37 | 0.18 | civil_engineers/task3 |
| −0.18 | 0.25 | 0.07 | bookkeeping_accounting_and_auditing_clerks/task1 |
| −0.18 | 0.61 | 0.42 | financial_managers_branch_or_department/task2 |

pagentv4 在**长文书/技术写作/多源整合**类任务上更稳（technical_writers、HR、卫生管理）；OpenCode 在**工程计算/结构化台账**个别任务上更强（机械技师 task3 拿到全场次高 0.86）。

---

## 四、运行过程（跑了几次）

### 选手阶段（deepseek-v4-flash 产出交付物）

| 组合 | 并发 | 结果 |
|---|---|---|
| easy / OpenCode | 逐步 1→2 | 63/63 success。并发 3 曾因多进程冷启动争抢 models.dev 目录 fetch（硬编码 10s 超时）失败并 kill，补 `OPENCODE_DISABLE_MODELS_FETCH=1` 后并发 2 跑完 |
| main / OpenCode | 8 | 65/65 一次成功，0 失败 0 超时，仅 2 次偶发 429 被 SDK 重试吸收 |
| easy / pagentv4 | 16 | 63/63 success。inplace 模式在 `/tmp` 隔离 workspace 内运行 |
| main / pagentv4 | 16 | 65/65 success。高并发下靠 `--api-max-retries=6` 吸收 429 |

- OpenCode 关键修复：启动带 `OPENCODE_DISABLE_MODELS_FETCH=1`（opencode.json 已完整声明 deepseek provider，跳过目录抓取无副作用）。
- pagentv4 关键改动：`Provider` 增加 `max_retries` 透传给 AsyncOpenAI，高并发下把 SDK 默认重试 2 提到 6，吸收共享端点的 429。

### 裁判阶段（deepseek-v4-pro 打分）

- 四组合统一用 `run_judge.sh` 断点续跑（已评 SKIP，只补新增），rubric 级并发判定。
- **含图 rubric 降级**：deepseek-v4-pro 不接受 `image_url` 输入，`judge.py` 检测到该类异常时对该 rubric 降级为纯文本判分，避免误判为失败（详见 `image_content_unsupported`）。
- 四组合最终各自全量判完：easy 63/63 × 2，main 65/65 × 2，共 256 个任务判分。

---

## 五、评分口径说明

- **normalized_score（norm）**：`total_score / max_score`，即该任务 reward（0–1）。
- **rubric 通过**：`passed_count / total_count`。一个 rubric 的所有 criterion 全 PASS 才拿满该 rubric 的 weight，否则 0。
- **得分**：通过 rubric 的 weight 之和 / 所有 rubric 的 weight 之和。
- **macro vs micro**：macro 按任务等权；micro 按 rubric 分值加权（大任务权重更高）。

---

## 六、复现命令

### 选手（产出交付物）

OpenCode：

```bash
SPLIT=main \
BENCHMARK_MODELS="deepseek/deepseek-v4-flash|deepseek-v4-flash" \
MAX_CONCURRENT_PER_MODEL=8 \
OPENCODE_DISABLE_MODELS_FETCH=1 \
DEEPSEEK_API_KEY=... \
./eval/run_benchmark_opencode.sh
```

pagentv4（inplace）：

```bash
SPLIT=main \
BENCHMARK_MODELS="deepseek/deepseek-v4-flash|pagentv4-deepseek-v4-flash" \
MAX_CONCURRENT_PER_MODEL=16 \
DEEPSEEK_API_KEY=... \
./eval/run_benchmark_pagentv4.sh
```

（把 `SPLIT=main` 换成 `SPLIT=easy` 即跑 Easy split。）

### 裁判（打分，断点续跑）

```bash
SPLIT=main \
JUDGE_MODELS=deepseek-v4-pro \
JUDGE_API_BASE=https://api.deepseek.com \
JUDGE_API_KEY=... \
BENCHMARK_MODELS="deepseek-v4-flash pagentv4-deepseek-v4-flash" \
./eval/run_judge.sh
```

### 聚合与画图

```bash
# 汇总四组合，写快照供画图
uv run python examples/eval/aggregate_scores.py --json examples/eval/jobbench_scores.json

# 生成 Main split 多语言对比图
uv run python examples/eval/plot_jobbench_leaderboard.py
```

---

## 七、逐任务明细

### Main / OpenCode（65 题，降序）

| # | norm | 得分 | rubric | 职业 / 任务 |
|---|---|---|---|---|
| 1 | 0.86 | 50/58 | 8/9 | mechanical_engineering_technicians/task3 |
| 2 | 0.74 | 50/68 | 7/9 | civil_engineers/task2 |
| 3 | 0.73 | 44/60 | 6/8 | data_entry_keyers/task2 |
| 4 | 0.73 | 44/60 | 6/8 | reporters_and_correspondents/task1 |
| 5 | 0.72 | 42/58 | 6/8 | online_merchants/task1 |
| 6 | 0.70 | 46/66 | 7/10 | social_science_research_assistants/task1 |
| 7 | 0.68 | 34/50 | 5/7 | civil_engineers/task1 |
| 8 | 0.64 | 36/56 | 5/8 | computer_user_support_specialists/task1 |
| 9 | 0.64 | 50/78 | 7/10 | mechanical_engineering_technicians/task1 |
| 10 | 0.61 | 56/92 | 8/12 | data_entry_keyers/task1 |
| 11 | 0.61 | 40/66 | 5/9 | financial_managers_branch_or_department/task2 |
| 12 | 0.58 | 38/66 | 5/8 | sociology_teachers_postsecondary/task2 |
| 13 | 0.52 | 26/50 | 3/6 | social_science_research_assistants/task3 |
| 14 | 0.52 | 28/54 | 4/7 | training_and_development_specialists/task3 |
| 15 | 0.52 | 30/58 | 4/7 | biostatisticians/task2 |
| 16 | 0.51 | 40/78 | 5/10 | purchasing_agents.../task2 |
| 17 | 0.50 | 24/48 | 4/8 | lawyers/task1 |
| 18 | 0.50 | 30/60 | 4/7 | secretaries_and_administrative_assistants.../task1 |
| 19 | 0.49 | 46/94 | 5/10 | police_fire_and_ambulance_dispatchers/task1 |
| 20 | 0.49 | 36/74 | 4/8 | sales_agents_securities_and_commodities/task1 |
| 21 | 0.48 | 32/66 | 5/10 | technical_writers/task1 |
| 22 | 0.45 | 30/66 | 4/8 | statisticians/task2 |
| 23 | 0.44 | 30/68 | 4/9 | social_science_research_assistants/task2 |
| 24 | 0.44 | 34/78 | 4/9 | personal_financial_advisors/task1 |
| 25 | 0.42 | 28/66 | 4/9 | mechanical_engineers/task1 |
| 26 | 0.42 | 30/72 | 4/9 | sociology_teachers_postsecondary/task3 |
| 27 | 0.41 | 32/78 | 5/10 | medical_secretaries/task1 |
| 28 | 0.41 | 18/44 | 3/6 | training_and_development_specialists/task2 |
| 29 | 0.41 | 22/54 | 3/8 | statisticians/task3 |
| 30 | 0.40 | 34/84 | 5/12 | technical_writers/task3 |
| 31 | 0.40 | 24/60 | 4/8 | technical_writers/task2 |
| 32 | 0.37 | 20/54 | 3/7 | online_merchants/task2 |
| 33 | 0.37 | 28/76 | 4/9 | civil_engineers/task3 |
| 34 | 0.37 | 28/76 | 4/10 | court_clerks/task1 |
| 35 | 0.37 | 28/76 | 4/10 | customer_service_representatives/task1 |
| 36 | 0.36 | 18/50 | 3/8 | web_administrators/task1 |
| 37 | 0.35 | 26/74 | 3/8 | medical_and_health_services_managers/task1 |
| 38 | 0.33 | 16/48 | 2/6 | secretaries_and_administrative_assistants.../task2 |
| 39 | 0.33 | 18/54 | 3/9 | training_and_development_specialists/task1 |
| 40 | 0.33 | 26/80 | 4/10 | sales_representatives_wholesale.../task2 |
| 41 | 0.32 | 22/68 | 3/8 | sociology_teachers_postsecondary/task1 |
| 42 | 0.27 | 24/90 | 3/11 | financial_managers_branch_or_department/task1 |
| 43 | 0.25 | 22/88 | 3/10 | bookkeeping_accounting_and_auditing_clerks/task1 |
| 44 | 0.25 | 18/72 | 3/10 | licensing_examiners_and_inspectors/task1 |
| 45 | 0.25 | 26/106 | 3/11 | sales_representatives_wholesale.../task1 |
| 46 | 0.23 | 12/52 | 2/8 | bookkeeping_accounting_and_auditing_clerks/task2 |
| 47 | 0.23 | 18/80 | 2/9 | management_analysts/task2 |
| 48 | 0.22 | 26/116 | 3/12 | statisticians/task1 |
| 49 | 0.22 | 16/72 | 2/9 | producers/task1 |
| 50 | 0.21 | 12/56 | 2/8 | computer_and_information_systems_managers/task1 |
| 51 | 0.20 | 18/88 | 3/10 | purchasing_agents.../task1 |
| 52 | 0.18 | 12/66 | 2/9 | computer_and_information_research_scientists/task1 |
| 53 | 0.18 | 16/88 | 2/10 | management_analysts/task1 |
| 54 | 0.17 | 14/82 | 2/10 | computer_user_support_specialists/task2 |
| 55 | 0.17 | 12/72 | 2/9 | management_analysts/task3 |
| 56 | 0.17 | 16/96 | 2/11 | purchasing_agents.../task3 |
| 57 | 0.16 | 10/64 | 1/8 | human_resources_specialists/task1 |
| 58 | 0.15 | 6/40 | 1/6 | supply_chain_managers/task2 |
| 59 | 0.12 | 10/82 | 1/10 | computer_and_information_research_scientists/task2 |
| 60 | 0.11 | 8/70 | 1/8 | mechanical_engineering_technicians/task2 |
| 61 | 0.09 | 6/64 | 1/8 | supply_chain_managers/task1 |
| 62 | 0.08 | 6/72 | 1/8 | biostatisticians/task1 |
| 63 | 0.07 | 6/86 | 1/9 | medical_and_health_services_managers/task2 |
| 64 | 0.00 | 0/62 | 0/7 | computer_and_information_systems_managers/task2 |
| 65 | 0.00 | 0/50 | 0/6 | petroleum_engineers/task1 |

### Main / pagentv4（65 题，降序）

| # | norm | 得分 | rubric | 职业 / 任务 |
|---|---|---|---|---|
| 1 | 1.00 | 52/52 | 7/8 | data_entry_keyers/task2 |
| 2 | 0.91 | 60/66 | 9/10 | technical_writers/task1 |
| 3 | 0.83 | 70/84 | 10/12 | technical_writers/task3 |
| 4 | 0.83 | 48/58 | 7/8 | online_merchants/task1 |
| 5 | 0.82 | 54/66 | 8/10 | social_science_research_assistants/task1 |
| 6 | 0.79 | 44/56 | 6/8 | computer_user_support_specialists/task1 |
| 7 | 0.73 | 48/66 | 6/8 | statisticians/task2 |
| 8 | 0.70 | 42/60 | 5/7 | secretaries_and_administrative_assistants.../task1 |
| 9 | 0.68 | 34/50 | 5/7 | civil_engineers/task1 |
| 10 | 0.65 | 44/68 | 6/9 | civil_engineers/task2 |
| 11 | 0.64 | 50/78 | 6/10 | purchasing_agents.../task2 |
| 12 | 0.62 | 40/64 | 5/8 | human_resources_specialists/task1 |
| 13 | 0.62 | 30/48 | 5/8 | lawyers/task1 |
| 14 | 0.62 | 46/74 | 5/8 | medical_and_health_services_managers/task1 |
| 15 | 0.61 | 40/66 | 5/8 | sociology_teachers_postsecondary/task2 |
| 16 | 0.57 | 54/94 | 6/10 | police_fire_and_ambulance_dispatchers/task1 |
| 17 | 0.57 | 34/60 | 5/8 | reporters_and_correspondents/task1 |
| 18 | 0.53 | 38/72 | 5/9 | sociology_teachers_postsecondary/task3 |
| 19 | 0.52 | 26/50 | 3/6 | social_science_research_assistants/task3 |
| 20 | 0.52 | 28/54 | 4/7 | online_merchants/task2 |
| 21 | 0.52 | 28/54 | 4/7 | training_and_development_specialists/task3 |
| 22 | 0.52 | 30/58 | 5/9 | mechanical_engineering_technicians/task3 |
| 23 | 0.49 | 40/82 | 6/12 | data_entry_keyers/task1 |
| 24 | 0.49 | 38/78 | 5/10 | mechanical_engineering_technicians/task1 |
| 25 | 0.46 | 26/56 | 4/8 | computer_and_information_systems_managers/task1 |
| 26 | 0.46 | 24/52 | 4/8 | bookkeeping_accounting_and_auditing_clerks/task2 |
| 27 | 0.44 | 30/68 | 4/9 | social_science_research_assistants/task2 |
| 28 | 0.42 | 28/66 | 4/9 | financial_managers_branch_or_department/task2 |
| 29 | 0.42 | 30/72 | 4/9 | producers/task1 |
| 30 | 0.42 | 20/48 | 2/6 | secretaries_and_administrative_assistants.../task2 |
| 31 | 0.41 | 32/78 | 4/9 | personal_financial_advisors/task1 |
| 32 | 0.41 | 22/54 | 3/8 | statisticians/task3 |
| 33 | 0.41 | 30/74 | 3/8 | sales_agents_securities_and_commodities/task1 |
| 34 | 0.38 | 22/58 | 3/7 | biostatisticians/task2 |
| 35 | 0.36 | 16/44 | 2/6 | training_and_development_specialists/task2 |
| 36 | 0.33 | 24/72 | 4/10 | licensing_examiners_and_inspectors/task1 |
| 37 | 0.33 | 26/78 | 4/10 | medical_secretaries/task1 |
| 38 | 0.33 | 18/54 | 3/9 | training_and_development_specialists/task1 |
| 39 | 0.32 | 24/76 | 3/11 | financial_managers_branch_or_department/task1 |
| 40 | 0.30 | 18/60 | 3/8 | technical_writers/task2 |
| 41 | 0.29 | 22/76 | 3/10 | customer_service_representatives/task1 |
| 42 | 0.28 | 20/72 | 3/9 | management_analysts/task3 |
| 43 | 0.27 | 24/88 | 3/10 | management_analysts/task1 |
| 44 | 0.27 | 18/66 | 3/9 | mechanical_engineers/task1 |
| 45 | 0.24 | 12/50 | 2/8 | web_administrators/task1 |
| 46 | 0.24 | 18/76 | 3/10 | court_clerks/task1 |
| 47 | 0.23 | 18/80 | 3/10 | sales_representatives_wholesale.../task2 |
| 48 | 0.20 | 18/88 | 3/10 | purchasing_agents.../task1 |
| 49 | 0.20 | 14/70 | 2/8 | mechanical_engineering_technicians/task2 |
| 50 | 0.20 | 16/82 | 2/10 | computer_and_information_research_scientists/task2 |
| 51 | 0.18 | 14/76 | 2/9 | civil_engineers/task3 |
| 52 | 0.18 | 12/66 | 2/9 | computer_and_information_research_scientists/task1 |
| 53 | 0.17 | 14/82 | 2/10 | computer_user_support_specialists/task2 |
| 54 | 0.15 | 16/106 | 2/11 | sales_representatives_wholesale.../task1 |
| 55 | 0.13 | 8/62 | 1/7 | computer_and_information_systems_managers/task2 |
| 56 | 0.12 | 6/50 | 1/6 | petroleum_engineers/task1 |
| 57 | 0.10 | 8/80 | 1/9 | management_analysts/task2 |
| 58 | 0.09 | 6/64 | 1/8 | supply_chain_managers/task1 |
| 59 | 0.09 | 6/68 | 1/8 | sociology_teachers_postsecondary/task1 |
| 60 | 0.09 | 10/116 | 1/12 | statisticians/task1 |
| 61 | 0.08 | 6/72 | 1/8 | biostatisticians/task1 |
| 62 | 0.07 | 6/86 | 1/9 | medical_and_health_services_managers/task2 |
| 63 | 0.07 | 6/88 | 1/10 | bookkeeping_accounting_and_auditing_clerks/task1 |
| 64 | 0.00 | 0/96 | 0/11 | purchasing_agents.../task3 |
| 65 | 0.00 | 0/40 | 0/6 | supply_chain_managers/task2 |

> Easy split 两 harness 的逐任务明细见 `jobbench_scores.json`（`easy/OpenCode`、`easy/pagentv4` 的 `rows`）。机器可读的完整四组合数据都在该快照里。
