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

### E-20260629-02 — Default Cabal Python support to 3.14
- **Task**: Replace multi-version/lower Python defaults with Python 3.14 across CI, package metadata, Cabal runtime installers, launchers, docs, and fast fake test envs.
- **Constraints followed?** Yes — kept launcher prompts plain-language while enforcing the version internally, and preserved intentional legacy cache fixtures.
- **Unverified assumptions?** Minimal — treated active defaults/build surfaces as in scope and historical/spec-only version mentions as out of scope.
- **Verified current facts?** Yes — searched active files for Python version drift and ran focused Cabal/tool tests under Python 3.14.6.
- **Requested format?** Yes — implemented the correction directly.
- **To remember**:
  - P-20260629-01 (default Python support baseline is 3.14)
- **To unlearn**: nothing.

### E-20260716-01 — Add Claude forwarding and release intelligence
- **Task**: Audit all global Claude agents for forwarded subagent output, then add a live Claude Code changelog with Added entries visible, other categories disclosed on demand, and highlighted service health.
- **Constraints followed?** Yes — audited all 29 agent definitions, placed the shared opt-in at the harness/settings boundaries, preserved unrelated documentation work, and used only official Claude sources.
- **Unverified assumptions?** Minimal — selected the existing Claude Info screen as the discoverable UI surface after inspecting its callers and verified both live feed formats before implementing parsers.
- **Verified current facts?** Yes — checked Claude Code 2.1.211 help, parsed the live official changelog and status summary, ran the full 433-test setup suite under Python 3.14, and ran the 213-test A2A suite.
- **Requested format?** Yes — Added entries are expanded per version, other categories are collapsed behind a click, and Claude Code health is color-coded with active incident context.
- **To remember**:
  - M-20260716-01 (invoke root Cabal tests through the project Python interpreter)
- **To unlearn**: nothing.

### E-20260810-01 — Route web and Tauri through the root launcher
- **Task**: Make the root `run`/`run.cmd` launch the browser workspace and Tauri desktop app while preserving the settings TUI default.
- **Constraints followed?** Yes — kept bare `run` behavior unchanged, delegated to existing app launchers, preserved user changes, and did not commit.
- **Unverified assumptions?** Minimal — inferred the requested interface as `run web` and `run tauri`, then documented and exercised those exact commands.
- **Verified current facts?** Yes — `run.cmd web --help`, multi-argument web forwarding, `run.cmd tauri --help`, the existing `run.cmd --version` route, PowerShell parsing, and diff checks passed.
- **Requested format?** Yes — both graphical apps now start from the same root command file.
- **To remember**:
  - M-20260810-01 (preserve one-item PowerShell forwarding arrays)
- **To unlearn**: nothing.

### E-20260811-01 — Repair mixed-version Overview system panel
- **Task**: Fix the machine panel's `Not Found` state against an already-running older Cabal backend.
- **Constraints followed?** Yes — preserved the requested 3/4 machine and 1/4 GitHub layout and avoided forcing a backend restart.
- **Unverified assumptions?** Initially assumed frontend and backend would restart together; the live handshake disproved that assumption.
- **Verified current facts?** Yes — confirmed the live route returned 404, verified all four fallback endpoints returned 200, rebuilt the frontend, and ran 54 tests.
- **Requested format?** Yes — the panel now shows useful machine data and reserves “Restart required” for unavailable revision metadata.
- **To remember**: M-20260811-01 (new UI routes need mixed-version fallback coverage).
- **To unlearn**: nothing.

### E-20260811-02 — Separate terminal configuration from the computer header
- **Task**: Keep package-manager metadata under the OS, remove the shell path from that line, add a terminal settings panel, and simplify Cabal update status.
- **Constraints followed?** Yes — retained the 3/4 computer and 1/4 GitHub row, kept package-manager placement, added read-only terminal discovery, and exposed no shell-profile content.
- **Unverified assumptions?** Minimal — terminal discovery reports supported installed shells and safe configuration categories; platform-specific tools not present on this machine remain hidden in the UI.
- **Verified current facts?** Yes — the live authenticated endpoint reports `winget`, no machine `shell` field, four installed shells, Windows Terminal, its default profile, and five configuration categories; production build, 54 frontend tests, and focused Python tests passed.
- **Requested format?** Yes — `Latest version` occupies one status slot and becomes a yellow `Update` link only when an update is available; no `Up to date` control exists.
- **To remember**:
  - M-20260811-02 (passive Cabal status is not a disabled action)
  - P-20260811-01 (keep machine and terminal metadata separated)
- **To unlearn**: nothing.

