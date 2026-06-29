# Evals

Post-task self-evaluation log. Each entry has an ID of the form `E-YYYYMMDD-NN` and is appended after a non-trivial task. Old evaluations can be removed once their lessons have been promoted to `lessons.md` / `mistakes.md`.

The evaluation questions:

1. Did I follow user constraints?
2. Did I make unverified assumptions?
3. Did I verify current facts when needed?
4. Did I produce the requested format?
5. What should be remembered? → new lessons / mistakes / preferences
6. What should be unlearned? → stale lessons to remove

---

### E-20260510-01 — Roll out parallel-subagent-isolation policy
- **Task**: `/plan` then implementation: 8 tasks ending in a v1.1.0 constitution amendment + canonical docs explainer + ADR.
- **Constraints followed?** Yes — single-track, no contract (no full-stack), template/skill/CLAUDE.md surfaces all touched, no force-push.
- **Unverified assumptions?** Assumed the Agent tool's `isolation: "worktree"` is the durable name of the parameter. Did not verify against a current harness release note — but it's named in the Agent tool description in this session, so the verification is implicit.
- **Verified current facts?** Read every target file before editing; confirmed `.specify/` structure, constitution version, template content.
- **Requested format?** Yes — task breakdown table, then sequenced edits, then commit + push.
- **To remember**:
  - L-20260511-01 (parallel isolation rule)
- **To unlearn**: nothing.

### E-20260618-01 - Codex setup agenda correction
- **Task**: Refocus from PR administration to the Codex setup implementation agenda, audit helper gaps, patch no-op local apply handling, commit and push.
- **Constraints followed?** Yes - kept `.agents/` out of the feature commit and staged only Codex setup files.
- **Unverified assumptions?** Initially assumed "agenda" meant PR lifecycle; corrected by user and recorded M-20260618-01.
- **Verified current facts?** Yes - read helper/screen code, parsed Python files, ran direct helper smoke; pytest unavailable in bundled runtime.
- **Requested format?** Yes - continued implementation work rather than PR metadata.
- **To remember**:
  - M-20260618-01 (agenda means feature hardening unless PR admin is explicit)
- **To unlearn**: nothing.

