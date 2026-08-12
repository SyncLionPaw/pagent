# examples/eval

用当前 pagentv4 Runner 做测评 / benchmark 的示例。

| 示例 | 内容 |
|------|------|
| [runners_demo.py](runners_demo.py) | `VanillaRunner` / `ChatRunner` / `CodeRunner` 各跑一例 |
| [gsm8k_compare.py](gsm8k_compare.py) | GSM8K 小子集：无工具 vs `calc` 工具对比 |
| [swe_bench_run.py](swe_bench_run.py) | SWE-bench_Lite 冒烟测试：`CodeRunner` 作 coding agent（20 题，分层评测） |
| [harbor_pagent.py](harbor_pagent.py) | Terminal-Bench 2.1：在任务容器内运行 pagentv4 local harness |
| [aggregate_scores.py](aggregate_scores.py) · [plot_jobbench_leaderboard.py](plot_jobbench_leaderboard.py) | JobBench 判分聚合 + Main split 多语言排行榜图，见 [REPORT_jobbench_deepseek-v4-flash.md](REPORT_jobbench_deepseek-v4-flash.md) |

## API

```python
from pagentv4 import AgentCore, ChatRunner, CodeRunner, DeepSeek, VanillaRunner

# 无持久化、无 sandbox
runner = VanillaRunner(AgentCore(DeepSeek("deepseek-v4-flash"), system="..."))
ans = "".join([text async for text in runner.run(question, return_type="text")])

# conversation 持久化
runner = ChatRunner(AgentCore(DeepSeek("deepseek-v4-flash"), system="..."), thread_id="eval")
try:
    ans = "".join([text async for text in runner.run(question, return_type="text")])
finally:
    await runner.close()

# sandbox 文件/命令能力；第一次 run 前自动初始化 sandbox
runner = CodeRunner(
    AgentCore(DeepSeek("deepseek-v4-flash"), system="..."),
    thread_id="eval-code",
    backend="local",
)
try:
    ans = "".join([text async for text in runner.run(task, return_type="text")])
finally:
    await runner.close()
```

## 运行

```bash
export DEEPSEEK_API_KEY="your-key"
uv run python -m examples.eval.runners_demo
uv run --with datasets python -m examples.eval.gsm8k_compare
uv run --with datasets python -m examples.eval.gsm8k_compare --sample hard --limit 30 -v
uv run --with datasets python -m examples.eval.gsm8k_compare --sample head --limit 10

# SWE-bench_Lite 冒烟测试（CodeRunner 作 coding agent；数据 HF 直链下载，无需登录）
uv run --with pyarrow python -m examples.eval.swe_bench_run --limit 1 -v
uv run --with pyarrow python -m examples.eval.swe_bench_run --limit 20
uv run --with pyarrow python -m examples.eval.swe_bench_run --limit 20 --try-tests  # 含 best-effort 测试运行
```

## Terminal-Bench 2.1

Terminal-Bench 2.1 覆盖编译、调试、系统管理和文件操作等多步终端任务。Harbor
为每题创建隔离环境并运行 verifier。`harbor_pagent.PagentV4Agent` 会把当前
pagent 源码构建成 wheel，安装到任务容器，然后在容器的 task workdir 中启动
pagentv4 `CodeRunner + InplaceBackend`。命令执行和文件操作都发生在任务容器内，
模型通过配置的 API 调用。

前置条件：

- Python 3.12+
- Docker Engine 与 `docker compose`，或提供 Docker-compatible socket 的 Podman
- 一个支持 tool calling 的 OpenAI-compatible 模型

先运行 Harbor 的 oracle，确认容器和数据集可用：

```bash
uvx --python 3.12 --from harbor==0.20.0 harbor run \
  -d terminal-bench/terminal-bench-2-1 \
  -a oracle \
  -n 1 -k 1 -l 1
```

用 pagentv4 跑一道题：

```bash
export DEEPSEEK_API_KEY="..."

uvx --python 3.12 --from harbor==0.20.0 --with-editable . harbor run \
  -d terminal-bench/terminal-bench-2-1 \
  -a pagentv4.adapters.harbor:PagentV4Agent \
  -m deepseek/deepseek-chat \
  -n 1 -k 1 -l 1 \
  --ak max_turns=100
```

自定义 OpenAI-compatible endpoint（该地址需要能从任务容器访问）：

```bash
export PAGENT_BENCH_BASE_URL="https://api.example.com/v1"
export PAGENT_BENCH_API_KEY="not-needed"

uvx --python 3.12 --from harbor==0.20.0 --with-editable . harbor run \
  -d terminal-bench/terminal-bench-2-1 \
  -a pagentv4.adapters.harbor:PagentV4Agent \
  -m local/model-name \
  -n 1 -k 1 -l 1
```

结果、运行日志和 pagent 对话轨迹都写入 Harbor job 目录下对应 trial 的 `agent/`
目录。确认单题链路后，再提高 `-l` 任务数和 `-n` 并发数；固定模型、prompt、
`max_turns`、数据集版本和 `-k` 后，不同 harness 版本的结果才可比较。

### SWE-bench Verified

SWE-bench Verified 共 500 题。先用 `--install-only` 验证镜像、wheel 和 agent
安装链路，该命令不会调用模型：

```bash
uvx --python 3.12 --from harbor==0.20.0 --with-editable . harbor run \
  --install-only -y \
  -d swe-bench/swe-bench-verified \
  -a pagentv4.adapters.harbor:PagentV4Agent \
  -m deepseek/deepseek-chat \
  -n 1 -k 1 -l 1
```

安装验证通过后去掉 `--install-only` 运行一道题。确认结果和轨迹正常，再逐步增加
`-l` 和 `-n`。首次运行每个仓库版本时需要下载较大的官方测试镜像。

在 macOS 上使用 Podman 时，安装 Docker CLI 与 Compose 插件，并让 Harbor 通过
Podman 的 Docker-compatible socket 访问容器引擎：

```bash
export DOCKER_HOST="unix://$(podman machine inspect \
  --format '{{.ConnectionInfo.PodmanSocket.Path}}')"
docker version
docker compose version
```

### SWE-bench 状态分档

- `resolved`：agent patch + gold test_patch 在 fresh checkout 上让 FAIL_TO_PASS 全过（Tier1，需 `--try-tests`）
- `partial`：Tier1 环境正常但部分测试未过
- `patch-only`：Tier1 未跑或失败；看 patch 能否干净 apply + 与 gold 的文件重合（`file_jaccard`）/ 行相似度（`line_similarity`）
- `failed`：无 patch 或 patch 无法 apply

⚠️ 本机无 docker，无法用官方 `sweb.eval` 测试镜像。Tier1 在宿主机用 `venv + pip install -e .` 构建 best-effort 环境，存在 Python 版本不匹配、C 扩展编译失败等问题。`resolved` 率为下界，**不可与官方 leaderboard 对比**；`patch-only` 档的结构指标更可靠。
