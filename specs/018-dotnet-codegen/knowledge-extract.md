# Knowledge extract: cost engineering for LLM code generation

Portable notes, written to be lifted into another document. Two halves: **transferable principles with evidence**, then **what this repository already contains** that bears on them — including several things that turn out to be cost-control mechanisms without being labelled as such.

Source material: Aider's published benchmarks, Cursor's engineering blog, the leaked Lovable agent prompt and tool schema, Bolt/WebContainer reporting, prompt-caching pricing, and an audit of this repo. Full citations at the bottom.

---

## Part 1 — The transferable principles

### The framing that makes the rest make sense

There are only **four cost centres** in an LLM coding system. Every technique the fast/cheap tools use is an attack on one of them, and naming which one is how you tell a real optimisation from a superstition.

| Cost centre | Property | Consequence |
|---|---|---|
| **Output tokens** | ~5× input price, generated serially | Sets cost *and* wall-clock latency |
| **Input tokens** | Cheap, parallel, cacheable | Waste here is optional, not inherent |
| **Round trips** | Each re-runs inference over the entire context | Batching and routing matter more than they look |
| **Retries** | Full cost, zero progress | The most expensive possible outcome |

### 1. Output tokens: the diff paradox, and the split that resolves it

The naive rule is "emit diffs, not whole files." It is wrong on its own, and the reason is the useful part.

- Aider measured whole-file vs diff output: **quality is comparable**, but whole-file "significantly increases costs and latency."
- Cursor found the opposite failure mode. Frontier models are *bad* at diffs for three reasons: fewer output tokens means **fewer forward passes** and therefore worse reasoning; diffs are **out of distribution** (training data is overwhelmingly complete files); and **line numbers fail** because models cannot count and tokenizers merge digit sequences into single tokens.
- Aider independently reached the same conclusion on line numbers: *"GPT is terrible at working with source code line numbers"* — they strip them out of unified-diff hunk headers entirely.

So diffs are cheap but degrade the answer; whole files are accurate but expensive. **Both teams resolved it the same way, independently: split the job across two stages.**

- **Cursor:** frontier model emits a *lazy sketch* (the changed parts plus `// ... existing code ...`). A fine-tuned Llama-3-70B then rewrites the complete file at **~1000 tok/s** via *speculative edits* — since most output equals the input, the original file's own chunks are fed in as speculated tokens and unchanged runs are accepted in bulk. No draft model, just a deterministic guess that's nearly always right. **13× over vanilla 70B, 9× over their prior GPT-4 pipeline.** Degrades past ~400-line files.
- **Aider:** "architect/editor." One model reasons in prose, a second converts prose into edits. o1-preview + a cheap editor hit **85%**.

> **The single most useful number in this whole body of work: Claude Sonnet paired with *itself* went 77.4% → 80.5%.**
>
> The gain is not the second model. It is *separating reasoning from edit-formatting*. A single model splits its attention between solving the problem and conforming to the output format, and pays for it. This means the split is worth implementing even when you have only one model — which makes it available to pure prompt engineering, with no infrastructure at all.

**Corollary that people miss:** "keep files small" is a **cost-control mechanism**, not a style preference. Small files make whole-file rewrite affordable and make search/replace anchors unique.

### 2. Input tokens: send structure, not source

Aider's repo map is the sharpest single idea:

1. Parse with tree-sitter → AST.
2. Extract **signatures only** — no member bodies.
3. Build the symbol reference graph and rank with **PageRank**; heavily-referenced code is more important.
4. Pack the top-ranked signatures into a **hard token budget** (default 1k).

The model gets the shape of a 100k-line codebase for ~1k tokens, then asks for the two files it actually needs. Grep to locate, read ranges — never read whole files speculatively. Lovable's prompt hard-*forbids* re-reading anything already in context.

### 3. Round trips: a cache is a prefix

- Prompt caching delivers up to **90% cost** and **85% latency** reduction. Writes cost **1.25×**, reads **0.1×** — so you break even at **two hits**. One documented case moved from a **7% to 84%** hit rate, cutting total spend **59–70%**.
- **The non-obvious consequence:** a cache is a *prefix*. Anything that changes invalidates everything after it. Context must therefore be ordered **stable → volatile**: system prompt, tool schemas, rules, structural map, then files, then conversation. Most people scatter volatile content early and silently destroy their own cache.
- This is *why* these tools can afford 10k-token system prompts encoding an entire design system: after turn one it costs ~10%.
- **Route by intent before spending.** Lovable defaults to discussion mode and enters the agent loop only on explicit action words. Most user turns are not edits.

