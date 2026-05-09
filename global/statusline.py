import sys
import json
import subprocess
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def rgb(text, r, g, b):
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"


def hyperlink(text, url):
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def ctx_color(pct):
    if pct < 50:
        return (100, 220, 120)
    elif pct < 75:
        return (255, 200, 50)
    elif pct < 90:
        return (255, 140, 30)
    else:
        return (255, 80, 80)


def dotnet_test_status(cwd: Path):
    results_dir = cwd / "TestResults"
    if not results_dir.is_dir():
        return None
    trx_files = list(results_dir.glob("*.trx")) + list(results_dir.glob("*/*.trx"))
    if not trx_files:
        return None
    latest = max(trx_files, key=lambda f: f.stat().st_mtime)
    try:
        import xml.etree.ElementTree as ET
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


def jest_test_status(cwd: Path):
    summary = cwd / "coverage" / "coverage-summary.json"
    if not summary.exists():
        return None
    try:
        with open(summary) as f:
            data = json.load(f)
        total = data.get("total", {})
        lines_pct = total.get("lines", {}).get("pct", 100)
        if lines_pct >= 80:
            return rgb(f"✓ {lines_pct:.0f}%cov", 100, 220, 120)
        return rgb(f"◑ {lines_pct:.0f}%cov", 255, 200, 50)
    except Exception:
        return None


data = json.load(sys.stdin)

model = data.get("model", {}).get("display_name", "Claude")
session = data.get("session_name") or ""
used = data.get("context_window", {}).get("used_percentage")
cwd_str = data.get("workspace", {}).get("current_dir") or None

ctx_pct = round(used) if used is not None else None
ctx_str = f"{ctx_pct}%" if ctx_pct is not None else "--"

branch = ""
try:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True, text=True, timeout=1,
        cwd=cwd_str,
    )
    branch = result.stdout.strip()
except Exception:
    pass

cwd = Path(cwd_str) if cwd_str else None

# Docker
docker_present = cwd and any(
    (cwd / f).exists()
    for f in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")
)

# Test status — dotnet first, jest fallback
test_status = None
if cwd:
    test_status = dotnet_test_status(cwd) or jest_test_status(cwd)

# Agent state from Claude Code runtime fields (gracefully absent = idle)
tools_in_flight = data.get("tools_in_flight") or []
is_streaming = data.get("is_streaming") or False

agent_state = None
if tools_in_flight:
    names = {t.get("name", "") if isinstance(t, dict) else str(t) for t in tools_in_flight}
    if names & {"Grep", "Glob", "Read", "Explore"}:
        agent_state = rgb("🤖 indexing…", 140, 200, 255)
    elif names & {"EnterPlanMode", "Plan"}:
        agent_state = rgb("🧠 planning…", 220, 180, 255)
    elif names & {"Write", "Edit", "NotebookEdit"}:
        agent_state = rgb("✏️  writing…", 255, 220, 100)
    elif names & {"Bash", "PowerShell"}:
        agent_state = rgb("⚡ running…", 255, 180, 80)
    elif names & {"Agent"}:
        agent_state = rgb("🤖 agent…", 180, 255, 180)
    else:
        agent_state = rgb("⚙️  working…", 200, 200, 200)
elif is_streaming:
    agent_state = rgb("💬 thinking…", 150, 220, 255)

NA = rgb("N/A", 100, 100, 120)
SEP = rgb("  │  ", 70, 70, 90)

parts = [
    rgb(f"✦ {model}", 139, 196, 255),
    rgb(f"◐ {ctx_str}", *ctx_color(ctx_pct or 0)),
    rgb(f"⎇ {branch}", 255, 200, 80) if branch else rgb("⎇ N/A", 100, 100, 120),
    rgb("🐳 docker", 41, 182, 246) if docker_present else rgb("🐳 N/A", 100, 100, 120),
    test_status if test_status else rgb("✓ N/A", 100, 100, 120),
    agent_state if agent_state else rgb("⚙️  idle", 100, 100, 120),
    hyperlink(rgb(f"⊙ {cwd_str}", 200, 150, 255), f"vscode://file/{cwd_str.replace(chr(92), '/')}") if cwd_str else rgb("⊙ N/A", 100, 100, 120),
]

print(SEP.join(parts))
