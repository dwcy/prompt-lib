"""Smoke test for apply.py — non-interactive."""
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("apply", Path(__file__).resolve().parent.parent / "apply.py")
m = importlib.util.module_from_spec(spec)
sys.modules["apply"] = m
spec.loader.exec_module(m)

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
