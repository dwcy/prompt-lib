"""Unit tests for ``orchestrator.worktree.WorktreeManager``.

The manager shells out to a real ``git`` binary, so each test sets up a tiny
two-repo fixture — a bare ``origin.git`` plus a working clone — under
``tmp_path``. ``main`` is committed to both so ``git fetch origin main`` is a
real, side-effect-free operation.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from orchestrator import eventlog
from orchestrator.worktree import WorktreeError, WorktreeManager

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def git_repo(tmp_path: Path) -> Iterator[Path]:
    """Yield a working clone whose ``origin`` is a bare repo with one commit on
    ``main``. The clone is what ``WorktreeManager.repo_path`` should point at.
    """
    if shutil.which("git") is None:  # pragma: no cover
        pytest.skip("git not available on PATH")

    origin = tmp_path / "origin.git"
    work = tmp_path / "work"

    _run_git(tmp_path, ["init", "--bare", "--initial-branch=main", str(origin)])
    _run_git(tmp_path, ["clone", str(origin), str(work)])

    _run_git(work, ["config", "user.email", "test@example.com"])
    _run_git(work, ["config", "user.name", "Test"])
    (work / "README.md").write_text("hello\n", encoding="utf-8")
    _run_git(work, ["add", "README.md"])
    _run_git(work, ["commit", "-m", "initial"])
    _run_git(work, ["branch", "-M", "main"])
    _run_git(work, ["push", "-u", "origin", "main"])

    yield work


@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "events.db"
    eventlog.bootstrap(db_path)
    connection = eventlog.connect(db_path)
    try:
        yield connection
    finally:
        connection.close()


def _run_git(cwd: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


# ---------------------------------------------------------------------------
# acquire — happy paths
# ---------------------------------------------------------------------------


async def test_acquire_FirstCallForKey_CreatesWorktreeOnDisk(
    git_repo: Path, conn, tmp_path: Path
) -> None:
    root = tmp_path / "wts"
    manager = WorktreeManager(repo_path=git_repo, root=root, conn=conn)

    async with manager.acquire(key="pr-1", ref="main") as path:
        assert path == root / "pr-1"

    assert (root / "pr-1").is_dir()
    assert (root / "pr-1" / "README.md").exists()


async def test_acquire_SecondCallForSameKey_ReusesDirectoryAndRefreshes(
    git_repo: Path, conn, tmp_path: Path
) -> None:
    root = tmp_path / "wts"
    manager = WorktreeManager(repo_path=git_repo, root=root, conn=conn)

    async with manager.acquire(key="pr-1", ref="main") as first_path:
        (first_path / "scratch.txt").write_text("dirty", encoding="utf-8")

    async with manager.acquire(key="pr-1", ref="main") as second_path:
        assert second_path == first_path
        assert not (second_path / "scratch.txt").exists()


async def test_acquire_DifferentKeys_RunInParallel(
    git_repo: Path, conn, tmp_path: Path
) -> None:
    root = tmp_path / "wts"
    manager = WorktreeManager(repo_path=git_repo, root=root, conn=conn)

    barrier = asyncio.Event()
    inside_count = 0

    async def hold(key: str) -> None:
        nonlocal inside_count
        async with manager.acquire(key=key, ref="main"):
            inside_count += 1
            await barrier.wait()

    task_a = asyncio.create_task(hold("pr-1"))
    task_b = asyncio.create_task(hold("pr-2"))

    for _ in range(50):
        if inside_count == 2:
            break
        await asyncio.sleep(0.05)

    assert inside_count == 2
    barrier.set()
    await asyncio.gather(task_a, task_b)


async def test_acquire_SameKeyTwice_Serializes(
    git_repo: Path, conn, tmp_path: Path
) -> None:
    root = tmp_path / "wts"
    manager = WorktreeManager(repo_path=git_repo, root=root, conn=conn)

    enter_order: list[int] = []
    release_a = asyncio.Event()

    async def first() -> None:
        async with manager.acquire(key="pr-1", ref="main"):
            enter_order.append(1)
            await release_a.wait()

    async def second() -> None:
        async with manager.acquire(key="pr-1", ref="main"):
            enter_order.append(2)

    task_a = asyncio.create_task(first())
    await asyncio.sleep(0.1)
    task_b = asyncio.create_task(second())
    await asyncio.sleep(0.2)

    assert enter_order == [1]
    release_a.set()
    await asyncio.gather(task_a, task_b)
    assert enter_order == [1, 2]


# ---------------------------------------------------------------------------
# acquire — failure paths
# ---------------------------------------------------------------------------


async def test_acquire_InvalidKey_RaisesWorktreeError(
    git_repo: Path, conn, tmp_path: Path
) -> None:
    manager = WorktreeManager(repo_path=git_repo, root=tmp_path / "wts", conn=conn)

    with pytest.raises(WorktreeError):
        async with manager.acquire(key="../escape", ref="main"):
            pass


async def test_acquire_EmptyRef_RaisesWorktreeError(
    git_repo: Path, conn, tmp_path: Path
) -> None:
    manager = WorktreeManager(repo_path=git_repo, root=tmp_path / "wts", conn=conn)

    with pytest.raises(WorktreeError):
        async with manager.acquire(key="pr-1", ref=""):
            pass


# ---------------------------------------------------------------------------
# reconcile
# ---------------------------------------------------------------------------


async def test_reconcile_RegistryRowWithMissingPath_IsDropped(
    git_repo: Path, conn, tmp_path: Path
) -> None:
    root = tmp_path / "wts"
    manager = WorktreeManager(repo_path=git_repo, root=root, conn=conn)

    async with manager.acquire(key="pr-1", ref="main") as path:
        recorded_path = path
    shutil.rmtree(recorded_path)

    await manager.reconcile()

    rows = conn.execute("SELECT key FROM worktrees").fetchall()
    assert rows == []


async def test_reconcile_OrphanDirectoryNotInRegistry_IsRemoved(
    git_repo: Path, conn, tmp_path: Path
) -> None:
    root = tmp_path / "wts"
    manager = WorktreeManager(repo_path=git_repo, root=root, conn=conn)
    root.mkdir(parents=True)
    orphan = root / "pr-orphan"
    orphan.mkdir()
    (orphan / "leftover.txt").write_text("x", encoding="utf-8")

    await manager.reconcile()

    assert not orphan.exists()


# ---------------------------------------------------------------------------
# prune
# ---------------------------------------------------------------------------


async def test_prune_MaxCountTwo_EvictsLeastRecentlyUsed(
    git_repo: Path, conn, tmp_path: Path
) -> None:
    root = tmp_path / "wts"
    manager = WorktreeManager(repo_path=git_repo, root=root, conn=conn)

    async with manager.acquire(key="pr-1", ref="main"):
        pass
    conn.execute(
        "UPDATE worktrees SET last_used_at = ? WHERE key = ?",
        (int(time.time()) - 300, "pr-1"),
    )
    conn.commit()
    async with manager.acquire(key="pr-2", ref="main"):
        pass
    conn.execute(
        "UPDATE worktrees SET last_used_at = ? WHERE key = ?",
        (int(time.time()) - 200, "pr-2"),
    )
    conn.commit()
    async with manager.acquire(key="pr-3", ref="main"):
        pass

    evicted = await manager.prune(max_count=2, max_age_days=365)

    assert evicted == 1
    keys = {row["key"] for row in conn.execute("SELECT key FROM worktrees").fetchall()}
    assert keys == {"pr-2", "pr-3"}
    assert not (root / "pr-1").exists()


async def test_prune_OlderThanMaxAge_IsEvictedRegardlessOfCount(
    git_repo: Path, conn, tmp_path: Path
) -> None:
    root = tmp_path / "wts"
    manager = WorktreeManager(repo_path=git_repo, root=root, conn=conn)

    async with manager.acquire(key="pr-old", ref="main"):
        pass
    conn.execute(
        "UPDATE worktrees SET last_used_at = ? WHERE key = ?",
        (int(time.time()) - 30 * 86400, "pr-old"),
    )
    conn.commit()

    evicted = await manager.prune(max_count=10, max_age_days=14)

    assert evicted == 1
    assert not (root / "pr-old").exists()
