# Skills — every slash command explained

A skill is a markdown file with frontmatter. When you type `/<name>`, Claude reads the file and treats its body as the next instruction. **No subagent is spawned** — the skill runs in the current conversation with the tools listed in `allowed-tools:`.

Skills are how you turn "things you keep doing" into one keystroke.

## Git workflow skills

### `/git`
- **Args**: `commit` (default), `branch <name>`, `init`
- **Tools**: `Bash, Read, Glob`
- **What it does**:
  - `commit` — runs `git diff --staged`, drafts a conventional commit message (`<type>: <subject>`), tags it with a category (`ui/dotnet/python/css/html/js/ts`) when appropriate, refuses to commit on `main`/`master`, uses agent authorship via `-c user.email="my@agent.commit" -c user.name="Claude Agent"`, asks for confirmation, then commits.
  - `branch <name>` — creates a feature branch off `main`.
  - `init` — initialises a new repo with the convention.
- **Why**: enforces the global commit rules (subject ≤72 chars, imperative mood, agent authorship) without you having to remember them.

### `/commit`
- **Tools**: `Bash`
- **What it does**: lighter version of `/git commit` — staged-only, drafts a conventional message, asks confirmation, commits. No branch safety check, no category tagging, no agent authorship override.
- **When to pick it over `/git commit`**: quick fixups inside a feature branch where the safety machinery is overkill.

### `/pr`
- **Tools**: `Bash, Read`
- **What it does**: runs `git log` and `git diff` between the current branch and main, drafts a PR title + description, creates the PR with `gh pr create`. Uses HEREDOC for the body to keep formatting clean.

### `/review`
- **Tools**: `Bash, Read, Glob`
- **What it does**: structured branch review against `main` — code quality, conventions, potential issues. Output is a flat list of findings, not a code rewrite. Pairs naturally with the `review` output style.

### `/finishing-a-development-branch`
- **Tools**: `Bash, Read, Glob`
- **What it does**: end-of-feature checklist runner. Runs tests, verifies build, creates a final commit, and offers to either open a PR or push. Use after all implementation tasks are done — saves the "did I forget to run tests?" moment.

### `/using-git-worktrees`
- **Args**: `create` (default), `list`, `remove`, `prune`
- **Tools**: `Bash, Read, Glob`
- **What it does**: manages `git worktree` operations so you can run multiple Claude Code sessions on the same repo, in parallel, on different branches. Used by `/executing-plans` when a plan needs an isolated workspace.
- **Dual role**: this skill is the **manual** half of the parallel-isolation rule (for two human-driven Claude Code sessions). The **automatic** half is `isolation: "worktree"` on the Agent tool call, which the dispatcher passes when spawning concurrent subagents. See [`parallel-isolation.md`](parallel-isolation.md).

## Implementation skills

### `/executing-plans`
- **Tools**: `Bash, Read, Write, Edit, Glob, Grep`
- **What it does**: takes a written implementation plan (typically `tasks.md` from a spec) and executes it in a separate session with review checkpoints between phases. Announces itself at start so you know which mode you're in.
- **When to use**: long implementations where you want the model to execute, then pause for human review, rather than barrel through the whole feature.
- **Composes with**: `/using-git-worktrees` to isolate the workspace, then `@code-plan-verifier` once execution finishes.

## Frontend / React skills

### `/react-init`
- **Tools**: `Bash, Read, Write, Edit, Glob`
- **What it does**: scaffolds a complete React 2025 project — Vite + TS + Zustand + TanStack + Biome + Tailwind v4 + Zod + MUI Icons. Asks all questions up front, then generates config files, folder structure, and `.cursorrules` without further interruptions.
- **Pairs with**: `@react-architect` for React structure decisions and `@tanstack-architect` for route/data/form/table architecture.

### `/react-review`
- **Tools**: `Read, Glob, Bash`
- **What it does**: reviews a React file or feature for code quality — separation of concerns, naming, component design, data flow, types, documentation, hygiene. Outputs Critical / Warning / Suggestion findings.

### `/react-test`
- **Tools**: `Read, Write, Glob, Bash`
- **What it does**: scaffolds or reviews tests for a React component, hook, or feature using Vitest + React Testing Library. Follows DI patterns, covers happy paths and failure modes, never tests implementation details.

### `/react-safe`
- **Tools**: `Read, Glob, Bash`
- **What it does**: audits a React file/feature for async correctness, error handling completeness, security — unhandled promises, swallowed errors, missing sanitisation, logged secrets, input validation gaps.

### `/react-perf`
- **Tools**: `Read, Glob, Bash`
- **What it does**: performance audit — unnecessary re-renders, missing memoisation, heavy imports, bundle size, large-dataset handling, lazy-load opportunities.

