# Quickstart — Validating the `cabal` Refactor

**Feature**: 005-cabal-tools-polish
**Audience**: maintainer running the refactor or auditing it before merge.

## Pre-flight (run **before** any extraction)

Capture the baseline so you can diff against it after.

```bash
# 1. Component counts + env detection baseline
python setup/tools/_smoketest.py > /tmp/cabal_smoketest_before.txt 2>&1

# 2. Boot the TUI manually, hit every top-level screen, confirm no Textual error appears.
python -m cabal
#    (touch: Home → README, Init env, Update, MCP, Doctor, Restore, Local, Tools, Github device flow)

# 3. (Optional but recommended) Build the exe; confirm it boots.
python setup/build/build_exe.py
./setup/build/dist/cabal      # or cabal.exe on Windows
```

## After every extraction commit

Re-run the smoketest and diff against the baseline:

```bash
python setup/tools/_smoketest.py > /tmp/cabal_smoketest_after.txt 2>&1
diff /tmp/cabal_smoketest_before.txt /tmp/cabal_smoketest_after.txt
```

Expected diff: **empty**. If anything changed (a different number of NEW/CHANGED files, a different env probe count, an exception traceback), revert the last commit and investigate before continuing.

Run the contract test:

```bash
python -m pytest tests/contract/test_wizard_public_api.py -v
```

Expected: all assertions pass. If a Grandfathered name fails to resolve, the facade is missing a re-export.

## After all extractions complete

```bash
# 1. Smoketest — must still match baseline
python setup/tools/_smoketest.py > /tmp/cabal_smoketest_final.txt 2>&1
diff /tmp/cabal_smoketest_before.txt /tmp/cabal_smoketest_final.txt   # expect empty

# 2. Contract test — must pass
python -m pytest tests/contract/ -v

# 3. TUI parity — manual
python -m cabal                                                       # walk every screen

# 4. Built exe parity — manual
python setup/build/build_exe.py
./setup/build/dist/cabal[.exe]                                        # walk every screen

# 5. Module size check
find setup/src/cabal -name "*.py" -exec wc -l {} \; | sort -nr | head -20
#    expect: largest module < 500 LOC (or has a justification comment at the top)
#    expect: setup/src/cabal/wizard.py < 200 LOC
```

## Rollback

This refactor is reversible at any granularity:

- **Rollback last extraction**: `git revert HEAD`
- **Rollback the entire refactor**: `git revert <range>` covering every commit on `005-cabal-tools-polish` after the branch base
- **Hard reset (local only)**: `git reset --hard origin/main` — only if nothing else needs to keep

No state outside the repo changes, so rollback is a pure git operation. `~/.claude/` is unaffected.

## Smoke checklist — Part A (paste into the merge PR)

- [ ] `python setup/tools/_smoketest.py` baseline matches refactor (empty diff).
- [ ] `python -m pytest tests/contract/test_wizard_public_api.py` passes.
- [ ] `python -m cabal` boots; every screen renders; quit is clean.
- [ ] `python setup/build/build_exe.py` produces a working exe (Windows).
- [ ] `wc -l setup/src/cabal/wizard.py` < 200.
- [ ] No file under `setup/src/cabal/` exceeds 500 LOC without a justification comment at the top.
- [ ] `@code-plan-verifier` audit passes (PASS or PASS WITH WARNINGS).

---

# Part B — Init Project + Project MCP + Claude Stats Panel

Added 2026-05-28 (spec extension). Walk these scenarios manually before merge; all asserts also live as automated tests under `tests/`.

## P0 — Pre-flight (Part B)

```bash
# 1. Confirm gh is installed and authed for the "with GH templates" path
gh auth status
gh repo list --json isTemplate,name --limit 5 | python -c "import sys, json; d=json.load(sys.stdin); print(sum(1 for r in d if r['isTemplate']), 'template repos visible')"

# 2. Confirm claude CLI is installed for the "with claude" path (optional — the no-claude path must also work)
claude --version
claude -p "/status"   # see what the parser will see

# 3. Build clean test scratch dir
TEST_PARENT=$(mktemp -d)
echo "Will scaffold into $TEST_PARENT/<project-name>"
```

## P1 — Happy path: init from a GitHub template (SC-7)

```bash
python -m cabal
# Home screen: click "Init new project"
# 1. Parent folder picker: navigate to $TEST_PARENT, Select.
# 2. Project name: type "demo-init"
# 3. Template source: "GitHub" (pre-selected when gh has templates)
# 4. Pick one of your template repos from the OptionList.
# 5. Wait for the files table to populate ("Fetching template…" → table).
# 6. Optionally uncheck a row.
# 7. Click "Edit Project MCP…" → toggle on a `template`-scope server → Back.
# 8. Click Apply.
# 9. Wait for "claude finished" or the no-claude notice.

# Verify:
ls $TEST_PARENT/demo-init             # template files present
ls $TEST_PARENT/demo-init/.claude     # skills/, hooks/, agents/, settings.local.json
cat $TEST_PARENT/demo-init/.mcp.json  # contains the toggled MCP entry under "mcpServers"
cat $TEST_PARENT/demo-init/.claude/INIT_PROMPT.md   # static prompt the wizard sent
```

