"""Per-PR git worktree manager for the orchestrator daemon.

The orchestrator runs up to ``_MAX_CONCURRENT_RUNS`` PR-review agents in
parallel (``daemon.py``). Without isolation they would share the host's
working directory and race on ``.git/index.lock`` and on file state. This
module hands each run its own worktree under
``~/.claude/orchestrator/worktrees/<repo-slug>/<key>``, persisted across
runs for the same PR / branch and reconciled on daemon start.

Concurrency model:

* one ``asyncio.Lock`` per ``key`` — two acquires for the SAME key serialize
  on the same checkout; two acquires for DIFFERENT keys proceed in parallel.
* the underlying SQLite registry is single-writer (the daemon).

Lifecycle:

* ``acquire(key, ref)`` is the async context manager runs use; the
  worktree is NOT removed on exit (persistent), only ``last_used_at`` is
  bumped so :meth:`prune` can evict by LRU.
* ``reconcile()`` is called once on daemon start: it drops registry rows
  whose path is missing on disk, and ``git worktree remove``-s on-disk
  worktrees that are not tracked in the registry.
* ``prune(max_count, max_age_days)`` evicts the LRU tail.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import sqlite3
import time
from collections import defaultdict
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

_KEY_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_GIT_TIMEOUT_SECONDS = 60.0


class WorktreeError(RuntimeError):
    """Raised when a git worktree operation fails."""


@dataclass(frozen=True)
class WorktreeRecord:
    key: str
    path: Path
    ref: str
    created_at: int
    last_used_at: int


def bootstrap_worktrees_table(conn: sqlite3.Connection) -> None:
    """Create the ``worktrees`` table if missing. Idempotent."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS worktrees (
            key            TEXT PRIMARY KEY,
            path           TEXT NOT NULL,
            ref            TEXT NOT NULL,
            created_at     INTEGER NOT NULL,
            last_used_at   INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS worktrees_by_last_used ON worktrees (last_used_at)"
    )
    conn.commit()