### `/css`
- **Args**: `scaffold`, or a `ComponentName`
- **Tools**: `Read, Write, Edit, Glob`
- **What it does**: `scaffold` sets up `globals.css` with reset and design tokens. `Button` (or any component name) generates `Button.module.css` alongside the component file.
- **Pairs with**: `@frontend-css` for deeper architectural questions.

### `/ui-component`
- **Tools**: `Read, Glob, Grep, Write, Edit`
- **What it does**: builds a UI component on demand. Enforces design-language compliance, ships a `Preview` component alongside every component, enforces correct HTML semantics for inputs, wires forms to Zustand + Zod validation.
- **Iron rule**: only writes a component when explicitly asked — won't anticipate or pre-emptively scaffold.

### `/design`
- **Tools**: `Read, Write, Edit, Glob`
- **What it does**: loads the Premium Digital Agency 2.0 design system into context. Invoke before building UI components, reviewing designs, or making styling decisions — once loaded, every styling decision in the session must follow it.

### `/lovable-cleanup`
- **Tools**: `Read, Edit, Glob, Bash`
- **What it does**: strips all Lovable / GPTEngineer scaffolding from a project — `lovable-tagger` from `package.json` and `vite.config.ts`, cleans `index.html` metadata, removes injected `data-lovable-id` and `data-gptengineer-id` attributes from all source files, rewrites README, regenerates the lockfile.

## Meta skills

### `/skill-create`
- **Tools**: `Read, Write, Edit, Glob, Bash`
- **What it does**: walks you through designing, writing, testing, and refining a new skill. Use this whenever a workflow you keep doing manually should become a `/command`.

### `/self-improvement` (project-local)
- **Location**: `.claude/skills/self-improvement/` — directory-based skill, project-local (not deployed via `setup/settings-configurator-ui.py`)
- **Tools**: `Read, Write, Edit, Glob, Grep, Bash`
- **What it does**: maintains a structured project memory under `.claude/skills/self-improvement/memory/` — lessons learned, mistakes to avoid, durable preferences, and post-task self-evaluations. Reviews memory before non-trivial tasks. **Removes** lessons that have become stale (e.g., a tool that used to fail now works) rather than soft-deleting with `**STALE**` markers — git history is the audit trail.
- **Helper**: `python .claude/skills/self-improvement/scripts/extract_lessons.py [list|remove|validate]` for listing IDs, removing entries by ID, and validating memory format.
- **Core rule**: cannot retrain model weights. Improvement happens through reusable context, checklists, and evaluations — never by claiming "I've learned X" without writing it down.

## Folder-based skill resource ideas

Most global skills are currently single markdown files. If/when they are converted to full Agent Skill folders, use this shape:

```text
skill-name/
├── SKILL.md
├── scripts/      # executable helpers the skill can run
├── references/   # longer docs/checklists the skill reads
└── assets/       # templates, snippets, fixtures, boilerplate
```

The most useful early conversions are `/git`, `/pr`, `/react-init`, `/react-test`, `/review`, `/docs`, and `/skill-create`, because they already depend on repeatable checks, templates, or structured output.

### Suggested bundles by skill

