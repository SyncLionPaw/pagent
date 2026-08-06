from __future__ import annotations

from typing import Any

TITLE_MAX_CHARS = 40


def fallback_title(text: str) -> str:
    """Build a deterministic title when model generation is unavailable."""
    one_line = " ".join(text.split())
    if len(one_line) <= TITLE_MAX_CHARS:
        return one_line
    return one_line[:TITLE_MAX_CHARS] + "…"


def normalize_title(text: str) -> str:
    """Normalize model output into one short, displayable title."""
    line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    for prefix in ("标题：", "标题:", "Title:", "Title："):
        if line.startswith(prefix):
            line = line[len(prefix) :].strip()
            break
    line = line.strip("\"'“”‘’`# ")
    return fallback_title(line)


async def make_title(provider: Any, user_text: str) -> str:
    """Ask the active model for a title without mutating conversation history."""
    stream = await provider.complete(
        [
            {
                "role": "system",
                "content": (
                    "为一段新对话生成简短标题。只输出标题，不加引号、标签或解释。"
                    "标题使用用户输入的语言，概括具体任务，最多20个汉字或40个字符。"
                ),
            },
            {"role": "user", "content": user_text},
        ],
        tools=None,
        temperature=0.2,
        max_tokens=48,
    )
    parts: list[str] = []
    async for chunk in stream:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue
        delta = getattr(choices[0], "delta", None)
        content = getattr(delta, "content", None) if delta is not None else None
        if isinstance(content, str):
            parts.append(content)
    return normalize_title("".join(parts)) or fallback_title(user_text)