Expected wall time (excluding claude step): **< 10 s** for a < 5 MB template (SC-7).

## P2 — Offline fallback: no `gh`, no internet (SC-8)

```bash
# Simulate no gh
PATH=$(echo "$PATH" | sed 's|[^:]*gh[^:]*:||g') python -m cabal
# Or: chmod -x $(which gh)   # then revert with chmod +x after

# Home screen: click "Init new project"
# Template source: should auto-select "Local templates" with yellow hint
#   "No GitHub template repos available — using local templates."
# Pick "python" from the local-templates OptionList.
# Apply.

# Verify:
cat $TEST_PARENT/demo-init/CLAUDE.md         # python template
cat $TEST_PARENT/demo-init/.gitignore        # Python preset present
```

## P3 — Project MCP toggle round-trip (SC-9)

```bash
# After P1 finishes:
cd $TEST_PARENT/demo-init
claude mcp list   # the toggled server should appear with scope `project`

# Or, without running claude:
python -c "
import json, pathlib
data = json.loads(pathlib.Path('.mcp.json').read_text())
print(list(data['mcpServers']))
"

# Verify .mcp.json is gitignored (FR-17 / SC-14)
grep -c '^\.mcp\.json$' .gitignore   # expect 1 (exactly one entry)
# Re-Apply the wizard against the same project: count MUST still be 1 (idempotent)
```

Expected: the server you toggled is listed. `.gitignore` contains exactly one `.mcp.json` line — even if you only ran the offline local-template flow without toggling any MCP entry.

## P4 — Target dir exists & non-empty (SC-10)

```bash
mkdir -p $TEST_PARENT/existing-proj
echo "hi" > $TEST_PARENT/existing-proj/README.md

python -m cabal
# Init new project → parent $TEST_PARENT → name "existing-proj" → pick any template → Apply
# Expected: red status "$TEST_PARENT/existing-proj exists and is not empty — pick another name or location."
# Files in existing-proj UNCHANGED.
ls $TEST_PARENT/existing-proj         # only README.md
```

## P5 — `claude` CLI missing (SC-11)

```bash
# Hide claude from PATH then re-run P1
PATH=$(echo "$PATH" | sed 's|[^:]*claude[^:]*:||g') python -m cabal
# Run the full Init flow.
# Expected at the end: yellow status "claude CLI not installed — skipping architecture step."
# Files in $TEST_PARENT/<name>/ are still written (template + .claude/ scaffold + .mcp.json).
```

## P6 — Claude stats panel renders (SC-12 / SC-13)

```bash
# With claude installed:
python -m cabal
# Home screen → look at the panel BELOW "Env summary" / ABOVE "Global Claude Settings":
#   Account: <your-email> (Max 20x / Pro / etc.)
#   Active model: claude-opus-4-7
#   5-hour usage: NN%
#   Weekly cap: NN%
#   Token: ✓ present
# Press Ctrl+S → panel refreshes.

# With claude hidden from PATH (P5 setup):
python -m cabal
# Same panel shows: "claude CLI not installed" + email read from ~/.claude.json (if signed in)
```

Inspect the rendered text and confirm:

- [ ] No OAuth token, refresh token, or API key string appears anywhere in the panel.
- [ ] Account type is one of the recognised values OR shows `unknown` with raw `/status` output below.
- [ ] Refresh doesn't block the rest of the screen (you can still hit other buttons while it's working).

## Rollback (Part B)

Part B writes only to user-selected folders **outside this repo**. To roll back:

```bash
rm -rf $TEST_PARENT/demo-init   # delete the scaffolded project
git revert <Part B commits on 005-cabal-tools-polish>
```

`~/.claude/` is unaffected — Part B's only `~/`-touching read is `~/.claude.json` (read-only).

## Smoke checklist — Part B (paste into the merge PR)

- [ ] P1 (GitHub template happy path) succeeds; project dir has template files + `.claude/` + `.mcp.json` if MCP toggled.
- [ ] P2 (local-template fallback with no gh) succeeds; CLAUDE.md + `.gitignore` written.
- [ ] P3 (Project MCP round-trip) — `claude mcp list` shows the entry under scope `project`; `.gitignore` contains exactly one `.mcp.json` line; re-running Apply does NOT append a duplicate.
- [ ] P4 (non-empty target dir refusal) — wizard refuses; existing files untouched.
- [ ] P5 (no-claude fallback) — files written; yellow "skipping architecture step" message; no error.
- [ ] P6 (stats panel) — renders on launch; never shows a token value; refresh button works.
- [ ] `pytest tests/unit tests/integration` passes.
- [ ] `@code-plan-verifier` audit on Part B changes passes.