class WorktreeManager:
    def __init__(
        self,
        *,
        repo_path: Path,
        root: Path,
        conn: sqlite3.Connection,
    ) -> None:
        self._repo_path = repo_path
        self._root = root
        self._conn = conn
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._git = shutil.which("git") or "git"

    @asynccontextmanager
    async def acquire(self, *, key: str, ref: str) -> AsyncIterator[Path]:
        """Yield the worktree path for ``key`` checked out at ``ref``.

        Holds a per-key lock for the lifetime of the ``async with`` block, so
        two concurrent runs for the same PR queue serially on the same
        directory. Different keys never block each other.

        Raises :class:`WorktreeError` if any underlying ``git`` call fails.
        """
        if not _KEY_RE.match(key):
            raise WorktreeError(f"invalid worktree key: {key!r}")
        if not ref:
            raise WorktreeError("ref must be non-empty")

        lock = self._locks[key]
        async with lock:
            path = self._path_for(key)
            existing = self._registry_get(key)

            if existing is not None and path.exists():
                await self._refresh(path, ref)
            else:
                if path.exists():
                    await self._remove_worktree_disk(path)
                self._root.mkdir(parents=True, exist_ok=True)
                await self._add_worktree(path, ref)

            now = int(time.time())
            self._registry_upsert(key, path, ref, now)
            try:
                yield path
            finally:
                self._registry_touch(key, int(time.time()))

    async def reconcile(self) -> None:
        """Drop registry rows whose path is missing; remove on-disk worktrees
        not present in the registry. Called once at daemon start."""
        registered = self._registry_all()
        registered_paths = {Path(r.path).resolve() for r in registered}

        for record in registered:
            if not Path(record.path).exists():
                self._registry_delete(record.key)

        if not self._root.exists():
            return

        on_disk: list[Path] = []
        for child in self._root.iterdir():
            if child.is_dir():
                on_disk.append(child.resolve())

        for path in on_disk:
            if path not in registered_paths:
                await self._remove_worktree_disk(path)

        await self._git_run(["worktree", "prune"], cwd=self._repo_path)

    async def prune(self, *, max_count: int, max_age_days: int) -> int:
        """Evict LRU entries above ``max_count`` and older than ``max_age_days``.

        Returns the number of entries removed.
        """
        now = int(time.time())
        cutoff = now - max_age_days * 86400
        records = self._registry_all_by_lru()
        keep_recent = [r for r in records if r.last_used_at >= cutoff]
        evict: list[WorktreeRecord] = [r for r in records if r.last_used_at < cutoff]

        if max_count >= 0 and len(keep_recent) > max_count:
            overflow = len(keep_recent) - max_count
            evict.extend(keep_recent[:overflow])

        for record in evict:
            await self._evict(record)
        return len(evict)

    def _path_for(self, key: str) -> Path:
        return self._root / key

    async def _add_worktree(self, path: Path, ref: str) -> None:
        await self._git_run(["fetch", "origin", ref], cwd=self._repo_path)
        await self._git_run(
            ["worktree", "add", "--detach", str(path), "FETCH_HEAD"],
            cwd=self._repo_path,
        )

    async def _refresh(self, path: Path, ref: str) -> None:
        await self._git_run(["fetch", "origin", ref], cwd=path)
        await self._git_run(["reset", "--hard", "FETCH_HEAD"], cwd=path)
        await self._git_run(["clean", "-fdx"], cwd=path)

    async def _remove_worktree_disk(self, path: Path) -> None:
        # Best effort: ask git first, then nuke any leftover directory.
        await self._git_run(
            ["worktree", "remove", "--force", str(path)],
            cwd=self._repo_path,
            check=False,
        )
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)

    async def _evict(self, record: WorktreeRecord) -> None:
        async with self._locks[record.key]:
            await self._remove_worktree_disk(record.path)
            self._registry_delete(record.key)
        await self._git_run(["worktree", "prune"], cwd=self._repo_path, check=False)

    async def _git_run(
        self,
        args: Iterable[str],
        *,
        cwd: Path,
        check: bool = True,
    ) -> tuple[int, bytes, bytes]:
        argv = [self._git, *args]
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=_GIT_TIMEOUT_SECONDS
            )
        except TimeoutError as exc:
            proc.kill()
            await proc.wait()
            raise WorktreeError(f"git {' '.join(args)} timed out") from exc

        rc = proc.returncode or 0
        if check and rc != 0:
            tail = stderr_b.decode("utf-8", errors="replace").strip()[-512:]
            raise WorktreeError(f"git {' '.join(args)} exited {rc}: {tail}")
        return rc, stdout_b, stderr_b

    # --- registry helpers (sync SQLite, sub-millisecond) -------------------

    def _registry_get(self, key: str) -> WorktreeRecord | None:
        row = self._conn.execute(
            "SELECT key, path, ref, created_at, last_used_at "
            "FROM worktrees WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        return WorktreeRecord(
            key=row["key"],
            path=Path(row["path"]),
            ref=row["ref"],
            created_at=row["created_at"],
            last_used_at=row["last_used_at"],
        )

    def _registry_upsert(self, key: str, path: Path, ref: str, ts: int) -> None:
        self._conn.execute(
            "INSERT INTO worktrees (key, path, ref, created_at, last_used_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET "
            "path = excluded.path, ref = excluded.ref, last_used_at = excluded.last_used_at",
            (key, str(path), ref, ts, ts),
        )
        self._conn.commit()

    def _registry_touch(self, key: str, ts: int) -> None:
        self._conn.execute(
            "UPDATE worktrees SET last_used_at = ? WHERE key = ?",
            (ts, key),
        )
        self._conn.commit()

    def _registry_delete(self, key: str) -> None:
        self._conn.execute("DELETE FROM worktrees WHERE key = ?", (key,))
        self._conn.commit()

    def _registry_all(self) -> list[WorktreeRecord]:
        rows = self._conn.execute(
            "SELECT key, path, ref, created_at, last_used_at FROM worktrees"
        ).fetchall()
        return [
            WorktreeRecord(
                key=r["key"],
                path=Path(r["path"]),
                ref=r["ref"],
                created_at=r["created_at"],
                last_used_at=r["last_used_at"],
            )
            for r in rows
        ]

    def _registry_all_by_lru(self) -> list[WorktreeRecord]:
        rows = self._conn.execute(
            "SELECT key, path, ref, created_at, last_used_at "
            "FROM worktrees ORDER BY last_used_at ASC"
        ).fetchall()
        return [
            WorktreeRecord(
                key=r["key"],
                path=Path(r["path"]),
                ref=r["ref"],
                created_at=r["created_at"],
                last_used_at=r["last_used_at"],
            )
            for r in rows
        ]
