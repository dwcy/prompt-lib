# Quickstart: Claude Session Dashboard

## Prerequisites

- Python 3.11+
- Cabal TUI dependencies installed (`uv sync` in `setup/`)
- Claude Code installed (logs at `~/.claude/projects/`)

## Running the Dashboard

```bash
# From repo root
./run          # POSIX
.\run.cmd      # Windows

# Navigate to Sessions screen in Cabal TUI
# (keyboard: press S or use menu to reach Sessions view)
```

## Development

```bash
cd setup
uv run python -m cabal   # or however Cabal is launched
```

## Key Files

| Path | Purpose |
|---|---|
| `setup/src/cabal/screens/sessions_screen.py` | Textual Screen for session list + detail |
| `setup/src/cabal/services/session_reader.py` | Log parsing, session scanning, delete |
| `setup/src/cabal/data/pricing.py` | Bundled model pricing table |
| `~/.claude/projects/` | Source of session transcript JSONL files |
| `~/.claude/write_audit.jsonl` | Source of hook trigger events |

## Pricing Override

To update pricing without code changes, create `~/.claude/dashboard-pricing.json`:

```json
{
  "claude-sonnet-4-6": {
    "input_usd_per_mtok": 3.00,
    "output_usd_per_mtok": 15.00,
    "cache_read_usd_per_mtok": 0.30,
    "cache_write_usd_per_mtok": 3.75
  }
}
```

## Testing

```bash
cd setup
uv run pytest tests/dashboard/ -v
```

Tests use a fixture directory with sample JSONL transcripts — no real `~/.claude/` data required.
