"""In-process locks for concurrent eval variant progress on a shared snapshot."""

from __future__ import annotations

import asyncio
from uuid import UUID

_locks: dict[UUID, asyncio.Lock] = {}
_guard = asyncio.Lock()


async def progress_lock(run_id: UUID) -> asyncio.Lock:
    """Return a process-local lock for eval_run snapshot updates."""
    async with _guard:
        lock = _locks.get(run_id)
        if lock is None:
            lock = asyncio.Lock()
            _locks[run_id] = lock
        return lock


def discard_progress_lock(run_id: UUID) -> None:
    """Drop lock after a run reaches a terminal state (best-effort cleanup)."""
    _locks.pop(run_id, None)
