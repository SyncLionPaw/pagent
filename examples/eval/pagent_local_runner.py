"""Compatibility entry point for the packaged Harbor runner."""

from pagentv4.adapters.harbor_runner import run

if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
