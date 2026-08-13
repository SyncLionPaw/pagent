# Benchmarks

We ran [JobBench](https://job-bench.github.io/) with `deepseek-v4-flash` as the
player, comparing two harnesses — the official **OpenCode** and pagentv4's
**inplace** mode (`CodeRunner + InplaceBackend`). Both use the same player model
and the same judge (`deepseek-v4-pro`, temperature 0), so only the harness and
the split change.

::: warning Judge differs from the official leaderboard
The official leaderboard is judged by **Grok 4.3**. We judge with
**deepseek-v4-pro** (same vendor as the player, so scores run lenient). Our
numbers are indicative only and **not directly comparable** to the official
board. That is why our rows are marked with `*`.
:::

## OpenCode vs pagentv4

Same player, same judge — swapping only the harness. pagentv4 leads on both
splits.

![OpenCode vs pagentv4 on JobBench Easy and Main splits — pagentv4 leads micro score by +4.5 on Easy and +1.6 on Main](/benchmarks/jobbench_harness_compare_en.png)

- **Easy split:** pagentv4 **80.0** vs OpenCode 75.5 (micro).
- **Main split:** pagentv4 **38.2** vs OpenCode 36.6 (micro).
- On Main, pagentv4 produced 5 tasks scoring ≥0.8 (one perfect) against
  OpenCode's 1.

`micro` = total score / max score (rubric-weighted). `macro` = mean of
per-task normalized scores.

## Where it lands on the Main leaderboard

The official board only counts the Main split. Dropping our two harness runs
into that ranking (judge differs, so this is illustrative):

![JobBench Main split leaderboard with deepseek-v4-flash under pagentv4 at 38.2 and OpenCode at 36.6, placed between GPT-5.5 and Claude Sonnet 4.6](/benchmarks/jobbench_leaderboard_en.png)

- **pagentv4 = 38.2** lands between GPT-5.5 (38.3) and Claude Sonnet 4.6 (36.6).
- **OpenCode = 36.6** ties with Claude Sonnet 4.6.

## Reproduce

Figures are generated from `examples/eval/jobbench_scores.json`:

```bash
uv run python examples/eval/aggregate_scores.py --json examples/eval/jobbench_scores.json
uv run --with matplotlib python examples/eval/plot_jobbench_leaderboard.py
```

Full methodology, per-task breakdowns, and run commands are in
[`examples/eval/REPORT_jobbench_deepseek-v4-flash.md`](https://github.com/SyncLionPaw/pagent/blob/main/examples/eval/REPORT_jobbench_deepseek-v4-flash.md).
