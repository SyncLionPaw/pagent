"""预制子 agent —— 开箱即用的命名 SubAgentSpec。

这里放官方预设的子 agent 角色（system 提示词 + 沙箱工具白名单），供上层直接取用，
免去每个 thread 手写 [sub.<name>]。

用法：把需要的预设并进 thread.spec.subs，再在 [agent] tools 列 delegate_to_subagent
即可让主 agent 委派。程序化创建时：

    from pagentv4.subagents import PRESET_SUBAGENTS

    overrides = {
        "agent_tools": ("delegate_to_subagent",),
        "subs": {"explore": PRESET_SUBAGENTS["explore"]},
    }

角色本身与运行机制解耦：这里只声明"是谁、能用哪些工具"，怎么委派、怎么落盘由
tools/delegate.py 与 runtime 负责。
"""

from __future__ import annotations

from ..ithread import SubAgentSpec
from .explore import EXPLORE

# name -> SubAgentSpec，预设子 agent 注册表。
PRESET_SUBAGENTS: dict[str, SubAgentSpec] = {
    "explore": EXPLORE,
}


def preset_subs(*names: str) -> dict[str, SubAgentSpec]:
    """挑选若干预设子 agent，返回可直接并进 thread.spec.subs 的 dict。

    不传名字则返回全部预设。未知名字直接报错，避免拼错被静默忽略。
    """
    if not names:
        return dict(PRESET_SUBAGENTS)
    unknown = [n for n in names if n not in PRESET_SUBAGENTS]
    if unknown:
        available = ", ".join(PRESET_SUBAGENTS)
        raise ValueError(f"unknown preset subagents: {unknown}; available: {available}")
    return {name: PRESET_SUBAGENTS[name] for name in names}


__all__ = ["EXPLORE", "PRESET_SUBAGENTS", "preset_subs"]