### E-20260510-02 — Branch + commit + push session work
- **Task**: Move all working-tree changes to `feat/parallel-subagent-isolation`, commit with agent authorship, push.
- **Constraints followed?** Mostly — agent authorship via `-c` flags ✓, no Co-Authored-By trailer ✓, push only because explicitly requested ✓. **One slip**: bundled unrelated WIP into the same `feat:` commit instead of splitting (see M-20260510-02).
- **Unverified assumptions?** Assumed `.todo/` was local-only when it was actually substantive backlog content the user wanted committed. Had to add a second commit when they redirected.
- **Verified current facts?** Yes — ran `git status --short`, `git ls-files`, `.gitignore` contents before staging.
- **Requested format?** Yes — proposed commit message in the conversation before running `git commit`.
- **To remember**:
  - M-20260510-01 (`-c` flag position on git commit)
  - M-20260510-02 (don't pollute `feat:` subjects with unrelated WIP)
  - M-20260510-03 (audit tracked-but-ignored files before any commit flow)
- **To unlearn**: nothing.

### E-20260623-01 — Cabal logo runtime corrections
- **Task**: Explain and fix the old header still showing, the `RenderStyles.node` error, and repeated source-run install prompts.
- **Constraints followed?** Yes — inspected current launcher/Textual environment before explaining; did not touch unrelated user WIP.
- **Unverified assumptions?** Reduced after testing; verified selected Python, installed dependency availability, Textual composition, `RichVisual` route, and widget `render_lines`.
- **Verified current facts?** Yes — `py -3` selects Python 3.14 with Textual 6.12.0; `CabalLogo` renders as `RichVisual`; `render_lines` succeeds.
- **Requested format?** Mostly — answered the two questions and patched the repo.
- **To remember**:
  - M-20260623-01 (asset fallback must be diagnostic)
  - M-20260623-02 (wrap dense Rich Text in Group for Textual)
- **To unlearn**: nothing.

### E-20260623-02 — Replace bad Cabal raster header
- **Task**: Respond to user correction that the rendered Cabal header looked terrible and replace the live TUI header with a terminal-native mark.
- **Constraints followed?** Yes — kept the packaged PNG asset, but stopped using half-block rasterization in the live UI.
- **Unverified assumptions?** Some subjective design judgement remains; verified the rendered plain shape at 100 and 60 columns and Textual render path.
- **Verified current facts?** Yes — syntax check passed; Textual harness reports `CabalLogo RichVisual`; `render_lines` succeeds.
- **Requested format?** Yes — fixed the result rather than defending it.
- **To remember**:
  - M-20260623-03 (terminal rasterization is not acceptable brand UI)
- **To unlearn**: nothing.

### E-20260623-03 — Redesign Cabal elephant mark after scale regression
- **Task**: Fix the Cabal terminal logo after user correction that the smaller sprite looked worse.
- **Constraints followed?** Yes — kept Pillow removed, kept the PNG as a packaged source asset, and changed only the terminal-native logo component.
- **Unverified assumptions?** Some visual judgement remains, but the sprite dimensions, trunk placement, and Textual render path were verified.
- **Verified current facts?** Yes — all sprite rows are 32 columns, rendered mark is 32x12 terminal cells, compile check passed, and Textual reports `CabalLogo RichVisual`.
- **Requested format?** Yes — implemented the visual correction rather than only explaining it.
- **To remember**:
  - M-20260623-04 (preserve silhouette before shrinking terminal logos)
- **To unlearn**: nothing.

### E-20260624-01 — Keep Cabal start screen scrolled to top
- **Task**: Prevent ProjectGateScreen from opening scrolled down to recent projects.
- **Constraints followed?** Yes — scoped the change to the startup chooser and added a focused regression test.
- **Unverified assumptions?** Minimal — verified Textual `focus` and `scroll_home` signatures before patching.
- **Verified current facts?** Yes — compile check passed and a direct async smoke with 12 fake recents confirmed `#gate-init` is focused and `#gate-scroll.scroll_y == 0`.
- **Requested format?** Yes — implemented the behavior fix.
- **To remember**:
  - M-20260624-01 (Textual startup tables can pull scroll down)
- **To unlearn**: nothing.

### E-20260624-02 — Repair compact Cabal elephant details
- **Task**: Fix 24x6 Cabal logo deformation around the left leg, trunk stripes, and ears.
- **Constraints followed?** Yes — kept the 24x6 size and changed the terminal-native sprite only.
- **Unverified assumptions?** Some visual judgement remains, but the sprite now maps directly at 24x6 instead of relying on sampling.
- **Verified current facts?** Yes — sprite rows are fixed at 24 columns, stripe count is verified, compile check passed, direct focused tests passed, and Textual reports `CabalLogo RichVisual`.
- **Requested format?** Yes — implemented the visual correction.
- **To remember**:
  - M-20260624-02 (tiny terminal logos need target-size sprites)
- **To unlearn**: nothing.

### E-20260624-03 — Move Cabal setup labels to outer wrapper
- **Task**: Move the existing update/version information into the outer start-screen wrapper and keep README there, while the inner setup wrapper says `Local setup`.
- **Constraints followed?** Yes — changed the EnvPanel/UpdatePanel wrapper ownership and focused regression test.
- **Unverified assumptions?** Minimal — corrected the label wording to the user's explicit hierarchy and verified the resulting Textual widget state.
- **Verified current facts?** Yes — compile check passed and a direct Textual `run_test` confirmed outer `#env-summary` owns `✓ Latest version ...`/README while inner `#env-info` owns only `Local setup`.
- **Requested format?** Yes — implemented the requested layout correction.
- **To remember**:
  - M-20260624-03 (Cabal outer wrapper owns update status/README labels)
- **To unlearn**: nothing.

### E-20260624-04 — Restore readable Cabal elephant size
- **Task**: Replace the broken 24x6 default elephant mark with a larger 32x12 terminal-native mark.
- **Constraints followed?** Yes — kept flat body color, horizontal trunk stripes, and no Pillow/runtime image rasterization.
- **Unverified assumptions?** Some visual judgement remains, but the new mark preserves the requested landmarks instead of squeezing them into 24x6.
- **Verified current facts?** Yes — compile check passed, focused logo tests passed directly, and a Textual `run_test` rendered the mounted `CabalLogo` at 32x12.
- **Requested format?** Yes — implemented the larger fallback the user allowed.
- **To remember**:
  - M-20260624-04 (increase logo size when tiny mark loses the elephant shape)
- **To unlearn**: nothing.

### E-20260624-05 — Nest Recent Projects inside Select project panel
- **Task**: Move the ProjectGateScreen Recent Projects panel inside the Select project panel and change the nested border color.
- **Constraints followed?** Yes — kept the action buttons in Select project and nested Recent Projects below them in the same outer panel.
- **Unverified assumptions?** Minimal — chose the existing light Cabal pink `#FF55A5` for the nested border because it matches other inner frames.
- **Verified current facts?** Yes — compile check passed and a Textual `run_test` confirmed the widget tree and resolved nested border color.
- **Requested format?** Yes — implemented the layout correction.
- **To remember**:
  - M-20260624-05 (start-screen workflow table belongs inside the Select project panel)
- **To unlearn**: nothing.

### E-20260624-06 — Fix Clone repo blue border
- **Task**: Correct the Clone repo button so the border no longer uses the blue primary variant.
- **Constraints followed?** Yes — matched the GitHub purple and removed the Textual primary variant from Clone repo.
- **Unverified assumptions?** Minimal — verified the mounted Textual styles for classes, background, text, and border edges.
- **Verified current facts?** Yes — compile check passed and a `run_test` confirmed `#gate-clone` has no `-primary` class and purple border edges.
- **Requested format?** Yes — implemented the missed visual fix.
- **To remember**:
  - M-20260624-06 (remove variant and verify borders when restyling Cabal buttons)
- **To unlearn**: nothing.

### E-20260624-07 — Align GitHub and Clone repo borders
- **Task**: Give both the EnvPanel GitHub button and the ProjectGate Clone repo button borders in their button colors.
- **Constraints followed?** Yes — applied explicit purple border rules to GitHub and kept Clone repo's purple border rule.
- **Unverified assumptions?** Minimal — verified both controls in the mounted app rather than only reading CSS.
- **Verified current facts?** Yes — compile check passed and `run_test` confirmed all four border edges on `#btn-github` and `#gate-clone` resolve to `#8B5CF6`.
- **Requested format?** Yes — implemented the paired visual fix.
- **To remember**:
  - M-20260624-07 (verify both sides of matched Cabal button styles)
- **To unlearn**: nothing.

### E-20260624-08 — Make purple button borders visibly fixed
- **Task**: Replace same-color GitHub/Clone borders with visible purple bevel edges.
- **Constraints followed?** Yes — kept both controls purple and changed the border treatment to readable light/dark purple edges.
- **Unverified assumptions?** Reduced — inspected Textual Button CSS, mounted styles, hover states, and exported SVG color presence.
- **Verified current facts?** Yes — compile check passed; `run_test` confirmed normal/hover edge colors, and exported SVG contains the visible bevel colors.
- **Requested format?** Yes — corrected the visual mistake and explained the actual lesson.
- **To remember**:
  - M-20260624-08 (same-color border is not a visible button border)
- **To unlearn**: nothing.

### E-20260624-09 — Place Local setup paths above buttons
- **Task**: Move Source/Claude/OpenAI/Gemini folder paths inside Local setup but above the action buttons.
- **Constraints followed?** Yes — kept the paths inside `#env-info` and moved them directly before `#env-tools-row`.
- **Unverified assumptions?** Minimal — verified mounted widget order instead of relying on source indentation.
- **Verified current facts?** Yes — compile check passed and `run_test` confirmed `#env-paths` immediately precedes `#env-tools-row`.
- **Requested format?** Yes — corrected the placement.
- **To remember**:
  - M-20260624-09 (Local setup paths go above the button row)
- **To unlearn**: nothing.

### E-20260624-10 — Move README to Local setup wrapper
- **Task**: Move the README border action from the outer setup wrapper to the inner Local setup wrapper.
- **Constraints followed?** Yes — outer wrapper keeps dynamic version status only; `#env-info` owns `Local setup` and `README`.
- **Unverified assumptions?** Minimal — verified mounted Textual border subtitles directly.
- **Verified current facts?** Yes — compile check passed and `run_test` confirmed outer subtitle is empty while inner subtitle contains `README` and `screen.readme`.
- **Requested format?** Yes — implemented the wrapper ownership change.
- **To remember**:
  - Updated M-20260624-03 (outer owns version status; inner owns README)
- **To unlearn**: Removed the stale README-on-outer part of M-20260624-03.

### E-20260624-11 — Fix Cabal copy to real OS clipboard
- **Task**: Correct the failed Cabal text-copy behavior after user reported copying still did not work.
- **Constraints followed?** Yes — patched the existing clipboard/app path and added regression coverage.
- **Unverified assumptions?** Reduced — verified Textual mouse-drag selection and a live OS clipboard round trip, restoring the original clipboard afterward.
- **Verified current facts?** Yes — compile check passed, direct `run_test` smokes passed, and `write_clipboard()` round-tripped on Windows.
- **Requested format?** Yes — implemented the fix rather than only explaining the previous miss.
- **To remember**:
  - M-20260624-10 (verify OS clipboard, not just Textual internal buffer)
- **To unlearn**: nothing.

### E-20260624-12 — Pin Cabal refresh loader to row edge
- **Task**: Fix the Cabal refresh loader so it is strictly right-aligned on the version row.
- **Constraints followed?** Yes — kept the existing version-row layout and patched the actual alignment bug.
- **Unverified assumptions?** Reduced — measured mounted Textual regions before and after the change.
- **Verified current facts?** Yes — compile check passed and `run_test` confirmed `refresh_region.right == version_row_region.right`.
- **Requested format?** Yes — implemented the visual bug fix.
- **To remember**:
  - M-20260624-11 (alignment fixes need mounted region assertions)
- **To unlearn**: nothing.

### E-20260624-13 — Stretch Recent Projects rendered table grid
- **Task**: Fix Recent Projects so the visible `DataTable` grid uses full width even when row content is short.
- **Constraints followed?** Yes — kept the three-column table and changed only ProjectGate-specific sizing.
- **Unverified assumptions?** Reduced — inspected the installed Textual `DataTable` source before using explicit column widths.
- **Verified current facts?** Yes — compile check passed and `run_test` confirmed rendered column widths and `virtual_size.width` equal `content_region.width`.
- **Requested format?** Yes — implemented the table layout correction.
- **To remember**:
  - M-20260624-12 (verify DataTable rendered grid width, not only widget width)
- **To unlearn**: nothing.

### E-20260624-14 — Align EnvPanel setup detail rows
- **Task**: Align the setup detail rows between the Cabal version line and Source block to the same left edge.
- **Constraints followed?** Yes — scoped the change to EnvPanel row layout and kept the existing vertical spacing.
- **Unverified assumptions?** Reduced — measured mounted Textual regions before and after moving the override into app CSS.
- **Verified current facts?** Yes — compile check passed and `run_test` confirmed `#env-version-meta`, `#env-row-system`, its first cell, and `#env-paths` all start at x=5.
- **Requested format?** Yes — implemented the visual alignment fix.
- **To remember**:
  - M-20260624-13 (global `Horizontal` requires app-level row exceptions)
- **To unlearn**: nothing.

### E-20260624-15 — Tighten Cabal logo-to-panel spacing
- **Task**: Reduce the visual gap between the Cabal elephant logo and the first panel on start/project views.
- **Constraints followed?** Yes — changed only the shared banner padding and added focused geometry tests.
- **Unverified assumptions?** Reduced — measured mounted Textual regions and confirmed the remaining blank row was internal bottom padding.
- **Verified current facts?** Yes — compile check passed and direct Textual smoke confirmed start/home banner bottom padding is 0 with panel gap 0.
- **Requested format?** Yes — implemented the UI spacing fix.
- **To remember**:
  - M-20260624-14 (logo spacing needs padding checks, not just region checks)
- **To unlearn**: nothing.

### E-20260629-01 — Check PR readiness for Cabal tools branch
- **Task**: Audit `010-cabal-tools-polish-part2` readiness, fix the env cache crash found during targeted tests, and classify full-suite failures.
- **Constraints followed?** Yes — used current git/test state, avoided committing without confirmation, and kept generated temp files out of the tree.
- **Unverified assumptions?** Some full-suite failures remain classified as outside this branch because they reproduce in untouched files; CI currently runs pylint only.
- **Verified current facts?** Yes — fetched/pruned origin, checked branch divergence, ran CI-style pylint, ran branch-relevant pytest, and inspected failing full-suite commands.
- **Requested format?** Mostly — continued the readiness pass; commit/push remains blocked on explicit confirmation.
- **To remember**:
  - L-20260629-01 (persisted cache schemas need legacy fixtures)
- **To unlearn**: nothing.
