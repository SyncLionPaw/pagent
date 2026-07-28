"""预制子 agent：explore 只读白名单、注册表选取。"""

import pytest

from pagentv4 import PRESET_SUBAGENTS, preset_subs
from pagentv4.ithread import SubAgentSpec
from pagentv4.subagents import EXPLORE
from pagentv4.subagents.explore import EXPLORE_TOOLS


def test_explore_is_read_only():
    # explore 的沙箱白名单不含任何写/交付工具。
    assert isinstance(EXPLORE, SubAgentSpec)
    forbidden = {"write_file", "str_replace", "copy_from_host", "copy_to_host"}
    assert forbidden.isdisjoint(EXPLORE.sandbox_tools)
    # 读与检索工具在。
    assert set(EXPLORE.sandbox_tools) == set(EXPLORE_TOOLS)
    assert "read_file" in EXPLORE.sandbox_tools
    assert "run_command" in EXPLORE.sandbox_tools


def test_explore_has_system_prompt():
    assert EXPLORE.system.strip()
    assert "只读" in EXPLORE.system


def test_preset_registry_contains_explore():
    assert "explore" in PRESET_SUBAGENTS
    assert PRESET_SUBAGENTS["explore"] is EXPLORE


def test_preset_subs_all_when_no_names():
    assert preset_subs() == dict(PRESET_SUBAGENTS)


def test_preset_subs_selects_named():
    picked = preset_subs("explore")
    assert set(picked) == {"explore"}
    assert picked["explore"] is EXPLORE


def test_preset_subs_unknown_raises():
    with pytest.raises(ValueError, match="unknown preset subagents"):
        preset_subs("nope")