### 4. Retries: the underrated one

A failed edit is the worst outcome available — full price, zero progress, plus a correction turn.

- **Forgiving appliers are not optional.** Aider disabled flexible patch-matching as an experiment and edit errors rose **9×**. Tolerate missing markers, wrong indentation, dropped lines. The applier should be a fuzzy matcher, not a parser.
- **Use in-distribution formats.** Unified diff won because it is `git diff` output. Switching to it took GPT-4 Turbo from **20% → 61%** on the refactoring benchmark and cut lazy "rest unchanged" stubs from 12 tasks to 4 of 89.
- **Prefer high-level hunks.** A whole rewritten function beats interleaved ± lines by **30–50% fewer errors**.
- **Close the loop with a machine.** Lovable's tool list includes `lov-read-console-logs` and `lov-read-network-requests` — it reads the live preview's errors and self-heals. Bolt runs the whole stack in a browser WebContainer so there's no VM to wait for.
- **Aider also tested "emotional appeal" prompting** (blind user, no hands, tipping). It measurably **hurt** both formats. Worth knowing, given how widespread the folklore is.

### 5. Scope deletion: the cheapest lever, and the least technical

- **One fixed stack, enforced.** Lovable's prompt explicitly *refuses* Vue/Next/Svelte/Python. Every architectural decision removed is reasoning never paid for and a failure mode that cannot occur.
- **Never bootstrap.** Projects start from an already-running scaffold, deps installed, dev server hot. Turn 1 edits a working app. Bootstrapping is the most expensive and most failure-prone phase, and they skip it entirely.
- **Managed backend.** Supabase deletes auth, storage, migrations and deploy from the problem.
- **Taste decided once.** Semantic design tokens in `index.css`; components are *forbidden* from using `text-white`. The model never re-derives aesthetics per component.

### 6. The honest failure mode

Bolt ships diff mode **off by default**, and users report *"token burn on debug loops — you pay full price to fix Bolt's own breakage."*

> **A self-healing loop is only as good as its error signal.** Browser console output is noisy, late, and frequently fails to name the cause. A weak signal turns a self-correcting loop into a money incinerator. Any repair loop needs a hard, visible ceiling.

### 7. Why compiled backends are a *better* fit than React

The frontend tools' two weakest components are precisely a typed backend's two strongest:

| Component | Lovable / Bolt / v0 have | .NET has |
|---|---|---|
| Structural map | tree-sitter syntax tree, no type resolution | **Roslyn semantic model** — real type resolution, find-all-references, inheritance graph |
| Error signal | browser console — noisy, late, vague | **Compiler + xUnit** — deterministic, precise, names the exact symbol/file/line, free |

Working against you: brownfield codebases don't fit in context, and a bad edit cascades into a wall of compile errors. Both are mitigated by the same asset — the compiler tells you exactly what broke, instantly.

### 8. One original conclusion from this analysis

