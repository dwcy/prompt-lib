"""Smoke test for the cabal wizard — non-interactive.

Adds `setup/src/` to sys.path so the test runs against the source tree
regardless of whether the wheel is installed. Verifies the core helpers
(`detect_env`, `find_env_vars`, `diff_component`) work without raising.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "setup" / "src"))

from cabal import wizard as m  # noqa: E402

print("import OK")
print(f"Components: {len(m.COMPONENTS)}")

env = m.detect_env()
print(f"OS: {env['os']} | git: {env['git']} | bash: {env['bash']}")

evars = m.find_env_vars(m.GLOBAL_DIR / "settings.json")
print(f"Env vars in settings.json: {evars}")

for c in m.COMPONENTS:
    statuses = m.diff_component(c)
    new = sum(1 for s in statuses if s.state == "NEW")
    chg = sum(1 for s in statuses if s.state == "CHANGED")
    unc = sum(1 for s in statuses if s.state == "UNCHANGED")
    print(f"  {c.label:25} new={new:3} changed={chg:3} unchanged={unc:3}")