| Skill | Useful `scripts/` | Useful `references/` | Useful `assets/` |
|---|---|---|---|
| `/git` | `classify_changes.py` to infer commit type/scope from staged paths; `validate_commit_msg.py` for Conventional Commit + 72-char subject checks | `commit-conventions.md`; `branch-safety.md`; `agent-authorship.md` | `commit-message.tmpl`; `branch-name-examples.md` |
| `/commit` | `validate_commit_msg.py`; `staged_summary.py` for a compact staged diff summary | `conventional-commits.md`; `commit-tone.md` | `commit-message.tmpl` |
| `/pr` | `collect_pr_context.py` to gather branch, commits, changed files, test status; `validate_pr_body.py` | `pr-body-guidelines.md`; `reviewable-pr-checklist.md` | `pr-body.tmpl.md`; `release-note-snippet.tmpl.md` |
| `/review` | `changed_files.py`; `extract_findings.py`; `severity_sort.py` | `severity-rubric.md`; `review-checklist.md`; `false-positive-guidance.md` | `review-output.tmpl.md` |
| `/finishing-a-development-branch` | `run_project_checks.py`; `detect_package_manager.py`; `verify_clean_tree.py` | `finish-checklist.md`; `release-readiness.md` | `handoff-summary.tmpl.md` |
| `/using-git-worktrees` | `list_worktrees.py`; `safe_prune.py`; `worktree_status.py` | `worktree-safety.md`; `parallel-session-patterns.md` | `worktree-name-examples.md` |
| `/executing-plans` | `parse_tasks.py`; `phase_status.py`; `plan_progress.py` | `execution-checkpoints.md`; `phase-review-rubric.md`; `rollback-policy.md` | `phase-report.tmpl.md`; `completion-report.tmpl.md` |
| `/react-init` | `scaffold_project.py`; `detect_package_manager.py`; `validate_generated_app.py` | `react-stack-decisions.md`; `tanstack-boundaries.md`; `tailwind-v4-notes.md` | `vite.config.ts.tmpl`; `router.tsx.tmpl`; `queryClient.ts.tmpl`; `feature-folder.tmpl` |
| `/react-review` | `component_inventory.py`; `detect_anti_patterns.py` | `react-review-rubric.md`; `component-boundaries.md`; `hook-rules.md` | `react-review-output.tmpl.md` |
| `/react-test` | `detect_test_runner.py`; `generate_test_skeleton.py`; `summarize_failures.py` | `rtl-patterns.md`; `vitest-patterns.md`; `testing-boundaries.md` | `component.test.tsx.tmpl`; `hook.test.ts.tmpl`; `fixture-factory.tmpl.ts` |
| `/react-safe` | `scan_dangerous_html.py`; `scan_secret_logs.py`; `async_hazards.py` | `frontend-security-checklist.md`; `async-safety.md`; `dompurify-guidance.md` | `security-findings.tmpl.md` |
| `/react-perf` | `bundle_import_scan.py`; `render_hotspots.py`; `large_list_scan.py` | `react-perf-rubric.md`; `memoization-decision-tree.md`; `virtualization-guidance.md` | `perf-report.tmpl.md` |
| `/css` | `generate_module_css.py`; `validate_tokens.py`; `find_hardcoded_values.py` | `token-rules.md`; `css-module-patterns.md`; `accessibility-colors.md` | `globals.css.tmpl`; `Component.module.css.tmpl` |
| `/ui-component` | `component_scaffold.py`; `validate_a11y_structure.py`; `preview_scaffold.py` | `component-api-rules.md`; `html-semantics.md`; `form-control-patterns.md` | `Component.tsx.tmpl`; `ComponentPreview.tsx.tmpl`; `props-interface.tmpl.ts` |
| `/design` | `extract_tokens.py`; `contrast_check.py`; `palette_audit.py` | `premium-agency-system.md`; `layout-density-rules.md`; `motion-guidance.md` | `token-map.json`; `page-section.tmpl.tsx` |
| `/lovable-cleanup` | `remove_lovable_attrs.py`; `clean_vite_config.py`; `rewrite_readme.py` | `lovable-artifacts.md`; `cleanup-checklist.md` | `clean-readme.tmpl.md` |
| `/docs` | `link_check.py`; `toc_generate.py`; `agent_skill_index.py`; `stale_doc_scan.py` | `docs-style-guide.md`; `doc-taxonomy.md`; `where-to-document.md` | `doc-page.tmpl.md`; `index-section.tmpl.md` |
| `/skill-create` | `validate_skill.py`; `score_description.py`; `scaffold_skill.py`; `resource_check.py` | `description-trigger-rubric.md`; `skill-folder-format.md`; `tool-selection-guide.md` | `SKILL.md.tmpl`; `scripts-readme.tmpl.md`; `references-readme.tmpl.md`; `assets-readme.tmpl.md` |

### Good shared helpers

Some helpers are useful across many skills and could live in a shared internal utility folder if this repo later supports that:

- `detect_project.py` — detect stack, package manager, test command, repo root.
- `git_context.py` — branch, merge base, staged files, changed files, dirty counts.
- `markdown_lint_light.py` — validate headings, links, and fenced blocks without requiring a heavy external dependency.
- `frontmatter_validate.py` — validate `name`, `description`, `allowed-tools`, and folder layout for skills.
- `template_fill.py` — tiny placeholder replacement for assets like `*.tmpl.md` and `*.tmpl.tsx`.

### Reference files worth centralizing

These are high-value because multiple skills would read them:

- `references/conventional-commits.md`
- `references/review-severity-rubric.md`
- `references/react-architecture-rules.md`
- `references/tanstack-boundaries.md`
- `references/testing-rubric.md`
- `references/docs-style-guide.md`
- `references/skill-description-rubric.md`

The rule of thumb: if the content is long, stable, and read-only, make it a reference. If it is copied or filled in, make it an asset. If it makes a decision or validates output, make it a script.

## Pattern: skill vs agent

| Use a skill when… | Use an agent when… |
|---|---|
| The flow is short, deterministic, mostly tool calls | The work is open-ended, exploratory, or large |
| You want it to run in the current context | You want context isolation (a clean window) |
| Output should land directly in the conversation | Output should be a single summary message |
| You'll trigger it explicitly with `/name` | You want autonomous routing on description match |

A skill can call an agent (via the `Task` tool) and an agent can be invoked from a skill — they compose.

## Adding a skill

1. Create `global/skills/<name>.md`:
   ```yaml
   ---
   name: <name>
   description: One sentence — what triggers it, what it does.
   allowed-tools: Bash, Read
   ---
   ```
2. Body = the instruction Claude follows when you invoke it.
3. `python setup/settings-configurator-ui.py` → restart.

Use `/skill-create` if you want guided drafting and trigger-accuracy checks.
