import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

STATE_FILE = Path.home() / ".claude" / ".session_state.json"
SUBAGENT_FILE = Path.home() / ".claude" / ".subagent_state.json"
SUBAGENT_TTL = 1800  # ignore a "running" state older than 30 min (stale/never-stopped)
UPDATE_FILE = Path.home() / ".claude" / ".update_state.json"
UPDATE_TTL = 6 * 3600
UPDATE_CHECKER = Path.home() / ".claude" / "hooks" / "check_claude_update.py"


def rgb(text, r, g, b):
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"


def hyperlink(text, url):
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def ctx_color(pct):
    if pct < 50:
        return (100, 220, 120)
    if pct < 75:
        return (255, 200, 50)
    if pct < 90:
        return (255, 140, 30)
    return (255, 80, 80)


def cost_color(usd):
    if usd < 1:
        return (100, 220, 120)
    if usd < 3:
        return (255, 200, 50)
    if usd < 10:
        return (255, 140, 30)
    return (255, 80, 80)


def headroom_color(pct):
    if pct > 50:
        return (100, 220, 120)
    if pct > 25:
        return (255, 200, 50)
    return (255, 80, 80)


def git(args, cwd):
    try:
        r = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=1,
            cwd=cwd,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


# === segment builders ===


def seg_model(data):
    name = data.get("model", {}).get("display_name") or "Claude"
    return rgb(f"✦ {name}", 139, 196, 255)


def seg_thinking(data):
    """Show the configured thinking/effort mode from settings.json. Hidden if unknown."""
    try:
        cfg = json.loads(
            (Path.home() / ".claude" / "settings.json").read_text(encoding="utf-8")
        )
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if cfg.get("fastMode"):
        return rgb("⚡ fast", 255, 180, 80)
    if cfg.get("alwaysThinkingEnabled") is False:
        return rgb("🧠 off", 100, 100, 120)
    effort = cfg.get("effortLevel")
    if effort:
        return rgb(f"🧠 {effort}", 180, 220, 255)
    return None


def _maybe_refresh_update_cache():
    try:
        if (
            UPDATE_FILE.exists()
            and (time.time() - UPDATE_FILE.stat().st_mtime) < UPDATE_TTL
        ):
            return
        if not UPDATE_CHECKER.exists():
            return
        kwargs = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(["python", str(UPDATE_CHECKER)], **kwargs)
    except Exception:
        pass


def _parse_ver(v):
    return tuple(int(p) for p in re.findall(r"\d+", v or "")[:3])


