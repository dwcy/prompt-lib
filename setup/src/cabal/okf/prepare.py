"""Bundle export + index freshness orchestration keyed on a content fingerprint."""

from __future__ import annotations

from pathlib import Path

from cabal.okf.exporter import export_okf
from cabal.okf.index import SCHEMA_VERSION, bundle_fingerprint, build_index, connect


def _stored_fingerprint(db_path: Path) -> str | None:
    """Return the persisted bundle_fingerprint metadata value, or None if db/schema/row is absent."""
    if not Path(db_path).exists():
        return None
    try:
        with connect(db_path) as conn:
            row = conn.execute("SELECT value FROM metadata WHERE key = 'schema_version'").fetchone()
            if row is None or row["value"] != SCHEMA_VERSION:
                return None
            fp_row = conn.execute("SELECT value FROM metadata WHERE key = 'bundle_fingerprint'").fetchone()
            return fp_row["value"] if fp_row is not None else None
    except Exception:
        return None


def ensure_fresh_index(
    bundle_root: Path,
    db_path: Path,
    *,
    repo_root: Path | None = None,
    force: bool = False,
) -> tuple[Path, str, bool]:
    """Export the bundle if missing, then rebuild the index only if its fingerprint changed or force=True."""
    bundle_root = Path(bundle_root)
    db_path = Path(db_path)
    exported = False
    graph = bundle_root / "graph.json"
    if not graph.exists():
        export_okf(repo_root or Path.cwd(), bundle_root)
        exported = True

    current_fingerprint = bundle_fingerprint(bundle_root)
    previous_fingerprint = _stored_fingerprint(db_path)

    if not force and previous_fingerprint == current_fingerprint:
        prefix = "Exported bundle; index" if exported else "Index"
        return db_path, f"{prefix} already up to date at `{db_path}`.", False

    build_index(bundle_root, db_path)
    if force:
        reason = "forced rebuild"
    elif previous_fingerprint is None:
        reason = "no prior index"
    else:
        reason = "bundle changed"
    prefix = "Exported bundle and rebuilt" if exported else "Rebuilt"
    return db_path, f"{prefix} OKF index at `{db_path}` ({reason}).", True
