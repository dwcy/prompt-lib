#!/usr/bin/env bash
# apply-global-claude-settings.sh
# Non-interactive fallback: copies <repo>/global/ into ~/.claude
# Run from Git Bash:
#   bash setup/tools/apply-global-claude-settings.sh
# or from anywhere:
#   bash /path/to/prompt-lib/setup/tools/apply-global-claude-settings.sh

set -euo pipefail

# Script lives in setup/tools/ — global/ is at <repo>/global/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../global" && pwd)"
TARGET="$HOME/.claude"

echo "Applying global Claude settings..."
echo "  Source : $SCRIPT_DIR"
echo "  Target : $TARGET"
echo ""

# Backup existing settings.json before overwriting
if [ -f "$TARGET/settings.json" ]; then
  cp "$TARGET/settings.json" "$TARGET/settings.json.bak"
  echo "  Backed up existing settings.json -> settings.json.bak"
fi

# Copy settings.json with two transforms:
#   1. Strip dead `mcpServers` / `mcpServersDisabled` (Claude Code does NOT read MCP from
#      settings.json — `claude mcp add` writes the real config to `~/.claude.json`).
#   2. On non-Windows shells, swap $USERPROFILE -> $HOME so hook command paths resolve.
SRC="$SCRIPT_DIR/settings.json" DST="$TARGET/settings.json" OS_NAME="$(uname -s)" python -c '
import json, os
from pathlib import Path
src = Path(os.environ["SRC"])
dst = Path(os.environ["DST"])
data = json.loads(src.read_text(encoding="utf-8"))
data.pop("mcpServers", None)
data.pop("mcpServersDisabled", None)
text = json.dumps(data, indent=2) + "\n"
os_name = os.environ.get("OS_NAME", "")
if not (os_name.startswith("MINGW") or os_name.startswith("MSYS") or os_name.startswith("CYGWIN")):
    text = text.replace("$USERPROFILE", "$HOME")
dst.write_text(text, encoding="utf-8")
'
echo "  Copied  settings.json (mcpServers stripped; \$USERPROFILE translated on non-Windows)"

# Copy agents
mkdir -p "$TARGET/agents"
cp "$SCRIPT_DIR/agents/"*.md "$TARGET/agents/"
echo "  Copied  agents/ ($(ls "$SCRIPT_DIR/agents/"*.md | wc -l) files)"

# Copy hooks (skip plugin-only hooks.json — loaded only when the prompt-lib plugin is installed)
mkdir -p "$TARGET/hooks"
copied_hooks=0
for f in "$SCRIPT_DIR/hooks/"*; do
  [ "$(basename "$f")" = "hooks.json" ] && continue
  [ -d "$f" ] && continue
  cp "$f" "$TARGET/hooks/"
  copied_hooks=$((copied_hooks + 1))
done
echo "  Copied  hooks/ ($copied_hooks files)"

# Copy project-templates
mkdir -p "$TARGET/project-templates"
cp "$SCRIPT_DIR/project-templates/"*.md "$TARGET/project-templates/"
echo "  Copied  project-templates/ ($(ls "$SCRIPT_DIR/project-templates/"*.md | wc -l) files)"

# Copy output-styles
mkdir -p "$TARGET/output-styles"
cp "$SCRIPT_DIR/output-styles/"*.md "$TARGET/output-styles/"
echo "  Copied  output-styles/ ($(ls "$SCRIPT_DIR/output-styles/"*.md | wc -l) files)"

# Copy CLAUDE.md
if [ -f "$SCRIPT_DIR/CLAUDE.md" ]; then
  cp "$SCRIPT_DIR/CLAUDE.md" "$TARGET/CLAUDE.md"
  echo "  Copied  CLAUDE.md"
fi

# Copy DESIGN.md (design system; imported by CLAUDE.md and referenced by /ui-component skill)
if [ -f "$SCRIPT_DIR/DESIGN.md" ]; then
  cp "$SCRIPT_DIR/DESIGN.md" "$TARGET/DESIGN.md"
  echo "  Copied  DESIGN.md"
