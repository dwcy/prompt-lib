---
name: systematic-debugging
description: Root-cause-first debugging process. Use when a test fails, a bug is reported, behaviour differs from what was expected, an earlier fix did not hold, or the user says "why does this happen", "it's still broken", "flaky test", "works locally but not in CI", "stop guessing", or asks to debug, investigate, or fix an error — invoke before proposing any fix.
allowed-tools: Bash, Read, Glob, Grep
---

Announce: "I'm using the systematic-debugging skill."

## The rule

No fix before the root cause is understood. A fix aimed at a symptom passes the check that is in front of you and leaves the defect in place. The second failure costs more than the investigation would have, because by then two changes are tangled together.

The four phases below are sequential. Skipping ahead is the failure mode this skill exists to stop.

## Phase 1 — Reproduce and read

- Read the actual error text and the full stack trace. Not the summary line, the whole thing. The frame that matters is often three frames down.
- Reproduce it on purpose with the smallest command that shows the failure. Put that command in the report; it is the verification command for Phase 4.
- Find the exact line and the state at that line. Add a temporary print or breakpoint if needed; remove it before finishing.
- Check what changed: `git -C <repo> log --oneline -15 -- <affected paths>` and `git -C <repo> diff HEAD -- <affected paths>`. A failure that appeared today usually has a cause from today.
- Decide which layer owns the failure. When our feature "doesn't work" against an external service or library, debug our code path first: our request, our parsing, our config. Blaming the dependency is a hypothesis, not a finding.

Stop condition for this phase: you can say, in one sentence, what the program does at the failing point and what it was supposed to do.

## Phase 2 — Look for the pattern

- Find a working counterpart: a sibling test, a similar endpoint, the same widget on another screen. Diff the two paths.
- Check whether the same defect exists elsewhere. One bad copy of a pattern usually has siblings.
- If the failure is intermittent, treat timing as the prime suspect and read [`references/condition-based-waiting.md`](references/condition-based-waiting.md) before touching the code.
- If a test passes alone but fails in the suite, another test is polluting shared state. Run `python scripts/find_polluter.py <failing test id>` to bisect the suite down to the one test that leaves the state behind.

## Phase 3 — Hypothesis and experiment

- Write the hypothesis as one sentence: "X causes Y because Z." If you cannot write it, you are still in Phase 1.
- Design the smallest experiment that would prove the hypothesis wrong. Change one variable. Predict the outcome before running.
- Run it. If the prediction was wrong, the hypothesis is dead; go back to Phase 2 with what you learned. Do not patch the experiment until it "works".

## Phase 4 — Fix and verify

- Fix the cause named in the hypothesis. If the fix touches a different place than the hypothesis pointed at, the hypothesis was wrong; say so and go back.
- Where the project has a test suite, add a regression test that fails before the fix and passes after it. This is the proof that you fixed the cause and not the symptom.
- Run the reproduction command from Phase 1 and the relevant suite. Report the actual output. "Should be fixed now" is not a report.
- Remove every temporary print, breakpoint, and debug flag you added.

## The three-strikes rule

When three fixes for the same failure have not held, stop fixing. Three failed fixes is not bad luck; it means the mental model of the code is wrong, and the fourth attempt made from the same model will fail the same way.

Write down what each failed fix assumed, then step back to the design: which component owns this state, which contract was violated, which assumption in the plan does not match the code. Bring that to the user as a design question, not as a fourth patch.

## Red flags

| What you are about to say | What it actually means |
|---|---|
| "Let me just try changing X" | No hypothesis. Back to Phase 3. |
| "It's probably the library / the network / the CI runner" | Unverified blame. Back to Phase 1, our code path first. |
| "I'll add a retry / a sleep / a try-except around it" | Hiding the symptom. The cause is still there. |
| "The error message is misleading, ignore it" | You have not read the whole trace yet. |
| "This should fix it" | No verification. Run the command, paste the output. |
| "Let me rewrite this part cleanly" | Refactoring as debugging. It moves the bug and destroys the reproduction. |
| Fourth fix attempt for the same failure | Three-strikes rule. Stop and question the design. |

## Signals from the user

"Stop guessing", "did you actually read the error", "it's still broken", "that's the third time" all mean the same thing: the process was skipped. Return to Phase 1, say which phase was skipped, and do it properly.

## Afterwards

When the root cause was not obvious from reading the code, record it so it is not rediscovered: `/self-improvement` in projects that carry it, or the session memory otherwise. Store the mechanism, not the incident.

## Integration

- `~/.claude/rules/tests.md` holds the no-fixed-sleeps rule for test files; this skill's condition-based-waiting reference is the how-to behind it.
- `/self-improvement` captures the non-obvious root cause as a lesson.
- `@code-plan-verifier` checks the finished fix against the plan when one exists; it does not replace the investigation.
