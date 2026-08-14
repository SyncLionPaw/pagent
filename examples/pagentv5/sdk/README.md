# pagentv5 SDK examples

| 文件 | 用途 |
|---|---|
| `base_agent.py` | 有状态模型会话与完整事件流 |
| `base_agent_persistent.py` | 在当前目录用 JSONL 持久化 BaseAgent 对话 |
| `local_workspace_agent.py` | 直接读写本地工作目录 |
| `sandbox_worker.py` | 在 Podman 容器中执行命令和文件工具 |
| `sandbox_worker_ssh.py` | 在 SSH 远程工作区中执行命令和文件工具 |

运行前配置模型凭据：

```bash
export DEEPSEEK_API_KEY="your-key-here"
```

各示例的环境变量和运行命令写在对应文件顶部。

SSH 示例使用 ssh-agent 和 AsyncSSH 的默认密钥发现，并从以下环境变量读取连接：

- `PAGENT_SSH_HOST`
- `PAGENT_SSH_USER`
- `PAGENT_SSH_PORT`
- `PAGENT_SSH_WORKDIR`
- `PAGENT_SSH_KNOWN_HOSTS`
