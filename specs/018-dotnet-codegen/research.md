# Phase 0 Research: dotnet-codegen

**Feature**: 018-dotnet-codegen | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

This document carries forward research already established in conversation rather than re-deriving it, then resolves the five open technical questions the plan depends on.

---

## Part 1 — Established findings (carried forward)

### 1.1 The four cost centres

Every technique below attacks one of these. Naming which one is how each decision in this plan is justified.

| Cost centre | Property | Consequence |
|---|---|---|
| Output tokens | ~5x input price, generated serially | Sets both cost and wall-clock latency |
| Input tokens | Cheap, parallel, cacheable | Waste here is optional, not inherent |
| Round trips | Each re-runs inference over the whole context | Batching and routing matter more than they appear to |
| Retries | Full cost, zero progress | The most expensive possible outcome |

### 1.2 Aider's findings (edit formats)

- Whole-file and diff output produce **comparable quality**, but whole-file "significantly increases costs and latency".
- Unified diff **with line numbers stripped** took GPT-4 Turbo from **20% to 61%** on the refactoring benchmark. Lazy "rest unchanged" stubs fell from **12 to 4** of 89 tasks.
- **High-level whole-function hunks beat interleaved +/- lines by 30-50% fewer errors.**
- Disabling flexible/fuzzy patch application increased edit errors **9x**.
- **Line numbers are poison** — models cannot count, and tokenizers merge digit sequences into single tokens.
- Emotional-appeal prompting ("the user has no hands") measurably **hurt** both formats.

### 1.3 Cursor's findings (why frontier models fail at diffs)

- Fewer output tokens means fewer forward passes, which means **worse reasoning**. Compressing an answer into a diff removes the model's thinking room.
- Diffs are **out of distribution** — training data is overwhelmingly complete files.
- Line-number counting fails for the tokenizer reason above.
- Their fix: a **two-model split**. The frontier model emits a lazy sketch; a fine-tuned Llama-3-70B rewrites the whole file at **~1000 tok/s** using speculative edits, where the original file's own chunks are the speculated draft and unchanged runs are accepted in bulk. **13x** over vanilla 70B, **9x** over their prior GPT-4 pipeline. Degrades past **~400-line files**.
- Observed side effect: models tend to "fix/clean up" unrelated code, deleting commented-out code and newlines.

### 1.4 The architect/editor split

- Aider: o1-preview reasoning + a cheap editor scored **85%**.
- **Claude Sonnet paired with itself went 77.4% to 80.5%.**

That second number is the single most important data point in this research. The gain comes from **separating reasoning from edit-formatting**, not from introducing a second model. It means the split is worth implementing even when both stages run on the same model — which is what makes a prompt-only first slice viable.

### 1.5 Structural context (the repo map)

Aider: tree-sitter AST, then signatures only, then PageRank over the symbol reference graph, packed into a hard token budget (default 1k tokens). The model sees the shape of the codebase, then requests the two or three files it actually needs.

### 1.6 Prompt caching economics

- Up to **90% cost** and **85% latency** reduction.
- Writes cost **1.25x**, reads **0.1x**, so break-even is at **two hits**.
- One documented case moved from **7% to 84%** hit rate, cutting total spend **59-70%**.
- **A cache is a prefix.** Anything that changes invalidates everything after it, so context must be ordered stable-to-volatile or the cache destroys itself every turn.

### 1.7 Scope deletion (Lovable / Bolt)

One fixed stack with explicit refusal of alternatives; a pre-warmed running scaffold so turn 1 edits a working app; a managed backend; design decisions made once in the prompt; discussion mode by default with the agent loop entered only on explicit action words.

### 1.8 The documented failure mode

Bolt ships diff mode **off by default**, and users report "token burn on debug loops — you pay full price to fix Bolt's own breakage."

**A self-healing loop is only as good as its error signal.** This is the entire justification for FR-021's hard retry ceiling and FR-022's environment-versus-defect classification.

### 1.9 Why .NET is a better fit than React

Both of the frontend tools' weakest components are .NET's strongest:

| Component | Frontend tools have | .NET has |
|---|---|---|
| Structural map | tree-sitter syntax tree, no type resolution | **Roslyn semantic model** — real type resolution, find-all-references, inheritance graph |
| Error signal | browser console — noisy, late, rarely names the cause | **Compiler + xUnit** — deterministic, precise, names exact symbol/file/line, free |

---

## Part 2 — Resolved technical decisions

### R1. Edit format for C#

**Decision: symbol-anchored whole-member replacement, with fuzzy search/replace as the fallback for non-member edits. Reject unified diff.**

**Rationale.** Every format Aider benchmarked anchors edits in *text* — either line numbers (fails: models cannot count) or surrounding source (fails: drifts). C# offers an anchor none of the languages in that study had available: **stable symbol identity**. A member is uniquely addressable as `namespace + type + member signature`, which is invariant under every whitespace, ordering, and formatting change.

