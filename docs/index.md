---
layout: home

hero:
  image:
    src: /logo.png
    alt: pagent
  name: pagent
  text: Your minimal agent framework
  tagline: Small · transparent · you extend it
  actions:
    - theme: brand
      text: Quick start
      link: /guide/quick-start
    - theme: alt
      text: Install
      link: /guide/install
    - theme: alt
      text: 中文文档
      link: /zh/
    - theme: alt
      text: 日本語
      link: /ja/
    - theme: alt
      text: 四川话
      link: /sc/

features:
  - title: Small & embeddable
    details: Session + Agent + tools — no file editor, no shell, no MCP. You own the loop.
  - title: Stream as it runs
    details: Incremental output for chat UIs — wire up your own frontend when you are ready; the docs walk you through it.
  - title: OpenAI-shaped API
    details: Works with OpenAI, DeepSeek, Ollama, vLLM, SGLang — any /v1/chat/completions compatible server.
---

## Same model, better harness

On [JobBench](https://job-bench.github.io/), pagentv4's inplace harness beats the
official OpenCode harness on both splits — same player (`deepseek-v4-flash`) and
same judge, only the harness changes.

<div style="display:flex; flex-wrap:wrap; gap:16px; align-items:flex-start;">
  <a href="./benchmarks" style="flex:1 1 300px;">
    <img src="/benchmarks/jobbench_harness_compare_en.png" alt="OpenCode vs pagentv4 on JobBench — pagentv4 leads micro score by +4.5 on Easy and +1.6 on Main" style="width:100%; border-radius:8px;">
  </a>
  <a href="./benchmarks" style="flex:1 1 300px;">
    <img src="/benchmarks/jobbench_leaderboard_en.png" alt="JobBench Main split leaderboard — deepseek-v4-flash under pagentv4 at 38.2 sits between GPT-5.5 and Claude Sonnet 4.6" style="width:100%; border-radius:8px;">
  </a>
</div>

[See the full benchmarks →](./benchmarks)

**Want to try this harness?** Same pagentv4 core, pick the surface you like:

[Terminal CLI (`uv run pagent`) →](./pagentv4/) · [Desktop app →](./desktop) · [VS Code extension →](./vscode) · [Web UI →](./web)

## A full agent in ~25 lines

Pick a provider tab, set the API key, save as `demo.py`, run `python demo.py`. The model can call your `@tool` and you read the answer from `result.content`.

::: code-group

<<< ./snippets/minimal_agent_openai.py{python}[OpenAI]

<<< ./snippets/minimal_agent_deepseek.py{python}[DeepSeek]

<<< ./snippets/minimal_agent_claude.py{python}[Claude]

<<< ./snippets/minimal_agent_kimi.py{python}[Kimi]

:::

Example output: `Sunny in Xiamen today.` (actual text depends on the model). More providers: [Providers & API keys](./guide/providers).

[Install →](./guide/install) · [Quick start →](./guide/quick-start)

## Looking for pagentv4?

The repo also contains a newer typed API built around `Provider`,
`Message`, `Runner`, and optional sandbox execution.

[pagentv4 overview →](./pagentv4/) · [pagentv4 quick start →](./pagentv4/quick-start)
