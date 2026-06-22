---
name: executing-plans
description: Use when you have a written implementation plan to execute in a separate session with review checkpoints
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

Announce at start: "I'm using the executing-plans skill to implement this plan."

Note: Tell your human partner that this skill works much better with access to subagents. The quality of its work will be significantly higher if run on a platform with subagent support (such as Claude Code or Codex).

## The Process

### Step 1: Load and Review Plan

- Read the plan file
- Review critically — identify any questions or concerns about the plan
- If concerns: Raise them with your human partner before starting
- If no concerns: Create tasks and proceed

### Step 2: Execute Tasks

For each task:

1. Mark as in_progress
2. Follow each step exactly (plan has bite-sized steps)
3. Run verifications as specified
4. Mark as completed

### Step 3: Complete Development

After all tasks complete and verified:

Announce: "I'm using the finishing-a-development-branch skill to complete this work."

Then follow the finishing-a-development-branch skill to verify tests, present options, and execute the chosen completion path.

## When to Stop and Ask for Help

STOP executing immediately when:

- Hit a blocker (missing dependency, test fails, instruction unclear)
- Plan has critical gaps preventing starting
- You don't understand an instruction
- Verification fails repeatedly

Ask for clarification rather than guessing.

## When to Revisit Earlier Steps

Return to Review (Step 1) when:

- Partner updates the plan based on your feedback
- Fundamental approach needs rethinking

Don't force through blockers — stop and ask.

## Rules

- Review plan critically first
- Follow plan steps exactly
- Don't skip verifications
- Stop when blocked, never guess
- Never start implementation on main/master branch without explicit user consent

## Integration

Required workflow skills:

- **using-git-worktrees** — Ensures isolated workspace (creates one or verifies existing)
- **writing-plans** — Creates the plan this skill executes
- **finishing-a-development-branch** — Complete development after all tasks