elif [ -f "$SCRIPT_DIR/design.md" ]; then
  cp "$SCRIPT_DIR/design.md" "$TARGET/design.md"
  echo "  Copied  design.md"
fi

# Copy git/ folder (templates used by /git init skill — hooks, .editorconfig, .gitattributes)
if [ -d "$SCRIPT_DIR/git" ]; then
  mkdir -p "$TARGET/git"
  cp -r "$SCRIPT_DIR/git/." "$TARGET/git/"
  echo "  Copied  git/ ($(find "$SCRIPT_DIR/git" -type f | wc -l) files)"
fi

# Seed git-policy.json from default (idempotent — never overwrites user edits)
if [ -f "$SCRIPT_DIR/git/git-policy.default.json" ]; then
  if [ ! -f "$TARGET/git-policy.json" ]; then
    cp "$SCRIPT_DIR/git/git-policy.default.json" "$TARGET/git-policy.json"
    echo "  Seeded  git-policy.json (new file — edit to change agent identity / allowed commit types / tag rules)"
  else
    echo "  Kept    git-policy.json (existing user file preserved)"
  fi
fi

# Seed context-guard-policy.json from default (idempotent — never overwrites user edits).
# enabled: false by default — this opt-in /compact nudge stays off until turned on via
# the cabal TUI's Context Guard screen or by hand-editing the file.
if [ -f "$SCRIPT_DIR/context-guard-policy.json" ]; then
  if [ ! -f "$TARGET/context-guard-policy.json" ]; then
    cp "$SCRIPT_DIR/context-guard-policy.json" "$TARGET/context-guard-policy.json"
    echo "  Seeded  context-guard-policy.json (new file — disabled by default)"
  else
    echo "  Kept    context-guard-policy.json (existing user file preserved)"
  fi
fi

# Copy scripts/ (git-identity helper invoked by the commit rule in CLAUDE.md)
if [ -d "$SCRIPT_DIR/scripts" ]; then
  mkdir -p "$TARGET/scripts"
  cp "$SCRIPT_DIR/scripts/"* "$TARGET/scripts/"
  echo "  Copied  scripts/ ($(find "$SCRIPT_DIR/scripts" -type f | wc -l) files)"
fi

# Copy rules
mkdir -p "$TARGET/rules"
cp "$SCRIPT_DIR/rules/"*.md "$TARGET/rules/"
echo "  Copied  rules/ ($(ls "$SCRIPT_DIR/rules/"*.md | wc -l) files)"

# Copy skills — directory-style <name>/SKILL.md bundles only.
# Claude Code never loads flat <name>.md files under skills/, so any in the
# target are dead config from older deploys — prune them on every apply.
mkdir -p "$TARGET/skills"
rm -f "$TARGET/skills/"*.md
for dir in "$SCRIPT_DIR/skills/"*/; do
  [ -d "$dir" ] || continue
  name="$(basename "$dir")"
  mkdir -p "$TARGET/skills/$name"
  cp -r "$dir." "$TARGET/skills/$name/"
done
echo "  Copied  skills/ ($(find "$SCRIPT_DIR/skills" -mindepth 1 -maxdepth 1 -type d | wc -l) dir skills; stale flat .md pruned)"

# Copy keybindings
if [ -f "$SCRIPT_DIR/keybindings.json" ]; then
  cp "$SCRIPT_DIR/keybindings.json" "$TARGET/keybindings.json"
  echo "  Copied  keybindings.json"
fi

# Copy MEMORY.md if it exists in this folder
if [ -f "$SCRIPT_DIR/MEMORY.md" ]; then
  cp "$SCRIPT_DIR/MEMORY.md" "$TARGET/MEMORY.md"
  echo "  Copied  MEMORY.md"
fi

echo ""
echo "Done. Restart Claude Code for changes to take effect."
