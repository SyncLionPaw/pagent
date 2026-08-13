---
layout: home

hero:
  image:
    src: /logo.png
    alt: pagent
  name: pagent
  text: 你的轻量 Agent 框架
  tagline: 小库 · 全透明 · 你说了算
  actions:
    - theme: brand
      text: 快速开始
      link: /zh/guide/quick-start
    - theme: alt
      text: 安装
      link: /zh/guide/install
    - theme: alt
      text: English
      link: /
    - theme: alt
      text: 日本語
      link: /ja/
    - theme: alt
      text: 四川话
      link: /sc/

features:
  - title: 小而可嵌入
    details: Session + Agent + 工具 — 不带文件编辑、终端或 MCP，循环由你掌控。
  - title: 边跑边看
    details: 支持流式输出，适合聊天界面；需要再接 UI 时，文档里一步步写清楚。
  - title: OpenAI 形态 API
    details: 支持 OpenAI、DeepSeek、Ollama、vLLM、SGLang 等兼容 /v1/chat/completions 的服务。
---

## 同一模型，更好的 harness

在 [JobBench](https://job-bench.github.io/) 上，pagentv4 的 inplace harness 在两个
split 上都胜过官方 OpenCode harness——同选手（`deepseek-v4-flash`）、同裁判，只换 harness。

<div style="display:flex; flex-wrap:wrap; gap:16px; align-items:flex-start;">
  <a href="./benchmarks" style="flex:1 1 300px;">
    <img src="/benchmarks/jobbench_harness_compare_zh.png" alt="OpenCode 与 pagentv4 在 JobBench 上的对比——pagentv4 的 micro 分在 Easy 上领先 +4.5，Main 上领先 +1.6" style="width:100%; border-radius:8px;">
  </a>
  <a href="./benchmarks" style="flex:1 1 300px;">
    <img src="/benchmarks/jobbench_leaderboard_zh.png" alt="JobBench Main split 排行榜——deepseek-v4-flash 在 pagentv4 下 38.2，落在 GPT-5.5 与 Claude Sonnet 4.6 之间" style="width:100%; border-radius:8px;">
  </a>
</div>

[查看完整评测 →](./benchmarks)

**想试试这条 harness？** 同一套 pagentv4 内核，挑你顺手的入口：

[终端 CLI（`uv run pagent`）→](./pagentv4/) · [桌面端 →](./desktop) · [VS Code 插件 →](./vscode) · [Web UI →](./web)

## 二十多行，就是一个 Agent

选一个模型标签，设置对应 API Key，保存为 `demo.py`，运行 `python demo.py`。模型会按需调用 `@tool`，答案在 `result.content`。

::: code-group

<<< ../snippets/minimal_agent_openai.py{python}[OpenAI]

<<< ../snippets/minimal_agent_deepseek.py{python}[DeepSeek]

<<< ../snippets/minimal_agent_claude.py{python}[Claude]

<<< ../snippets/minimal_agent_kimi.py{python}[Kimi]

:::

示例输出：`Sunny in Xiamen today.`（以模型实际返回为准）。更多见 [模型与 API Key](./guide/providers)。

[安装 →](./guide/install) · [快速开始 →](./guide/quick-start)

## 想用 pagentv4？

仓库还提供较新的类型化 API，围绕 `Provider`、`Message`、`Runner`，
以及可选的 sandbox 执行环境。

[pagentv4 概览 →](./pagentv4/) · [pagentv4 快速开始 →](./pagentv4/quick-start)
