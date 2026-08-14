from __future__ import annotations

import os
from pathlib import Path


def default_pagent_home() -> Path:
    explicit = os.getenv("PAGENT_HOME")
    if explicit and explicit.strip():
        return Path(explicit).expanduser().resolve()
    return Path("~/.pagent").expanduser().resolve()
