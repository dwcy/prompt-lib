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

# Copy settings.json — authored Windows-canonical ($USERPROFILE). On non-Windows
# shells that variable is empty, so swap it for $HOME (resolves on Linux/macOS).
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) cp "$SCRIPT_DIR/settings.json" "$TARGET/settings.json" ;;
  *) sed 's/\$USERPROFILE/$HOME/g' "$SCRIPT_DIR/settings.json" > "$TARGET/settings.json" ;;
esac
echo "  Copied  settings.json"

# Copy agents
mkdir -p "$TARGET/agents"
cp "$SCRIPT_DIR/agents/"*.md "$TARGET/agents/"
echo "  Copied  agents/ ($(ls "$SCRIPT_DIR/agents/"*.md | wc -l) files)"

# Copy hooks (skip plugin-only hooks.json — loaded only when the prompt-lib plugin is installed)
mkdir -p "$TARGET/hooks"
copied_hooks=0
for f in "$SCRIPT_DIR/hooks/"*; do
  [ "$(basename "$f")" = "hooks.json" ] && continue
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

# Copy rules
mkdir -p "$TARGET/rules"
cp "$SCRIPT_DIR/rules/"*.md "$TARGET/rules/"
echo "  Copied  rules/ ($(ls "$SCRIPT_DIR/rules/"*.md | wc -l) files)"

# Copy skills
mkdir -p "$TARGET/skills"
cp "$SCRIPT_DIR/skills/"*.md "$TARGET/skills/"
echo "  Copied  skills/ ($(ls "$SCRIPT_DIR/skills/"*.md | wc -l) files)"

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
