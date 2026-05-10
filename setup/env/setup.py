#!/usr/bin/env python3
import json
import platform
import re
import shutil
import subprocess
from pathlib import Path


def load_env(env_file):
    with open(env_file) as f:
        return {k: str(v) for k, v in json.load(f).items() if str(v).strip()}


def apply_git_line_endings(mode):
    """Apply GIT_LINE_ENDINGS via `git config --global core.autocrlf`."""
    if mode == 'auto':
        mode = 'true' if platform.system() == 'Windows' else 'input'
    if mode not in ('true', 'input', 'false'):
        print(f"  Skipping GIT_LINE_ENDINGS={mode!r}: expected auto/true/input/false")
        return
    if not shutil.which('git'):
        print("  git not on PATH; skipping core.autocrlf")
        return
    result = subprocess.run(['git', 'config', '--global', 'core.autocrlf', mode],
                            capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  git config --global core.autocrlf {mode}")
    else:
        print(f"  git config failed: {result.stderr.strip()}")


def update_profile(profile_path, keys, export_lines):
    path = Path(profile_path).expanduser()
    if not path.exists():
        return
    with open(path) as f:
        lines = f.readlines()
    pat = re.compile(r'^export (' + '|'.join(re.escape(k) for k in keys) + r')=')
    lines = [l for l in lines if not pat.match(l) and l.strip() != '# claude-code-env']
    with open(path, 'w') as f:
        f.writelines(lines)
        f.write('# claude-code-env\n')
        for line in export_lines:
            f.write(line + '\n')
    print(f"  Updated {path}")


def main():
    script_dir = Path(__file__).parent
    env_file = script_dir / 'setup.env.json'

    if not env_file.exists():
        print(f"Error: {env_file} not found.")
        raise SystemExit(1)

    env = load_env(env_file)
    if not env:
        print("No values set in setup.env.json. Fill in the values and re-run.")
        raise SystemExit(0)

    export_lines = [f"export {k}={repr(v)}" for k, v in env.items()]

    for profile in ['~/.bashrc', '~/.zshrc', '~/.profile']:
        update_profile(profile, list(env.keys()), export_lines)

    if platform.system() == 'Windows':
        for k, v in env.items():
            result = subprocess.run(['setx', k, v], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  setx {k}")

    if 'GIT_LINE_ENDINGS' in env:
        apply_git_line_endings(env['GIT_LINE_ENDINGS'])

    print("\nDone. Restart your terminal for changes to take effect.")


if __name__ == '__main__':
    main()
