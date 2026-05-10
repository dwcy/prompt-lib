# ADR — Architecture Decision Record

Create a new Architecture Decision Record for the current project.

**Usage:** `/adr [title]`

---

## Step 1 — Locate the ADR directory

Always use `docs/adr/` relative to the project root. Do **not** create it yet — you'll create it alongside the file in Step 4.

---

## Step 2 — Determine the next ADR number

List all files matching `[0-9]*.md` in the ADR directory. Find the highest existing number and increment by 1. Use 4-digit zero-padded format: `0001`, `0002`, etc.

If no ADRs exist yet, start at `0001`.

---

## Step 3 — Collect the decision content

If `$ARGUMENTS` is non-empty, treat it as the ADR title and skip asking for one.

Ask the user for each of the following in sequence. Wait for each answer before asking the next — do not batch all questions at once.

1. **Title** (if not provided via `$ARGUMENTS`): A short imperative phrase, e.g. "Use PostgreSQL for the primary data store".

2. **Status**: One of `Proposed`, `Accepted`, `Deprecated`, `Superseded`. Default to `Proposed` if the user is unsure.

3. **Context**: What is the situation, constraint, or problem that necessitates a decision? Include relevant forces — technical, organisational, time-based. Write this as neutral background, not as advocacy for the decision.

4. **Decision**: What was decided? State it clearly and directly. Begin with "We will …" or "We have decided to …".

5. **Consequences**: What happens as a result — good, bad, and neutral? Be honest about downsides. At least one positive and one negative consequence should be listed if applicable.

6. **Alternatives considered** *(optional — ask once, skip if user says no)*: What other options were evaluated and why were they rejected?

---

## Step 4 — Write the ADR file

Derive a kebab-case slug from the title (lowercase, spaces → hyphens, strip punctuation).

File path: `<adr-dir>/<number>-<slug>.md`

Example: `docs/adr/0003-use-postgresql-for-primary-data-store.md`

Use this exact template. Do not add extra sections or change the heading names.

```markdown
# <NUMBER>. <Title>

Date: <YYYY-MM-DD using today's date>

## Status

<Status>

## Context

<Context content>

## Decision

<Decision content>

## Consequences

<Consequences content>

## Alternatives Considered

<Alternatives content, or omit this section entirely if none were provided>
```

---

## Step 5 — Confirm and report

After writing the file:

- Print the full file path.
- Print the ADR number and title.
- Ask: "Should I add a link to this ADR from any existing documentation (e.g. README, CLAUDE.md)?"

If the user says yes, find the relevant file, locate a natural place for an ADR reference, and add a one-line link. Do not restructure the target document.
