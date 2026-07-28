"""explore —— 预制的只读勘探子 agent。

面向"大范围扫代码 / 定位 / 调研"这类任务：主 agent 把一段需要翻很多文件的检索
丢给它，它只读地翻，回来只给结论，不把成堆文件内容灌回主上下文。

只读通过沙箱工具白名单落实：只给 read_file / list_dir / list_host_files /
run_command。run_command 仍在（grep/find/rg 这类检索靠它），沙箱层的
command_policy 负责挡越界路径；写类工具（write_file / str_replace / copy_*）
一概不给，从工具集和提示词两头都拿不到。
"""

from __future__ import annotations

from ..ithread import SubAgentSpec

# explore 能用的沙箱工具：读 + 检索，不含任何写/交付工具。
EXPLORE_TOOLS = (
    "read_file",
    "list_dir",
    "list_host_files",
    "run_command",
)

EXPLORE_SYSTEM = """你是一个只读勘探子 agent，专门大范围搜代码、文件和目录，替主 agent 定位信息。

你的工具是只读的：read_file 读文件、list_dir / list_host_files 看目录、run_command 跑
grep / find / rg 这类检索命令。你没有写文件或改文件的能力，也不需要——你的产出是结论，
不是改动。

工作方式：
- 收到任务先想清楚要找什么，再用检索命令缩小范围，最后读关键片段确认。
- 回答要直接给结论：命中的位置（文件路径 + 行号）、关键代码片段、以及你的判断。
- 不要把整个文件或大段内容原样贴回来，主 agent 要的是"在哪、是什么、说明什么"。
- 找不到就明说找不到，并说明你搜了哪些范围，别编。
"""

EXPLORE = SubAgentSpec(
    system=EXPLORE_SYSTEM,
    sandbox_tools=EXPLORE_TOOLS,
)
