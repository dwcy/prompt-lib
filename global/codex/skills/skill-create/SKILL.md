---
name: skill-create
description: Create, draft, and refine a new Claude Code skill (slash command). Use this skill whenever someone wants to build a new /skill, automate a workflow into a repeatable skill, capture a process they keep doing manually, convert a conversation into a reusable command, or improve an existing skill's description, instructions, or triggering accuracy. Even if the user just says "make this a skill" or "save this as a command", use this skill.
allowed-tools: Read, Write, Edit, Glob, Bash
---

You are helping design, write, test, and refine a Claude Code skill.

A skill is an **Agent Skill folder** — a directory whose entry point is `SKILL.md` (frontmatter + instructions) and that may bundle scripts, reference docs, and assets alongside. Every skill this skill creates uses the full folder layout, even when some subfolders are initially empty.

Work through the stages in order, but stay flexible — if the user already has a draft, skip to testing and iteration. If they say "just write it", skip the interview and proceed.

## The Agent Skill folder layout (canonical)

```
my-skill/
├── SKILL.md        # Required: YAML frontmatter + instructions
├── scripts/        # Optional but always scaffolded: executable helpers
├── references/     # Optional but always scaffolded: long-form docs / specs / cheat-sheets
└── assets/         # Optional but always scaffolded: templates, snippets, prompts, fixtures
```

Subfolders are **always created**, even if empty. Empty subfolders get a `.gitkeep` plus a one-line `README.md` explaining what belongs there, so future contributors and Claude itself see the slot clearly.

---

## Stage 1 — Capture intent

If the user hasn't explained what the skill should do, ask these questions in a single message:

1. What should invoking this skill cause Claude to do?
2. When should it trigger — what phrases or situations? (This becomes the description.)
3. What tools will it need? (Bash, Read, Write, Edit, Glob — or none?)
4. What should the output look like? (A file written, a report in chat, a command run?)
5. Should it ask the user questions before acting, or proceed directly?

If the user is converting something from the current conversation into a skill, extract the answers from what's already been said — tool calls used, corrections made, the sequence of steps — and confirm before writing.

---

## Stage 2 — Interview for edge cases

Before writing the draft, think about what could go wrong or vary:

- What if the target file doesn't exist?
- What if the user gives no arguments?
- Are there multiple modes (e.g., `/skill scaffold` vs `/skill review`)?
- Are there environment-specific concerns (Windows paths, pnpm vs Bun, etc.)?
- Does it need to read AGENTS.md or project context first?

Ask only the questions whose answers would change how you write the skill. Don't interrogate — one round of questions, then proceed.

---

## Stage 3 — Plan the bundled resources (scripts / references / assets)

**This stage is mandatory.** Even if every subfolder ends up empty at first, you propose candidates so the user makes a conscious decision about what to bundle. Three buckets, distinct purposes:

| Bucket | What goes there | Examples |
|---|---|---|
| `scripts/` | Executable helpers Claude can run | Python/JS/PS1 utilities, codemod runners, validators, extractors, format-checkers |
| `references/` | Long-form documentation Claude reads but doesn't execute | API cheat-sheets, protocol specs, design-system rules, glossary, decision matrices |
| `assets/` | Templates and fixtures Claude copies or fills in | Code snippets, prompt templates, test fixtures, JSON/YAML scaffolds, boilerplate files |

### Suggest concrete candidates

Based on what the skill does, propose at least one realistic candidate per bucket. Present them as a single message and ask which (if any) the user wants. Use this shape:

