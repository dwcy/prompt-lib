---
name: skill-create
description: Create, draft, and refine a new Claude Code skill (slash command). Use this skill whenever someone wants to build a new /skill, automate a workflow into a repeatable skill, capture a process they keep doing manually, convert a conversation into a reusable command, or improve an existing skill's description, instructions, or triggering accuracy. Even if the user just says "make this a skill" or "save this as a command", use this skill.
allowed-tools: Read, Write, Edit, Glob, Bash
---

You are helping design, write, test, and refine a Claude Code skill. A skill is a slash command — a markdown file with frontmatter that injects instructions into the current conversation when invoked.

Work through the stages below in order, but stay flexible — if the user already has a draft, skip to testing and iteration. If they say "just write it", skip the interview and proceed.

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
- Are there environment-specific concerns (Windows paths, Bun vs npm, etc.)?
- Does it need to read CLAUDE.md or project context first?

Ask only the questions whose answers would change how you write the skill. Don't interrogate — one round of questions, then proceed.

---

## Stage 3 — Write the skill draft

### Anatomy of a skill file

```
skills/
└── skill-name.md
    ├── YAML frontmatter  (name, description, allowed-tools)
    └── Markdown body     (instructions Claude follows when the skill is active)
```

Bundled resources (scripts, references, templates) live alongside the skill in a folder if needed, but the `.md` file is the entry point.

### Frontmatter rules

```yaml
---
name: skill-name           # kebab-case, matches the /command
description: ...           # see "Writing the description" below
allowed-tools: Bash, Read  # only tools this skill actually needs
---
```

### Writing the description — the most important field

The description is the **primary trigger mechanism**. Claude decides whether to use a skill based on this field alone. Two rules:

1. **Include both WHAT it does AND WHEN to use it** — all "when to use" information goes in the description, not the body.
2. **Be pushy** — Claude tends to undertrigger skills. Write descriptions that lean toward triggering. Instead of "Generates a commit message", write "Generates a conventional commit message from staged changes. Use this whenever the user asks to commit, stage changes, write a git message, or says anything like 'commit this' or 'let's commit'."

Test the description mentally: if someone typed a realistic user request, would this description match it clearly?

### Writing the body — explain WHY, not just WHAT

- Use imperative form: "Read the file first", not "The file should be read"
- Explain the reasoning behind instructions — Claude follows instructions better when it understands the purpose
- Avoid heavy-handed MUST/NEVER in all caps — reframe as the reason the constraint matters
- Keep the body under 500 lines; if it's growing larger, extract reference content to a separate file and point to it
- Use intermediate headers to structure multi-step workflows
- Include output format templates if the skill produces structured output

### Output format templates (when relevant)

Define the exact structure you want:

```markdown
## Output format
Always use this structure:

**Summary:** one sentence
**Changes:** bullet list
**Next step:** single action
```

### Example structure for a simple skill

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
# command to run
```

## Step 2 — [verb phrase]

[etc.]

## Output

[Template or description of expected output]
```

---

## Stage 4 — Choose a name and place the file

**Name rules:**
- kebab-case, short, verb-first if possible: `react-review`, `git-commit`, `css-scaffold`
- Must not conflict with an existing skill — Glob `~/.claude/skills/*.md` to check

**Where to save:**
- Global skill (available in every project) → `C:\projects\global\skills\<name>.md`
- Project skill (this project only) → `.claude/skills/<name>.md`

Ask the user which scope before writing, unless it's obvious from context.

After writing the file, remind the user:
- Global skills: run `bash scripts/apply-global-claude-settings.sh` then restart Claude Code
- Project skills: active immediately in this session

---

## Stage 5 — Generate 2–3 test prompts

Come up with realistic test cases — the kind of thing a real user would actually type. Not abstract ("test the skill"), but concrete and specific:

**Good:** `"ok I've staged my login form changes and want to commit, the issue was a broken redirect after OAuth"`
**Bad:** `"test the commit skill"`

Share the test prompts with the user and ask if they look right before running them. Then mentally walk through how the skill would handle each one — trace the steps, identify where it might fail or behave unexpectedly.

For each test prompt, answer:
- Would the description trigger the skill for this prompt?
- Does the skill body handle this case?
- What would the output look like?

Report the walkthrough to the user so they can validate.

---

## Stage 6 — Iterate based on feedback

After the user reviews the test walkthrough (or tries the skill for real):

1. Identify what failed or felt wrong
2. Diagnose the root cause — was it the description (wrong trigger), the instructions (wrong steps), or the output format?
3. Fix the root cause, not the symptom
4. Re-read the revised skill with fresh eyes before presenting it

**Common failure patterns:**
- Skill not triggering → description isn't pushy enough or missing key synonyms
- Skill doing too much → body is too prescriptive; simplify and explain the goal instead
- Wrong output format → add an explicit output template
- Missing edge case → add a short paragraph covering it, explain why it matters

Keep iterating until the skill handles its test cases cleanly.

---

## Stage 7 — Optimize the description (optional)

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
