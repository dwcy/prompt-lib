# Size discipline — shared block

Canonical reference for the 5 concern-separation triggers and the justification-comment convention. Linked from every per-language rule (`python.md`, `react.md`, `csharp.md`, `typescript.md`, `unity.md`). Not auto-loaded — has no `paths:` frontmatter — read it when a per-language rule points here.

## Numeric budgets

Soft cap = "consider splitting". Hard cap = "split or write a justification comment at line 1". The specific numbers live in each per-language rule.

## The 5 concern-separation triggers

Two or more firing = split before writing, not after.

1. **> 3 unrelated public symbols** (classes or top-level functions) in one file. A `Repository` and an unrelated `EventBus` don't share a file.
2. **Imports span > 5 logical domains** (UI + git + subprocess + http + json + db, etc.). Six domains is one file owning six jobs.
3. **> 15 methods on one class.** Extract collaborator / strategy / mixin.
4. **File approaches the soft cap AND mixes UI with side-effecting I/O** (subprocess / network / persistence). Extract the I/O into a service module; keep the UI file thin.
5. **Any single method does > 2 context switches** (e.g. parse JSON → call git → render UI). Extract an orchestrator that calls three single-purpose helpers.

## Justification comment

When a file legitimately exceeds the hard cap (e.g. an inline CSS blob co-located per a spec FR, a generated parser table, a Textual `App` with required inline CSS), write at line 1:

- Python: `# > <cap> LoC justified: <one-line reason>`
- TS / C#: `// > <cap> LoC justified: <one-line reason>`

Non-substantive reasons ("needed", "complex", "for now") do not count and will fail the verifier audit. The reason MUST point to a structural constraint (a spec FR, a framework requirement, a generated file marker).

## What this is NOT

- Not a hard line counter measured by tooling — agents self-apply it; the verifier audits it.
- Not a ban on legitimately big files — that's what the justification comment is for.
- Not a "split everything into 50-line files" rule. A 350-LoC module with one cohesive class is healthier than seven 50-LoC files with intertwined imports.

## Split patterns (Python examples; analogous in other languages)

- **Service module** — extract `subprocess` / `git` / HTTP calls into `<feature>_service.py`; the screen imports from it but does not call them directly.
- **View + worker** — keep `compose()` + event handlers in the view; move worker bodies (`_fetch_*`, `_apply_*`) into a sibling `<feature>_worker.py`.
- **Model + repository** — dataclass / Pydantic model in `models/<entity>.py`; persistence in `repositories/<entity>_repo.py`.
- **Builder + emitter** — large config/string construction goes into `<feature>_builder.py`; the consumer just calls `build_X()`.
