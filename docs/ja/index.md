---
layout: home

hero:
  image:
    src: /logo.png
    alt: pagent
  name: pagent
  text: あなたの軽量 Agent フレームワーク
  tagline: 小さく · 透ける · あなたが足す
  actions:
    - theme: brand
      text: クイックスタート
      link: /ja/guide/quick-start
    - theme: alt
      text: インストール
      link: /ja/guide/install
    - theme: alt
      text: English
      link: /
    - theme: alt
      text: 中文文档
      link: /zh/
    - theme: alt
      text: 四川话
      link: /sc/

features:
  - title: 小さく埋め込み可能
    details: Session + Agent + ツール — ファイル編集やシェル、MCP は含みません。ループはあなたが握ります。
  - title: 流しながら表示
    details: ストリーミング出力に対応。UI を足すときはドキュメントで順を追って説明します。
  - title: OpenAI 形式 API
    details: OpenAI、DeepSeek、Ollama、vLLM、SGLang など /v1/chat/completions 互換サーバーに対応。
---

## 同じモデル、より良い harness

[JobBench](https://job-bench.github.io/) では、pagentv4 の inplace harness が
両 split で公式 OpenCode harness を上回ります——同一プレイヤー
（`deepseek-v4-flash`）・同一審査で、harness のみ変更。

<div style="display:flex; flex-wrap:wrap; gap:16px; align-items:flex-start;">
  <a href="./benchmarks" style="flex:1 1 300px;">
    <img src="/benchmarks/jobbench_harness_compare_ja.png" alt="JobBench における OpenCode と pagentv4 の比較——micro スコアで pagentv4 が Easy で +4.5、Main で +1.6 リード" style="width:100%; border-radius:8px;">
  </a>
  <a href="./benchmarks" style="flex:1 1 300px;">
    <img src="/benchmarks/jobbench_leaderboard_ja.png" alt="JobBench Main split リーダーボード——deepseek-v4-flash が pagentv4 で 38.2、GPT-5.5 と Claude Sonnet 4.6 の間" style="width:100%; border-radius:8px;">
  </a>
</div>

[ベンチマークの詳細 →](./benchmarks)

**この harness を試す？** 同じ pagentv4 コアで、好きな入口を選べます（以下は英語ページ）：

[ターミナル CLI（`uv run pagent`）→](/pagentv4/) · [デスクトップ →](/desktop) · [VS Code 拡張 →](/vscode) · [Web UI →](/web)

## 25 行足らずで Agent が動く

プロバイダのタブを選び、API Key を設定、`demo.py` で `python demo.py`。モデルが `@tool` を呼び、答えは `result.content`。

::: code-group

<<< ../snippets/minimal_agent_openai.py{python}[OpenAI]

<<< ../snippets/minimal_agent_deepseek.py{python}[DeepSeek]

<<< ../snippets/minimal_agent_claude.py{python}[Claude]

<<< ../snippets/minimal_agent_kimi.py{python}[Kimi]

:::

出力例：`Sunny in Xiamen today.`（実際の出力はモデル次第）。[プロバイダと API Key](./guide/providers)

[インストール →](./guide/install) · [クイックスタート →](./guide/quick-start)