> Based on what this skill does, here's what could live in the bundled folders. Pick any combination, or say "none" for any bucket and I'll scaffold it empty for later.
>
> **scripts/**
> - `<name>.py` — <one-line purpose> (e.g., `validate_output.py` — checks the produced file against a schema)
> - `<name>.py` — <alternative>
>
> **references/**
> - `<name>.md` — <one-line purpose> (e.g., `api-cheatsheet.md` — endpoints + auth shapes)
> - `<name>.md` — <alternative>
>
> **assets/**
> - `<name>.<ext>` — <one-line purpose> (e.g., `commit-template.md` — boilerplate commit message)
> - `<name>.<ext>` — <alternative>

### Common candidates by skill type

If the skill is about... | scripts/ candidates | references/ candidates | assets/ candidates
---|---|---|---
**Code review / audit** | `extract_findings.py`, `scan_changes.sh` | `severity-rubric.md`, `house-style.md` | `review-template.md`
**Scaffolding / codegen** | `gen.py`, `rename.sh` | `architecture-rules.md`, `naming-conventions.md` | `component.tsx.tmpl`, `module.py.tmpl`
**Workflow automation** (commit, PR, release) | `validate.py`, `format_msg.py` | `convention-spec.md` | `commit-template.md`, `pr-body.md`
**Migration / refactor** | `codemod.py`, `dry_run.sh` | `migration-plan.md`, `compat-matrix.md` | `before.ts`, `after.ts` fixtures
**Documentation** | `link_check.py`, `toc_gen.py` | `style-guide.md` | `page-template.md`, `frontmatter.yml`
**Memory / knowledge** | `extract.py`, `validate.py`, `remove.py` | `categories.md` | `entry-template.md`
**Testing** | `run_focused.sh`, `summarise_failures.py` | `coverage-targets.md` | `fixture.json`, `test-case.tmpl.ts`

Pick from these as starting points; tailor names + descriptions to the actual skill.

### Empty is fine — but explicit

If the user says "none" for any bucket, scaffold it empty with:

- `.gitkeep` — empty file so git tracks the directory
- `README.md` — one paragraph: "This folder is for X. Drop files here when Y."

This makes it obvious that the bucket exists and is intentionally empty, not forgotten.

---

## Stage 4 — Write the skill draft

### Frontmatter rules

```yaml
---
name: skill-name           # kebab-case, matches the /command
description: ...           # see "Writing the description" below
allowed-tools: Bash, Read  # only tools this skill actually needs
---
```

### Writing the description — the most important field

The description is the **primary trigger mechanism**. Claude decides whether to use a skill based on this field alone. Three rules:

1. **The system-reminder shows only the first 64 characters.** Anything after that is cut with `…` and invisible until the skill is already invoked. Put the most critical trigger condition — especially proactive ones — in the first 64 characters. Test it: count the first 64 chars of your description and ask "is the right trigger visible here?"
2. **Include both WHAT it does AND WHEN to use it** — all "when to use" information goes in the description, not the body.
3. **Be pushy** — Claude tends to undertrigger skills. Write descriptions that lean toward triggering. Instead of "Generates a commit message", write "Generates a conventional commit message from staged changes. Use this whenever the user asks to commit, stage changes, write a git message, or says anything like 'commit this' or 'let's commit'."

Test the description mentally: if someone typed a realistic user request, would this description match it clearly within the first 64 characters?

### Writing the body — explain WHY, not just WHAT

- Use imperative form: "Read the file first", not "The file should be read"
- Explain the reasoning behind instructions — Claude follows instructions better when it understands the purpose
- Avoid heavy-handed MUST/NEVER in all caps — reframe as the reason the constraint matters
- Keep the body under 500 lines; if it's growing larger, extract reference content to `references/<topic>.md` and link to it
- Use intermediate headers to structure multi-step workflows
- Include output format templates if the skill produces structured output
- **Reference bundled resources by relative path** — e.g., `python scripts/validate.py`, `see references/api-cheatsheet.md`, `copy assets/commit-template.md`

### Output format templates (when relevant)

Define the exact structure you want:

```markdown
## Output format
Always use this structure:

**Summary:** one sentence
**Changes:** bullet list
**Next step:** single action
```

### Example structure for a folder-based skill

```
my-skill/
├── SKILL.md
├── scripts/
│   └── validate.py        # populated, or .gitkeep + README.md if empty
├── references/
│   └── api-cheatsheet.md
└── assets/
    └── commit-template.md
```

```markdown
---
name: my-skill
description: Does X. Use this when the user wants to Y, asks about Z, or says anything like "help me with X".
allowed-tools: Bash, Read
---

[One sentence explaining the skill's goal and why it exists]

## Step 1 — [verb phrase]

[Why this step matters, then what to do]

```bash
python scripts/validate.py <input>
```

## Step 2 — [verb phrase]

For the API contract, read [`references/api-cheatsheet.md`](references/api-cheatsheet.md).
For the output template, copy [`assets/commit-template.md`](assets/commit-template.md) and fill in the placeholders.

## Output

[Template or description of expected output]
```

---

## Stage 5 — Choose a name and place the folder

**Name rules:**
- kebab-case, short, verb-first if possible: `react-review`, `git-commit`, `css-scaffold`
- Must not conflict with an existing skill — `Glob` `~/.agents/skills/*.md` AND `~/.agents/skills/*/SKILL.md` to check both legacy single-file skills and folder skills

**Where to save:**
- Global skill (available in every project) → `global/skills/<name>/` (deploys to `~/.agents/skills/<name>/`)
- Project skill (this project only) → `.agents/skills/<name>/`

Ask the user which scope before writing, unless it's obvious from context.

### Files to create (every skill)

```
<scope>/skills/<name>/
├── SKILL.md                # written from Stage 4
├── scripts/
│   ├── <script files>      # any from Stage 3, else:
│   ├── .gitkeep
│   └── README.md           # "This folder is for executable helpers used by SKILL.md."
├── references/
│   ├── <reference files>   # any from Stage 3, else:
│   ├── .gitkeep
│   └── README.md           # "This folder is for long-form docs / specs the skill reads."
└── assets/
    ├── <asset files>       # any from Stage 3, else:
    ├── .gitkeep
    └── README.md           # "This folder is for templates / snippets / fixtures the skill copies or fills."