Every edit format in the published benchmarks anchors edits in **text** — line numbers (models can't count) or surrounding source (drifts). A statically-typed language offers an anchor none of them had available: **stable symbol identity**. `namespace + type + member signature` is invariant under every whitespace, ordering and formatting change.

So for C#-like languages, the recommendation is **symbol-anchored whole-member replacement**: no line numbers, no context lines, drift-proof, and it inherits the measured 30–50% error reduction of whole-member hunks while emitting nothing for the rest of the file.

This matters doubly if a formatter runs after every write — a formatter is a *systematic anchor-drift generator*, and any text-anchored format fights it on every turn.

---

## Part 2 — What this repository already contains

Audited against `prompt-lib`. Several of these are cost engineering that was never labelled as such.

### Already cost engineering, under another name

| Asset | What it actually is |
|---|---|
| `global/rules/_size-discipline.md` — soft/hard LoC caps, 5 concern-separation triggers | **Output-token control.** Small cohesive files are what make whole-member rewrites affordable and search anchors unique. Framed as style; functions as cost. |
| `global/rules/csharp.md` — one type per file, Command/Query separation, domain layer with zero external deps | **A cacheable constant.** Stable, project-independent rules belong in the low-volatility band of the cache prefix. Their stability is what makes them free after turn one. |
| `global/CLAUDE.md` → subagent routing: *"a subagent dispatch costs a full fresh context… delegate only when it buys scale, independence, or parallelism"* | **Round-trip discipline**, already correctly reasoned. The >5-files threshold is a break-even calculation. |
| `global/CLAUDE.md` → `/loop` guidance: *"stay under ~4.5 min to keep the prompt cache warm, otherwise commit to 20–30 min idle ticks — never ~5 min"* | **Prompt-cache TTL awareness**, already encoded. "Never ~5 min" is the worst-of-both-worlds observation — just past the TTL, too frequent to be cheap. |
| `global/CLAUDE.md` → *"never read generated, dependency, or build-output dirs"* | **Input-token control.** Committed source is the source of truth; artifacts are noise. |
| `/cli-llm-app` skill — persistent-subprocess pattern, **~10× speedup** | **Round-trip control at the process level.** Spawning a CLI per turn pays cold start every time; a persistent subprocess amortises it. Directly reusable for a provider layer. |

### Reusable code primitives

| Module | Verdict |
|---|---|
| `setup/src/cabal/session_pricing.py` — `PricingEntry`, `load_pricing()`, `lookup(model, pricing)` | **Reuse directly.** Per-model cost lookup: exactly what a cost ledger needs. |
| `setup/src/cabal/headless.py` | **Reuse as a pattern.** Established `argparse` + `--json` + plan/summary/emit CLI shape. |
| `setup/src/cabal/claude_cli.py` — `ClaudeRunResult`, exe resolution, subprocess invocation | **Reuse as a pattern** for provider invocation; pairs with `/cli-llm-app`. |
| `setup/src/cabal/model_assignments.py` | **Adjacent — do not reuse.** Manages which model a *skill or agent* declares in frontmatter, not per-stage routing. Similar name, different concern. |
| `setup/src/cabal/diff_apply.py`, `diff_text.py` | **Do not reuse.** Despite the names these are the settings-*deploy* differ (`Component` / `FileStatus`) and a Rich renderer — not a source-code edit applier. Noted to prevent a false assumption. |
| `docs/okf/` knowledge catalog + `graph.json` | **A structural map, for the agent ecosystem rather than for code.** Same idea as Aider's repo map applied to skills/agents/hooks/rules. Worth noting the pattern already exists here. |

### One local hazard worth writing down

`global/rules/csharp.md` documents that **`dotnet format` runs as a `PostToolUse` hook after every write.** That is a systematic anchor-drift generator: it rewrites the file immediately after each edit. Any text-anchored edit format is fighting the repo's own tooling on every turn — which is a large part of why symbol anchoring (Part 1 §8) is the right call here specifically, not merely in the abstract.

### Existing .NET assets and where they stop

- `@dotnet-architect` — reasoning only, no execution surface, and it deliberately **defers architecture to each project's CLAUDE.md**. That is the opposite of a locked template, and the tension is worth being explicit about: scope deletion (Part 1 §5) requires locking; this agent's design assumes not locking.
- `@dotnet-tester` — test authoring only.
- `/dotnet-class` — generates a single type from a prompt. No verification loop, no retry ceiling, no cost accounting.

---

## Citations

- Aider, *Unified diffs make GPT-4 Turbo 3X less lazy* — https://aider.chat/docs/unified-diffs.html
- Aider, *Separating code reasoning and editing* (architect/editor) — https://aider.chat/2024/09/26/architect.html
- Aider, *GPT code editing benchmarks* / *Edit formats* — https://aider.chat/docs/benchmarks.html · https://aider.chat/docs/more/edit-formats.html
- Aider, *Building a better repository map with tree sitter* — https://aider.chat/2023/10/22/repomap.html
- Cursor, *Editing Files at 1000 Tokens per Second* — https://cursor.com/blog/instant-apply
- Leaked Lovable agent prompt + tool schema — https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools (`Lovable/`); dated snapshots at https://github.com/EliFuzz/awesome-system-prompts (`leaks/lovable/`)
- `lovable-tagger` (first-party Vite plugin, click-to-edit source mapping) — https://www.npmjs.com/package/lovable-tagger
- GPT Engineer, Lovable's stated precursor — https://github.com/AntonOsika/gpt-engineer
- Open reimplementations — https://github.com/freestyle-sh/adorable · https://github.com/firecrawl/open-lovable
- Roslyn MCP prior art — `carquiza/RoslynMCP` · `JoshuaRamirez/RoslynMcpServer` · `mihakralj/dotnet-semantic-mcp`

**Caveats:** leaked prompts are point-in-time, unverified, and these products ship continuously. Benchmark figures come from the vendors' own published evaluations on their own harnesses — directionally strong, not independently reproduced. Pricing multipliers change.
