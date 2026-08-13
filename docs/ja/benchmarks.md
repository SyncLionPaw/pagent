# ベンチマーク

`deepseek-v4-flash` をプレイヤーとして [JobBench](https://job-bench.github.io/)
を実行し、2 つの harness——公式の **OpenCode** と pagentv4 の **inplace** モード
（`CodeRunner + InplaceBackend`）——を比較しました。両 harness は同一のプレイヤー
モデルと同一の審査（`deepseek-v4-pro`、temperature 0）を使い、harness と split
のみが異なります。

::: warning 審査は公式リーダーボードと異なる
公式リーダーボードの審査は **Grok 4.3** ですが、ここでは **deepseek-v4-pro**
（プレイヤーと同一ベンダーのため甘め）で採点しています。本リポジトリのスコアは
参考値であり、公式ボードとは**直接比較できません**。該当行には `*` を付けています。
:::

## OpenCode vs pagentv4

同一プレイヤー・同一審査で harness のみ変更。両 split で pagentv4 が上回ります。

![JobBench の Easy と Main split における OpenCode と pagentv4 の比較。micro スコアで pagentv4 が Easy で +4.5、Main で +1.6 リード](/benchmarks/jobbench_harness_compare_ja.png)

- **Easy split：** pagentv4 **80.0** vs OpenCode 75.5（micro）。
- **Main split：** pagentv4 **38.2** vs OpenCode 36.6（micro）。
- Main では pagentv4 が ≥0.8 のタスクを 5 件（うち 1 件は満点）獲得、OpenCode は 1 件。

`micro` = 合計 / 満点（rubric 重み付け）。`macro` = タスクごとの正規化スコアの等重平均。

## Main リーダーボードでの位置

公式ボードは Main split のみを集計します。本リポジトリの 2 つの harness をその
ランキングに挿入した図（審査基準が異なるため参考）：

![JobBench Main split リーダーボード。deepseek-v4-flash が pagentv4 で 38.2、OpenCode で 36.6、GPT-5.5 と Claude Sonnet 4.6 の間に位置](/benchmarks/jobbench_leaderboard_ja.png)

- **pagentv4 = 38.2**：GPT-5.5（38.3）と Claude Sonnet 4.6（36.6）の間。
- **OpenCode = 36.6**：Claude Sonnet 4.6 と同点。

## 再現

図は `examples/eval/jobbench_scores.json` から生成します：

```bash
uv run python examples/eval/aggregate_scores.py --json examples/eval/jobbench_scores.json
uv run --with matplotlib python examples/eval/plot_jobbench_leaderboard.py
```

方法論の詳細、タスクごとの内訳、実行コマンドは
[`examples/eval/REPORT_jobbench_deepseek-v4-flash.md`](https://github.com/SyncLionPaw/pagent/blob/main/examples/eval/REPORT_jobbench_deepseek-v4-flash.md)
を参照してください。
