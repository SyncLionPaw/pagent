"""Create a persistent Task from Provider, Sandbox, UserDir, and Session resources.

Usage:
    uv run python -m examples.pagentv5.resources
"""

import asyncio
import tempfile
from pathlib import Path

from pagentv5 import (
    LocalTaskBackend,
    ResourceService,
    SandboxConfig,
    SessionConfig,
    TaskSpec,
    UserDirConfig,
)


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="pagentv5-") as temporary:
        root = Path(temporary)
        service = ResourceService(LocalTaskBackend(root / "tasks"))
        spec = TaskSpec(
            sandbox=SandboxConfig(backend="local"),
            userdir=UserDirConfig(access="readonly", path=str(Path.cwd())),
            session=SessionConfig(storage="jsonl", root="messages"),
        )

        task = await service.create_task(
            spec,
            task_id="example-task",
            title="Resource example",
        )
        capabilities = await service.capabilities("example-task")

        print(f"Task: {task['id']}")
        print(f"Tools: {', '.join(capabilities['tool_names'])}")
        print(f"Task config: {task['spec_path']}")
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())
