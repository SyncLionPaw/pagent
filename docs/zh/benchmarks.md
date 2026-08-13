# 评测

我们用 `deepseek-v4-flash` 作选手跑了 [JobBench](https://job-bench.github.io/)，
对比两条 harness——官方的 **OpenCode** 和 pagentv4 的 **inplace** 模式
（`CodeRunner + InplaceBackend`）。两条 harness 用同一个选手模型、同一个裁判
（`deepseek-v4-pro`，temperature 0），只差 harness 和 split 两个变量。

::: warning 裁判与官方榜不同
官方榜的裁判是 **Grok 4.3**，我们用的是 **deepseek-v4-pro**（和选手同厂，打分偏松）。
所以这里的分数只作内部参考，**不能与官方榜直接横比**，本仓库的两行都标了 `*`。
:::

## OpenCode vs pagentv4

同选手、同裁判，只换 harness。两个 split 上 pagentv4 都领先。

![OpenCode 与 pagentv4 在 JobBench Easy 和 Main split 上的对比——pagentv4 的 micro 分在 Easy 上领先 +4.5，Main 上领先 +1.6](/benchmarks/jobbench_harness_compare_zh.png)

- **Easy split：** pagentv4 **80.0** vs OpenCode 75.5（micro）。
- **Main split：** pagentv4 **38.2** vs OpenCode 36.6（micro）。
- Main 上 pagentv4 有 5 个任务 ≥0.8（含 1 个满分），OpenCode 只有 1 个。

`micro` = 总分 / 满分（按 rubric 权重加权）。`macro` = 各任务归一化分的等权平均。

## 落在 Main 榜单的位置

官方榜只统计 Main split。把本仓库两条 harness 插进那个排名（裁判口径不同，仅示意）：

![JobBench Main split 排行榜，deepseek-v4-flash 在 pagentv4 下 38.2、OpenCode 下 36.6，落在 GPT-5.5 与 Claude Sonnet 4.6 之间](/benchmarks/jobbench_leaderboard_zh.png)

- **pagentv4 = 38.2**，落在 GPT-5.5（38.3）与 Claude Sonnet 4.6（36.6）之间。
- **OpenCode = 36.6**，与 Claude Sonnet 4.6 并列。

## 复现

图从 `examples/eval/jobbench_scores.json` 生成：

```bash
uv run python examples/eval/aggregate_scores.py --json examples/eval/jobbench_scores.json
uv run --with matplotlib python examples/eval/plot_jobbench_leaderboard.py
```

完整方法论、逐任务明细和运行命令见
[`examples/eval/REPORT_jobbench_deepseek-v4-flash.md`](https://github.com/SyncLionPaw/pagent/blob/main/examples/eval/REPORT_jobbench_deepseek-v4-flash.md)。