```

After writing, remind the user:
- Global skills: run `python setup/settings-configurator-ui.py` then restart Claude Code
- Project skills: active immediately in this session

---

## Stage 6 — Generate 2–3 test prompts

Come up with realistic test cases — the kind of thing a real user would actually type. Not abstract ("test the skill"), but concrete and specific:

**Good:** `"ok I've staged my login form changes and want to commit, the issue was a broken redirect after OAuth"`
**Bad:** `"test the commit skill"`

Share the test prompts with the user and ask if they look right before running them. Then mentally walk through how the skill would handle each one — trace the steps, identify where it might fail or behave unexpectedly.

For each test prompt, answer:
- Would the description trigger the skill for this prompt?
- Does the skill body handle this case?
- What would the output look like?
- If bundled resources are referenced, do they exist at the expected relative paths?

Report the walkthrough to the user so they can validate.

---

## Stage 7 — Iterate based on feedback

After the user reviews the test walkthrough (or tries the skill for real):

1. Identify what failed or felt wrong
2. Diagnose the root cause — was it the description (wrong trigger), the instructions (wrong steps), the output format, or a missing/broken bundled resource?
3. Fix the root cause, not the symptom
4. Re-read the revised skill with fresh eyes before presenting it

**Common failure patterns:**
- Skill not triggering → description isn't pushy enough or missing key synonyms
- Skill doing too much → body is too prescriptive; simplify and explain the goal instead
- Wrong output format → add an explicit output template
- Missing edge case → add a short paragraph covering it, explain why it matters
- Script referenced but missing → either write it now or remove the reference

Keep iterating until the skill handles its test cases cleanly.

---

## Stage 8 — Optimize the description (optional)

Once the skill is working, offer to review the description for triggering accuracy:

Generate 10 test queries — 5 that should trigger this skill, 5 that should not (but are close enough to be tricky):

```
Should trigger:
1. [realistic user prompt]
2. [different phrasing of same intent]
3. [casual/abbreviated version]
4. [edge case that still belongs to this skill]
5. [user who doesn't name the skill but clearly needs it]

Should NOT trigger (near-misses):
6. [shares keywords but needs a different skill/tool]
7. [adjacent domain, different intent]
8. [ambiguous — could go either way, but shouldn't]
9. [too simple to need this skill]
10. [different file type or scope]
```

Walk through each query and check whether the current description would trigger correctly. If not, adjust the description until all 10 are handled correctly, then report the before/after.

---

## What makes a great skill

- **Specific description** — a stranger reading only the description knows exactly when to use it
- **Pushy but not vague** — errs toward triggering, but on the right things
- **Why-driven instructions** — explains the purpose behind each step, not just the mechanics
- **Handles the no-argument case** — always defined what happens if the user gives no input
- **Defined output** — the user knows what they're going to get before they run it
- **Short enough to scan** — if you can't read the whole body in 2 minutes, it's too long
- **Bundled resources are real** — every script, reference, or asset mentioned in SKILL.md actually exists at the path stated
- **Empty buckets are explicit** — `.gitkeep` + one-line README.md, never silently absent