def seg_update(data):
    _maybe_refresh_update_cache()
    current = data.get("version")
    if not current or not UPDATE_FILE.exists():
        return None
    try:
        with UPDATE_FILE.open(encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        return None
    latest = state.get("latest")
    if not latest or latest == current:
        return None
    # Only surface major/minor bumps (2.1.x → 2.2.0); ignore patch-only churn.
    if _parse_ver(current)[:2] == _parse_ver(latest)[:2]:
        return None
    return rgb(f"⬆ {latest}", 255, 180, 80)


def seg_ctx_or_warn(data):
    used = data.get("context_window", {}).get("used_percentage")
    if used is not None:
        pct = round(used)
        return rgb(f"◐ {pct}%", *ctx_color(pct))
    if data.get("exceeds_200k_tokens"):
        return rgb("⚠ 200k+", 255, 80, 80)
    return rgb("◐ --", 100, 100, 120)


def seg_cost(data):
    usd = data.get("total_cost_usd")
    if usd is None:
        usd = (
            data.get("cost", {}).get("total_cost_usd")
            if isinstance(data.get("cost"), dict)
            else None
        )
    if usd is None:
        return None
    return rgb(f"${usd:.2f}", *cost_color(usd))


def seg_diff(data):
    added = data.get("total_lines_added") or 0
    removed = data.get("total_lines_removed") or 0
    if not isinstance(data.get("cost"), dict):
        pass
    else:
        added = added or data["cost"].get("total_lines_added") or 0
        removed = removed or data["cost"].get("total_lines_removed") or 0
    if added == 0 and removed == 0:
        return None
    plus = rgb(f"+{added}", 100, 220, 120)
    minus = rgb(f"-{removed}", 255, 120, 120)
    return f"{rgb('Δ', 180, 180, 200)} {plus} {minus}"


def seg_output_style(data):
    name = (
        data.get("output_style", {}).get("name")
        if isinstance(data.get("output_style"), dict)
        else None
    )
    if not name or name.lower() in ("default", ""):
        return None
    return rgb(f"📝 {name}", 140, 220, 220)


def _quota_pct(obj):
    if not isinstance(obj, dict):
        return None
    for k in ("used_percentage", "pct_used", "percent_used"):
        v = obj.get(k)
        if isinstance(v, (int, float)):
            return float(v) / 100 if v > 1 else float(v)
    used, total = obj.get("used"), obj.get("total") or obj.get("limit")
    if isinstance(used, (int, float)) and isinstance(total, (int, float)) and total > 0:
        return used / total
    if isinstance(used, (int, float)) and 0 <= used <= 1:
        return used
    return None


def seg_ratelimit(data):
    pieces = []
    for label, key in (("5h", "five_hour"), ("7d", "seven_day")):
        used_frac = _quota_pct(data.get(key))
        if used_frac is None:
            continue
        headroom = max(0, round((1 - used_frac) * 100))
        if headroom > 90:
            continue
        pieces.append(rgb(f"{label}:{headroom}%", *headroom_color(headroom)))
    if not pieces:
        return None
    return rgb("⏳ ", 200, 200, 220) + " ".join(pieces)


def seg_cwd(data):
    cwd_str = data.get("workspace", {}).get("current_dir") or data.get("cwd")
    if not cwd_str:
        return rgb("⊙ N/A", 100, 100, 120)
    url = f"vscode://file/{cwd_str.replace(chr(92), '/')}"
    return rgb(hyperlink(f"⊙ {cwd_str}", url), 200, 150, 255)


def seg_branch(cwd):
    branch = git(["branch", "--show-current"], cwd)
    if not branch:
        return rgb("⎇ N/A", 100, 100, 120), None
    out = git(["rev-parse", "--git-dir", "--git-common-dir"], cwd)
    is_worktree = False
    if out:
        lines = out.splitlines()
        if len(lines) == 2:
            # Resolve both against cwd before comparing — git returns
            # absolute git-dir but relative common-dir when invoked from a
            # subdirectory, which would falsely flag the main checkout as a
            # linked worktree.
            base = Path(cwd) if cwd else Path.cwd()
            resolved = [str((base / p).resolve()) for p in lines]
            is_worktree = resolved[0] != resolved[1]
    body = rgb(f"⎇ {branch}", 255, 200, 80)
    if is_worktree:
        body = rgb("🌳 worktree: ", 100, 220, 120) + body
    return body, branch


def seg_ahead_behind(cwd):
    out = git(["rev-list", "--count", "--left-right", "@{u}...HEAD"], cwd)
    if not out:
        return None
    parts = out.split()
    if len(parts) != 2:
        return None
    behind, ahead = int(parts[0]), int(parts[1])
    if ahead == 0 and behind == 0:
        return rgb("↕ sync", 100, 220, 120)
    bits = []
    if ahead:
        bits.append(rgb(f"↑{ahead}", 100, 220, 120))
    if behind:
        bits.append(rgb(f"↓{behind}", 255, 180, 80))
    return " ".join(bits)


def seg_uncommitted(cwd):
    out = git(["status", "--porcelain"], cwd)
    if out is None:
        return None
    lines = [l for l in out.splitlines() if l.strip()]
    if not lines:
        return None
    n = len(lines)
    return rgb(f"±{n} {'file' if n == 1 else 'files'}", 255, 200, 80)


def seg_stash(cwd):
    out = git(["stash", "list"], cwd)
    if not out:
        return None
    count = len([l for l in out.splitlines() if l.strip()])
    if count == 0:
        return None
    return rgb(f"⚑ {count}", 200, 150, 255)


def seg_docker(cwd):
    if not cwd:
        return rgb("🐳 N/A", 100, 100, 120)
    p = Path(cwd)
    present = any(
        (p / f).exists()
        for f in (
            "Dockerfile",
            "docker-compose.yml",
            "docker-compose.yaml",
            "compose.yml",
            "compose.yaml",
        )
    )
    return rgb("🐳 docker", 41, 182, 246) if present else rgb("🐳 N/A", 100, 100, 120)


def _dotnet_tests(cwd):
    results = Path(cwd) / "TestResults"
    if not results.is_dir():
        return None
    trx = list(results.glob("*.trx")) + list(results.glob("*/*.trx"))
    if not trx:
        return None
    latest = max(trx, key=lambda f: f.stat().st_mtime)
    try:
        root = ET.parse(latest).getroot()
        ns = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
        c = root.find(".//t:ResultSummary/t:Counters", ns)
        if c is None:
            return None
        passed = int(c.get("passed", 0))
        failed = int(c.get("failed", 0))
        total = passed + failed
        if failed:
            return rgb(f"✗ {failed}/{total}", 255, 80, 80)
        return rgb(f"✓ {total}", 100, 220, 120)
    except Exception:
        return None


def _pytest_tests(cwd):
    cache = Path(cwd) / ".pytest_cache" / "v" / "cache"
    nodeids_file = cache / "nodeids"
    lastfailed_file = cache / "lastfailed"
    if not nodeids_file.exists():
        return None
    base = Path(cwd)
    _seen = {}

    def _live(nodeid):
        # pytest's cache only ever grows: `nodeids` is the union of every id ever
        # collected and `lastfailed` only clears an id when that exact id runs and
        # passes. So a deleted or moved test file leaves ghost ids that inflate the
        # count forever (until `pytest --cache-clear`). Drop ids whose file is gone.
        rel = nodeid.split("::", 1)[0]
        if rel not in _seen:
            _seen[rel] = (base / rel).exists()
        return _seen[rel]

    try:
        with nodeids_file.open(encoding="utf-8") as f:
            ids = [l.strip() for l in f if l.strip()]
        if not ids:
            return None
        live_ids = [i for i in ids if _live(i)]
        # If nothing resolves (e.g. pytest rootdir differs from cwd), the path
        # check is misaligned — fall back to raw counts rather than hide the segment.
        use_filter = bool(live_ids)
        total = len(live_ids) if use_filter else len(ids)
        failed = 0
        if lastfailed_file.exists():
            with lastfailed_file.open(encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                failed = sum(1 for nid in data if not use_filter or _live(nid))
        if failed:
            return rgb(f"✗ {failed}/{total}", 255, 80, 80)
        return rgb(f"✓ {total}", 100, 220, 120)
    except Exception:
        return None


def _jest_tests(cwd):
    summary = Path(cwd) / "coverage" / "coverage-summary.json"
    if not summary.exists():
        return None
    try:
        with summary.open(encoding="utf-8") as f:
            data = json.load(f)
        pct = data.get("total", {}).get("lines", {}).get("pct", 100)
        if pct >= 80:
            return rgb(f"✓ {pct:.0f}%cov", 100, 220, 120)
        return rgb(f"◑ {pct:.0f}%cov", 255, 200, 50)
    except Exception:
        return None


def _playwright_tests(cwd):
    p = Path(cwd)
    for rel in ("test-results/results.json", "playwright-report/results.json"):
        path = p / rel
        if not path.exists():
            continue
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            stats = data.get("stats") or {}
            expected = stats.get("expected", 0)
            unexpected = stats.get("unexpected", 0)
            flaky = stats.get("flaky", 0)
            total = expected + unexpected + flaky
            if total == 0:
                continue
            if unexpected:
                return rgb(f"✗ {unexpected}/{total}", 255, 80, 80)
            return rgb(f"✓ {total}", 100, 220, 120)
        except Exception:
            continue
    return None


def seg_tests(cwd):
    if not cwd:
        return rgb("🧪 N/A", 100, 100, 120)
    result = (
        _dotnet_tests(cwd)
        or _pytest_tests(cwd)
        or _jest_tests(cwd)
        or _playwright_tests(cwd)
    )
    if result is None:
        return rgb("🧪 N/A", 100, 100, 120)
    return rgb("🧪 ", 180, 180, 200) + result


_SPEC_BRANCH_RE = re.compile(r"^(\d{3,}-[a-z0-9][a-z0-9-]*)")
_PHASE_RE = re.compile(r"^##\s+Phase\s+(\d+)\b", re.IGNORECASE)
_STATUS_RE = re.compile(r"\*\*Status\*\*:\s*([⬜🟡✅])[^()]*\((\d+)\s*/\s*(\d+)")


def seg_speckit(cwd, branch):
    if not cwd or not branch:
        return None
    m = _SPEC_BRANCH_RE.match(branch)
    if not m:
        return None
    spec_id = m.group(1)
    tasks = Path(cwd) / "specs" / spec_id / "tasks.md"
    if not tasks.exists():
        return None
    try:
        with tasks.open(encoding="utf-8") as f:
            phases = []
            current_phase = None
            for line in f:
                pm = _PHASE_RE.match(line)
                if pm:
                    current_phase = int(pm.group(1))
                    continue
                if current_phase is None:
                    continue
                sm = _STATUS_RE.search(line)
                if sm:
                    phases.append(
                        (current_phase, sm.group(1), int(sm.group(2)), int(sm.group(3)))
                    )
                    current_phase = None
    except Exception:
        return None
    if not phases:
        return None
    for phase, emoji, done, total in phases:
        if emoji != "✅":
            return rgb(f"🎯 P{phase} {done}/{total}", 255, 200, 80)
    return rgb("🎯 ✓ all", 100, 220, 120)


def seg_subagent(data):
    """Show the currently-running subagent (name + model) from .subagent_state.json."""
    if not SUBAGENT_FILE.exists():
        return None
    try:
        st = json.loads(SUBAGENT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not st.get("running"):
        return None
    started = st.get("started_at") or 0
    if started and (time.time() - started) > SUBAGENT_TTL:
        return None
    sid = data.get("session_id")
    if sid and st.get("session_id") and st.get("session_id") != sid:
        return None
    name = st.get("name") or "subagent"
    model = st.get("model")
    label = f"🤖 {name}" + (f" ({model})" if model else "")
    return rgb(label, 180, 255, 180)


def seg_activity(session_id):
    if not STATE_FILE.exists():
        return None
    try:
        with STATE_FILE.open(encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        return None
    if session_id and state.get("session_id") != session_id:
        return None
    agents = state.get("agent_count", 0)
    tools = state.get("tool_count", 0)
    if agents == 0 and tools == 0:
        return None
    return f"{rgb(f'🤖 {agents}', 180, 255, 180)} · {rgb(f'🛠 {tools}', 200, 200, 200)}"


# === layout (key → builder + which segments render, in what order) ===

SEGMENTS_META = Path(__file__).resolve().parent / "statusline-segments.json"
LAYOUT_CONFIG = Path.home() / ".claude" / "statusline-config.json"

# key → builder(ctx) -> segment string or None. ctx carries the parsed stdin
# payload plus the resolved cwd / session_id / branch the git segments need.
BUILDERS = {
    "model": lambda c: seg_model(c["data"]),
    "thinking": lambda c: seg_thinking(c["data"]),
    "update": lambda c: seg_update(c["data"]),
    "context": lambda c: seg_ctx_or_warn(c["data"]),
    "cost": lambda c: seg_cost(c["data"]),
    "diff": lambda c: seg_diff(c["data"]),
    "output_style": lambda c: seg_output_style(c["data"]),
    "ratelimit": lambda c: seg_ratelimit(c["data"]),
    "cwd": lambda c: seg_cwd(c["data"]),
    "branch": lambda c: seg_branch(c["cwd"])[0],
    "ahead_behind": lambda c: seg_ahead_behind(c["cwd"]),
    "uncommitted": lambda c: seg_uncommitted(c["cwd"]),
    "stash": lambda c: seg_stash(c["cwd"]),
    "docker": lambda c: seg_docker(c["cwd"]),
    "tests": lambda c: seg_tests(c["cwd"]),
    "speckit": lambda c: seg_speckit(c["cwd"], c["branch"]),
    "subagent": lambda c: seg_subagent(c["data"]),
    "activity": lambda c: seg_activity(c["session_id"]),
}


def _load_layout():
    """Ordered [{key, enabled, row}] from user config, else bundled defaults, else built-in."""
    for path in (LAYOUT_CONFIG, SEGMENTS_META):
        try:
            if path.exists():
                segs = json.loads(path.read_text(encoding="utf-8")).get("segments")
                if isinstance(segs, list) and segs:
                    return segs
        except Exception:
            continue
    # Built-in fallback: every known segment, declared order, row 1.
    return [{"key": k, "enabled": True, "row": 1} for k in BUILDERS]


# === main ===

data = json.load(sys.stdin)
cwd_str = data.get("workspace", {}).get("current_dir") or data.get("cwd")
session_id = data.get("session_id")
branch = git(["branch", "--show-current"], cwd_str)

ctx = {"data": data, "cwd": cwd_str, "session_id": session_id, "branch": branch}

SEP = rgb("  │  ", 70, 70, 90)

rows = {1: [], 2: []}
for seg in _load_layout():
    if not isinstance(seg, dict) or not seg.get("enabled", True):
        continue
    fn = BUILDERS.get(seg.get("key"))
    if fn is None:
        continue
    try:
        rendered = fn(ctx)
    except Exception:
        rendered = None
    if rendered:
        rows[2 if seg.get("row") == 2 else 1].append(rendered)

print(SEP.join(rows[1]))
print(SEP.join(rows[2]))