This matters acutely here because of a repo-specific hazard: **`dotnet format` runs as a `PostToolUse` hook after every write** (documented in `global/rules/csharp.md`). That hook rewrites the file after each edit — it is a systematic anchor-drift generator. Any text-anchored format would be fighting the repo's own tooling on every single turn.

Symbol anchoring also inherits the benefit already measured: whole-member hunks are exactly the "high-level, coherent block" shape that produced **30-50% fewer errors** than interleaved lines, and it gives the model full thinking room inside the member body (Cursor's forward-pass argument) while emitting nothing for the rest of the file (the output-token saving).

**Format.** The writing stage emits, per edit: target file, fully-qualified member signature, disposition (`replace` / `insert-into-type` / `delete`), and the complete new member text. No line numbers. No context lines.

**Fallback.** Edits that are not member-scoped — `using` directives, `Program.cs` top-level statements, `.csproj` items, DI registration lines — use fuzzy search/replace with progressive relaxation (exact, then whitespace-insensitive, then leading-trim, then normalised-token). Aider's 9x result says the relaxation ladder is not optional.

**Alternatives rejected.**

- *Unified diff (line numbers stripped)* — its measured advantage was familiarity plus the rigor the patch format imposes. But it reintroduces text anchors, which `dotnet format` breaks on every turn, and C# has a strictly better anchor available. Rejected on the drift interaction, not on the benchmark.
- *Whole-file rewrite* — quality is comparable per Aider, but the cost and latency penalty is exactly what this feature exists to remove. It also invites Cursor's observed "clean up unrelated code" behaviour. Retained only as a last-resort repair path for files under the ~400-line threshold Cursor identified.
- *Reproducing Cursor's fast-apply model* — requires a fine-tune. Explicitly out of scope per the spec.

### R2. Fork an existing Roslyn MCP server, or build one?

**Decision: neither, in the first slice — defer the question to the brownfield phase, and evaluate forking then.**

**Rationale.** The greenfield path (US1-US5) operates on solutions the tool just generated from a known template. Their structure is *already known* — it is the template. Building a semantic map to discover the shape of a solution whose shape you dictated is pure waste. The Roslyn map earns its cost only in US6, where the solution is unknown and large.

This is the largest scope reduction available in the plan, and it falls straight out of the greenfield-first ordering the developer chose.

**When it is picked up (Phase B), the evaluation order is fork before build.** Three candidates were identified — `carquiza/RoslynMCP`, `JoshuaRamirez/RoslynMcpServer`, `mihakralj/dotnet-semantic-mcp`. Between them they already expose symbol search by pattern, find-all-references with context snippets, symbol metadata including accessibility and XML docs, and project/namespace dependency analysis. That covers most of FR-005.

**What none of them is documented as providing**, and what this feature needs on top:

1. A **ranked, token-budgeted** map (FR-006). They answer queries; they do not produce a fixed-budget summary of an entire solution.
2. Reporting **what was omitted** when the budget binds (FR-006, US6 scenario 2).
3. A **symbol-anchored edit-application** tool matching R1.

**Note for Phase B**: because MCP is an external protocol, adopting this path activates **Constitution Gate 1** (link the spec, state conformance scope) and **Gate 3** (contract tests on tool schemas before implementation). That is a real cost of the MCP route and a further reason not to pay it in the first slice.

### R3. Symbol ranking for a .NET structural map

**Decision: cheap layered heuristic in Phase A; PageRank deferred to Phase B and only if the heuristic measurably fails.**

**Rationale.** PageRank over a reference graph is the right answer when you have no other signal about importance — Aider's situation, since it must work on arbitrary repositories in any language. A .NET solution built from a known template has **stronger and much cheaper signals**:

1. **Project layer position** — a template-generated solution declares its own layering (Domain / Application / Infrastructure / Api). Layer is a direct importance proxy, free to read from the `.csproj` reference graph.
2. **Public surface** — public and protected members are the API; private members are implementation detail. Free from syntax alone.
3. **Recency** — types touched in recent runs are what the current work concerns. Free from the run records already kept for FR-028.

Ordering by (layer, visibility, recency) requires no graph construction and no semantic model. Given SC-006 asks for the map to be under 2% of source size, and signatures-only extraction alone typically clears that by an order of magnitude, the ranking function's real job is tie-breaking inside an already-small budget.

**Trigger to revisit**: if SC-006 holds but the map fails to surface the *right* types — measured as the writing stage requesting files the map did not point at — the heuristic is inadequate and PageRank over Roslyn's find-all-references becomes justified. A Phase B decision with a concrete test, not a guess made now.

### R4. Distinguishing environment failure from code defect (FR-022)

**Decision: classify on diagnostic ID prefix first, exit code second, absence-of-diagnostics last.**

The .NET toolchain emits structured, prefixed diagnostic IDs. This is the deterministic signal Lovable's browser console never had.

| Signal | Classification | Reason |
|---|---|---|
| `CS####` | **Code defect** | C# compiler diagnostic — the code is wrong |
| xUnit assertion failures; non-zero `dotnet test` with reported failures | **Code defect** | Behaviour is wrong |
| `NU####` | **Environment** | NuGet restore, feed, auth, offline |
| `NETSDK####` | **Environment** | SDK version or targeting problem |
| `MSB####` | **Environment** (default) | Build/toolchain — one exception below |
| Non-zero exit, zero parsed diagnostics | **Environment** | Crash, missing tool, permissions — never spend a repair attempt here |
| Analyzer diagnostics from `.editorconfig` severity | **Code defect** | The repo's own rules |

**Two refinements that matter:**

- `MSB####` raised against a file the run itself just wrote is reclassified as a **code defect** — the tool broke the `.csproj`, and that is repairable. `MSB####` against anything else is environmental.
- **Environment failures consume zero repair attempts** and abort the run immediately with a diagnosis. Repairing a missing SDK by regenerating C# is precisely the runaway loop FR-021 exists to prevent.

### R5. Cache prefix ordering and what belongs in it

**Decision: a five-band stable-to-volatile ordering, with cache checkpoints after bands 2 and 3.**

Per 1.6, a cache is a prefix, so this ordering *is* the caching strategy. Getting the bands wrong is what produced the 7% hit rate in the cited case study.

| Band | Contents | Changes when | Cacheable |
|---|---|---|---|
| 1 | Pipeline system prompt, stage instructions, edit-format contract, tool schemas | Tool is upgraded | Yes — near-permanent |
| 2 | `global/rules/csharp.md`, `global/rules/_size-discipline.md`, the project's locked template contract | Rules edited, or never (template is locked per FR-001a) | Yes — **checkpoint here** |
| 3 | Structural map of the solution | Solution structure changes (type added, removed, renamed) | Yes — **checkpoint here** |
| 4 | Contents of files opened this run | Every run | No |
| 5 | Approved change intent, prior attempt diagnostics, repair history | Every attempt within a run | No |

**Consequences that constrain the design:**

- Band 2 is cacheable *only* because the template is locked per project (FR-001a/b). A tool that re-decided architecture per run would place a volatile item in band 2 and destroy everything below it. **The architecture lock and the caching strategy are the same decision seen twice.**
- Band 3 must be **content-addressed, not regenerated per run** — a map rebuilt from scratch each time produces a different byte sequence and invalidates itself even when the solution has not changed. Cache the map; invalidate on a structural fingerprint.
- Repair attempts append to band 5 only. A repair must never touch bands 1-3, which is a second, independent reason FR-020 routes diagnostics to the writing stage rather than the reasoning stage.
- SC-005 asks for 70% of served context from cache across 5+ runs. With bands 1-3 stable and dominant in size that is achievable; it is **not** achievable inside a host session whose prefix ordering the tool does not control. See the delivery-form analysis in `plan.md`.

---

## Part 3 — Existing assets audited for reuse

Checked against the `cabal` package in this repo before proposing anything new (Constitution Principle V).

| Asset | Verdict |
|---|---|
| `setup/src/cabal/session_pricing.py` | **Reuse directly.** `PricingEntry` / `load_pricing()` / `lookup(model, pricing)` is exactly the per-model cost lookup the FR-028 cost ledger needs. |
| `setup/src/cabal/headless.py` | **Reuse as a pattern.** Established `argparse` + `--json` + plan/summary/emit CLI shape to mirror for the pipeline's command surface. |
| `setup/src/cabal/claude_cli.py` | **Reuse as a pattern.** `ClaudeRunResult`, exe resolution, subprocess invocation. Pairs with the `/cli-llm-app` skill's persistent-subprocess guidance for the provider layer. |
| `setup/src/cabal/model_assignments.py` | **Adjacent, do not reuse.** Manages which model a skill or agent declares in frontmatter — not per-stage provider routing. Different concern despite the similar name. |
| `setup/src/cabal/diff_apply.py`, `diff_text.py` | **Do not reuse.** Despite the names, these operate on prompt-lib deploy components (`Component` / `FileStatus`) and Rich rendering — the settings-deploy differ, not a source-code edit applier. Named here to prevent a false assumption later. |
| `global/rules/csharp.md`, `_size-discipline.md` | **Consume as-is, unmodified** (FR-032a). Supply band 2 of the cache prefix. |
| `@dotnet-architect`, `@dotnet-tester`, `/dotnet-class`, `/dotnet-test` | **Coexist, unmodified** (FR-032). |

## Open items deliberately left for Phase B

- Licence verification for any code ported from an existing project (a relaxation ladder modelled on Aider's, the Roslyn MCP candidates). To be confirmed before any port, not assumed.
- Whether Roslyn replaces the Phase A syntax-level extractor, or supplements it.
- Whether brownfield (US6) justifies the MCP surface at all, versus an in-process analyser invoked directly by the pipeline.