### E-20260811-03 — Center the Windows/Cabal header split
- **Task**: Put the Windows/Cabal divider in the middle and keep all Cabal version metadata on the Cabal name row with status last.
- **Constraints followed?** Yes — retained package-manager placement, the outer 3/4 computer and 1/4 GitHub split, and the conditional yellow update action.
- **Unverified assumptions?** No — encoded the requested sequence in component structure and a focused DOM-order assertion.
- **Verified current facts?** Yes — focused lint passed, production build passed, and all six Overview component tests passed.
- **Requested format?** Yes — the inner header is exactly 50/50 and the Cabal row is name/version, hash, date, state/action.
- **To remember**:
  - M-20260811-03 (preserve the requested header axis and metadata order)
- **To unlearn**: nothing.

### E-20260811-04 — Correct Environment switch visual parity
- **Task**: Fix the shared Environment switch after the user reported that it did not look like the reference design.
- **Constraints followed?** Yes — corrected the shared control itself and kept the Environment behavior unchanged.
- **Unverified assumptions?** Rendered comparison remains unavailable because no in-app browser is connected; I did not claim screenshot parity.
- **Verified current facts?** Yes — compared every switch value against the checked-in design markup, fixed the generic hover cascade, and passed focused tests, lint, and production build.
- **Requested format?** Yes — replaced approximate accent styling with the exact design track, border, knob, and dimensions.
- **To remember**: M-20260811-04 (visual parity requires rendered evidence).
- **To unlearn**: nothing.

### E-20260811-05 — Remove remaining switch approximations
- **Task**: Retry the Environment switch implementation under the explicit never-approximate rule.
- **Constraints followed?** Yes — copied the reference's off/on colors, 150ms timing, and left-position knob movement exactly.
- **Unverified assumptions?** Rendered comparison remains unavailable because the in-app browser is still not connected.
- **Verified current facts?** Yes — source values match the checked-in reference; focused tests, lint, and production build pass.
- **Requested format?** Yes — removed transform motion, 120ms timing, token substitutions, and disabled fading that differed from the reference.
- **To remember**: P-20260811-02 and M-20260811-04.
- **To unlearn**: nothing.

### E-20260811-06 — Enable unset Environment secrets
- **Task**: Fix editable environment values that could not be switched on, using an unset secret as the regression case.
- **Constraints followed?** Yes — preserved masking and exact switch styling while changing only the interaction state model.
- **Unverified assumptions?** Rendered browser verification remains unavailable because no in-app browser is connected.
- **Verified current facts?** Yes — backend metadata marks curated entries editable; the focused five-test suite, lint, and production build pass.
- **Requested format?** Yes — switching on an unset secret now opens an empty password field and entering a value stages Apply.
- **To remember**: M-20260811-05.
- **To unlearn**: nothing.

### E-20260811-07 — Complete global toggle and secret reveal controls
- **Task**: Correct the remaining toggle design mismatch and add a proper show/hide eye to secret inputs.
- **Constraints followed?** Yes — used the checked-in reference values and state opacity without inventing alternate toggle styling.
- **Unverified assumptions?** Rendered browser comparison remains unavailable because the in-app browser is not connected.
- **Verified current facts?** Yes — all three switch call sites now use one component; 54 non-Overview tests, lint, and the production build pass.
- **Requested format?** Yes — off rows dim exactly as specified and secret inputs have accessible eye/eye-off controls.
- **To remember**: M-20260811-06.
- **To unlearn**: nothing.

### E-20260812-01 — Add running web apps control
- **Task**: Add a Services view listing listening apps by port, PID, name, and location with confirmation-guarded shutdown.
- **Constraints followed?** Yes — preserved unrelated WIP, reused the action-safety protocol, excluded Cabal's own backend, and did not commit.
- **Unverified assumptions?** Interpreted the user's “sid” as PID; live visual inspection remained unavailable because no in-app browser target was connected.
- **Verified current facts?** Yes — 56 Python tests, 62 frontend tests, targeted lint, production build, and whitespace checks passed.
- **Requested format?** Yes — implemented the table, refresh behavior, process discovery, stable identity validation, and shutdown action.
- **To remember**: M-20260812-01 (normalize differing psutil connection record shapes).
- **To unlearn**: nothing.

### E-20260812-02 — Add all-state Docker apps panel
- **Task**: Add a separate Services panel for all Docker containers with status, ports, Compose location, and safe Start/Stop actions.
- **Constraints followed?** Yes — included running, stopped, and unusual states; preserved unrelated WIP; reused confirmation tickets; made Docker absence non-fatal.
- **Unverified assumptions?** Live visual inspection remained unavailable because no in-app browser target was connected.
- **Verified current facts?** Yes — read the local Docker 29.7.2 output shape, detected all three live containers and Compose locations, passed 60 Python tests, 63 frontend tests, targeted lint, build, and whitespace checks.
- **Requested format?** Yes — Docker containers are in a separate panel with lifecycle actions matched to current state.
- **To remember**: No new durable lesson; behavior is explicit in tests and implementation.
- **To unlearn**: nothing.
