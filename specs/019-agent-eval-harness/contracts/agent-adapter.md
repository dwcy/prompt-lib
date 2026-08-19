# Contract: AgentAdapter Interface

The seam that keeps the runner core agent-agnostic (FR-013, US6). v1 ships one implementation (`claude-code`); Codex / Gemini CLI adapters must be addable without modifying `matrix.py`, `checks.py`, `metrics.py`, `judge.py`, or `report.py`.

## Protocol (`cabal/evals/adapters/base.py`)

```python
class AgentAdapter(Protocol):
    name: str  # registry key used in eval.config.toml `adapter`

    def check(self) -> AdapterStatus:
        """CLI exists and runs (--version). Never raises."""

    def capabilities(self) -> AdapterCapabilities:
        """Which metric fields this adapter can supply."""

    def run(self, spec: AgentRunSpec) -> AgentRunResult:
        """Execute one headless agent run. Never raises for run-level
        failures — they are encoded in AgentRunResult.status/reason.
        Raises AdapterUnavailableError only when the CLI itself is absent."""
```

```python
@dataclass(frozen=True)
class AgentRunSpec:
    prompt: str                 # verbatim task prompt.md
    worktree: Path              # cwd for the agent process
    config_dir: Path | None     # → CLAUDE_CONFIG_DIR (None = adapter has no equivalent)
    settings_file: Path | None  # → --settings (None = not passed)
    env: Mapping[str, str]      # extra env vars, merged over os.environ
    model: str | None           # → --model / -m
    timeout_seconds: int        # hard wall; adapter must kill the process at expiry
    skip_permissions: bool      # claude-code: --dangerously-skip-permissions
    transcript_path: Path       # adapter streams raw event lines here as it reads them

@dataclass(frozen=True)
class AgentRunResult:
    status: Literal["completed", "failed"]
    failure_reason: str | None      # "agent_timeout" | "agent_crash" | None
    final_text: str                 # "" when unavailable
    exit_code: int | None
    wall_seconds: float

@dataclass(frozen=True)
class AdapterCapabilities:
    tokens: bool        # can report input/output/cache token counts
    tool_calls: bool    # transcript carries per-tool-call events
    cost: bool          # reports cost in USD
```

## Behavioral requirements

1. **Isolation**: the adapter passes `config_dir` as `CLAUDE_CONFIG_DIR` (or its CLI's equivalent) and MUST NOT let the process see the user's real config root when `config_dir` is set.
2. **Timeout**: at `timeout_seconds` the adapter kills the process tree and returns `failed/agent_timeout` — it never hangs the matrix.
3. **Transcript**: raw CLI output events are appended to `transcript_path` verbatim (JSONL for claude-code); the adapter does not interpret them — `metrics.py` owns parsing. Fields the adapter's CLI cannot produce are reported by `capabilities()` so metrics records `null`, never fabricated zeros (US6-AS2).
4. **No side effects** outside `worktree`, `config_dir`, and `transcript_path`.
5. **Registry**: adapters register by `name` in `adapters/__init__.py`; `eval.config.toml`'s `adapter` value selects one; unknown name = validate-time error.

## v1 implementation: `claude-code`

- Command: `claude -p <prompt> --output-format stream-json --verbose --permission-mode acceptEdits [--model <m>] [--settings <file>]` (`--dangerously-skip-permissions` replaces the permission-mode flag when `skip_permissions`).
- cwd = `spec.worktree`; env = `os.environ | {"CLAUDE_CONFIG_DIR": str(config_dir)} | spec.env`.
- `final_text` = `result` event's `result` field; `status=failed/agent_crash` when the process exits non-zero without a `result` event or the `result` event carries `is_error`.
- Capabilities: `tokens=True, tool_calls=True, cost=True`.

## Contract tests

`setup/tests/contract/test_evals_artifacts.py` includes an adapter-contract section driven by a `FakeAdapter` plus the real `claude-code` adapter run against **recorded fixture transcripts** (no live CLI in CI): construction from `AgentRunSpec`, timeout kill behavior (fake process), transcript passthrough, and capability-driven null metrics.
