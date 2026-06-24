# Mistakes

Concrete failures from past sessions, recorded so they aren't repeated. Each entry has an ID of the form `M-YYYYMMDD-NN`. Remove entries that no longer apply.

---

### M-20260510-01 — Used `-c` after `commit` instead of before
- **Date**: 2026-05-10
- **Situation**: Tried to set agent authorship with `git commit -c user.email=... -c user.name=... -m "..."` and got `fatal: options '-m' and '-c' cannot be used together`.
- **Root cause**: `-c key=val` is a flag on the `git` program, not on the `commit` subcommand.
- **Future rule**: Always write `git -c user.email="my@agent.commit" -c user.name="Claude Agent" commit -m "..."`. Note the position: `-c` before `commit`.
- **Example**: See commit `0f73610` for the correct form.

### M-20260510-02 — Mixed user WIP into a feature-named commit without flagging it
- **Date**: 2026-05-10
- **Situation**: User asked to put "all changes" on a feature branch. Working tree contained both session work (parallel-isolation policy) and unrelated WIP (services/, statusline.py). Committed everything under a `feat:` subject line.
- **Root cause**: Took "all changes" too literally without sequencing the unrelated work into its own commit.
- **Future rule**: When a working tree contains unrelated changes and the user asks for "all changes" on a feature branch, group commits by concern: the headline feature gets the `feat:` commit, unrelated WIP gets a separate commit (`chore: include in-flight services WIP` or similar). Don't let an unrelated change pollute a `feat:` subject.
- **Example**: Should have been two commits: one `feat: enforce parallel subagent isolation…` and one `chore: ride along WIP from services/ and agents/`.

### M-20260511-01 — Raw string last line ended with backslash, breaking the closing delimiter
- **Date**: 2026-05-11
- **Situation**: Extended MASCOT ASCII art to full width using `__/  \` × 17 per row. The last row ended with `\`, immediately followed by the closing `"""`. Python's tokenizer treated `\"` as an escaped quote, leaving only `""` — not enough to close the triple-quoted string. The string ran on, consuming the LOGO definition as content. The error surfaced as `SyntaxError: invalid character '█'` on the LOGO line — far from the actual cause.
- **Root cause**: Python raw strings cannot end with an odd number of backslashes before the closing delimiter. `r"""...\"""` does not close at `\"`.
- **Future rule**: When generating multi-line raw strings containing `\` (ASCII art, regex patterns), verify the final line does not end with `\` before the closing `"""`. Adjust the last row so it ends with a non-backslash character (e.g. use `__/` instead of `__/  \`).
- **Example**: `r"""...__/"""` ✓ — `r"""...__/  \"""` ✗

### M-20260510-03 — Did not catch a tracked file matched by .gitignore
- **Date**: 2026-05-10
- **Situation**: Staged work and noticed `setup/__pycache__/apply.cpython-311.pyc` was tracked even though `.gitignore` covers `__pycache__/` and `*.pyc`.
- **Root cause**: `.gitignore` is advisory for *new* files. Files that are already tracked stay tracked until explicitly removed with `git rm --cached`.
- **Future rule**: At the start of any "let's commit this" flow, run `git ls-files | grep -E "__pycache__|\.pyc$|\.pyo$|\.DS_Store|Thumbs\.db"`. If anything matches, untrack it in a separate `chore:` commit before the feature commit.
- **Example**: See commit `b766600` for the correct cleanup.

### M-20260618-01 - Continued PR housekeeping when user meant feature agenda
- **Date**: 2026-06-18
- **Situation**: User said "continue with the agenda" after the Codex setup work was pushed; I inspected PR state instead of continuing the implementation hardening plan.
- **Root cause**: Treated "next steps" as delivery workflow by default after a push.
- **Future rule**: When the user says "agenda" during feature work, continue the feature/test/hardening plan unless they explicitly ask for PR administration.
- **Example**: After "continue with the agenda", audit the implementation against the requested plan and patch gaps before checking PR metadata.

### M-20260623-01 — Let Cabal logo fall back to the old header silently
- **Date**: 2026-06-23
- **Situation**: Replaced Cabal's header with a bitmap logo component, but the UI still showed the old honeycomb header.
- **Root cause**: The source launcher dependency gate did not match the new image-processing path, so the logo widget fell back to `render_banner`; the fallback looked like the old UI rather than exposing the failure.
- **Future rule**: Do not add image-processing runtime paths for TUI chrome unless the live UI truly needs them; if an asset load can fail, make the fallback visibly diagnostic instead of silently rendering the previous UI.
- **Example**: Keep `CabalLogo` terminal-native; do not route the header through image-processing-backed PNG rendering.

### M-20260623-02 — Fed heavy Rich Text directly into Textual Static
- **Date**: 2026-06-23
- **Situation**: Cabal's bitmap logo renderer produced a large `rich.text.Text` with many truecolor spans and passed it directly to `Static.update()`.
- **Root cause**: Textual special-cases bare Rich `Text` into internal `Content`, which is brittle for dense per-cell styling and can surface `RenderStyles` errors during live rendering/dev diagnostics.
- **Future rule**: For dense terminal image renderables in Textual, wrap the Rich content in a non-Text renderable such as `rich.console.Group` so Textual uses `RichVisual`.
- **Example**: `self.update(Group(render_cabal_logo(...)))` instead of `self.update(render_cabal_logo(...))`.

### M-20260623-03 — Treated terminal rasterization as acceptable brand UI
- **Date**: 2026-06-23
- **Situation**: The Cabal header rendered the PNG logo directly as ANSI truecolor half-blocks in the console UI.
- **Root cause**: Optimized for technically loading the image rather than designing for terminal cells; the result was noisy and visually poor.
- **Future rule**: For TUI branding, use terminal-native typography/marks for the live UI; keep raster images for docs, package assets, or external media.
- **Example**: `CabalLogo` should render a compact cell-designed mark plus wordmark, while `cabal-logo.png` remains packaged as the source brand asset.

### M-20260623-04 — Shrunk Cabal logo before preserving the silhouette
- **Date**: 2026-06-23
- **Situation**: User asked to move the trunk between the eyes and make the elephant a little smaller; I compressed the full-block sprite and made the logo less recognizable.
- **Root cause**: Treated the request as a dimension tweak instead of a visual design constraint, and did not validate the recognizable elephant silhouette before reporting success.
- **Future rule**: For terminal logo changes, first preserve the source silhouette landmarks (ears, eyes, trunk, legs), then adjust scale; validate fixed row widths and inspect a rendered preview before saying it is better.
- **Example**: Use a half-block sprite for Cabal's elephant mark so the trunk can start between the eyes while the overall mark stays smaller and still resembles `cabal-logo.png`.

### M-20260624-01 — Let startup table population pull the start view down
- **Date**: 2026-06-24
- **Situation**: Cabal's ProjectGateScreen opened scrolled down to recent projects after the recents table populated.
- **Root cause**: Startup focus and table cursor visibility could influence the enclosing `VerticalScroll` after layout refresh.
- **Future rule**: For Textual startup screens with below-the-fold focusable tables, focus the intended top action with `scroll_visible=False` and call `scroll_home(... immediate=True)` after refresh.
- **Example**: `ProjectGateScreen._reset_start_viewport()` focuses `#gate-init` and schedules `#gate-scroll.scroll_home()`.

### M-20260624-02 — Down-sampled Cabal logo past readable detail
- **Date**: 2026-06-24
- **Situation**: The 24x6 Cabal elephant was generated by sampling the larger sprite, which deformed the left leg and collapsed trunk/ear detail.
- **Root cause**: The generic sampler preserves proportions but not semantic landmarks at very small terminal sizes.
- **Future rule**: For tiny terminal logos, use a hand-tuned compact sprite at the target size instead of down-sampling a larger mark.
- **Example**: Cabal's default 24x6 mark uses a 24x12 source sprite so each pixel row maps directly into the six terminal rows.

### M-20260624-03 — Put Cabal wrapper labels on the wrong border
- **Date**: 2026-06-24
- **Situation**: User asked for the start screen wrapper labels to use the existing version/update information; later clarified that README belongs on the Local setup wrapper.
- **Root cause**: I treated wrapper labels as decorative copy instead of preserving the dynamic update-status information already produced by `UpdatePanel`.
- **Future rule**: In Cabal's start screen, the outer wrapper title owns dynamic version/update status; the inner setup wrapper owns `Local setup` plus the README action.
- **Example**: `#env-summary` carries `✓ Latest version ...` with no subtitle; `#env-info` carries `Local setup` plus `README`.

### M-20260624-04 — Forced the Cabal elephant into too small a mark
- **Date**: 2026-06-24
- **Situation**: User said the 24x6 elephant no longer looked like a smaller version of the original logo.
- **Root cause**: I kept optimizing inside an impossible cell budget after the silhouette landmarks no longer had room to read.
- **Future rule**: If ears, eyes, centered trunk, trunk stripes, and separated legs cannot all read at a requested tiny size, increase the default logo size rather than continuing micro-tweaks.
- **Example**: Cabal's default mark should use the 32x12 terminal render when 24x6 breaks the elephant shape.

### M-20260624-05 — Made Recent Projects a sibling instead of nested panel
- **Date**: 2026-06-24
- **Situation**: User wanted the start screen actions inside the Select project panel and then clarified that the Recent Projects panel should also sit inside it.
- **Root cause**: I treated the recents table as a separate screen section instead of part of the Select project workflow frame.
- **Future rule**: For Cabal start-screen grouping requests, keep related workflow controls and their follow-on data table inside the same outer panel unless the user asks for separate sections.
- **Example**: `#gate-select-panel` owns `#gate-actions` and nested `#gate-recents-panel`; Recent Projects is not a sibling of the Select panel.

### M-20260624-06 — Matched Cabal button fill but left variant border blue
- **Date**: 2026-06-24
- **Situation**: User asked for Clone repo to match GitHub purple; I changed the fill but left `variant="primary"`, so Textual kept the blue primary bevel border.
- **Root cause**: I verified background color only and forgot that Textual variants contribute border state via classes.
- **Future rule**: When restyling Cabal buttons away from a Textual variant, remove the variant class and verify background, text, and border edges in a mounted `run_test`.
- **Example**: `#gate-clone` should have no `-primary` class and its `styles.border.*[1]` colors should resolve to `#8B5CF6`.

### M-20260624-07 — Matched only one side of a paired Cabal button style
- **Date**: 2026-06-24
- **Situation**: User wanted the GitHub button and Clone repo button to have borders in their respective colors; I fixed Clone repo but left GitHub's default border.
- **Root cause**: Treated "make Clone repo like GitHub" as a one-button change instead of aligning both controls to the same complete style contract.
- **Future rule**: When two Cabal controls are meant to match, verify both controls' background, text, hover/focus rules, variant classes, and all border edges.
- **Example**: `#btn-github` and `#gate-clone` should both resolve every border edge to `#8B5CF6` in the normal state.

### M-20260624-08 — Accepted an invisible same-color button border as fixed
- **Date**: 2026-06-24
- **Situation**: User pointed out the GitHub/Clone button borders still looked unfixed after I set every border edge to the same purple as the fill.
- **Root cause**: I treated resolved `styles.border` as proof, but same-color border edges visually disappear in Textual's button renderer.
- **Future rule**: For Cabal button borders, use a visible bevel pair (lighter top, darker bottom) and verify rendered output/SVG colors, not only widget style properties.
- **Example**: Purple buttons use fill `#8B5CF6`, top edge `#A78BFA`, bottom edge `#5B21B6`.

### M-20260624-09 — Put Local setup paths below action buttons
- **Date**: 2026-06-24
- **Situation**: User asked for Source/Claude/OpenAI/Gemini folders inside the Local setup panel, then clarified they should sit above the buttons.
- **Root cause**: I interpreted "in the bottom" as the absolute last child, instead of below the setup rows but before the action row.
- **Future rule**: In Cabal's Local setup panel, folder paths belong inside `#env-info` immediately above `#env-tools-row`.
- **Example**: `#env-info` child order has `#env-paths` directly followed by `#env-tools-row`.

### M-20260624-10 — Verified Textual's internal clipboard instead of OS copy
- **Date**: 2026-06-24
- **Situation**: User reported text copy was still not possible after I added Cabal copy bindings.
- **Root cause**: I tested `app._clipboard` and programmatic selection, but Textual's default copy path only reliably updates its internal buffer/OSC 52; it may not populate the Windows clipboard.
- **Future rule**: For Cabal copy/paste changes, verify a real OS clipboard round trip and a mouse-drag selection path, not only `app._clipboard`.
- **Example**: `CabalApp.copy_to_clipboard()` must call `write_clipboard()`, and tests must assert the OS writer receives selected text.

### M-20260624-11 — Verified widget parentage instead of Textual geometry
- **Date**: 2026-06-24
- **Situation**: User reported the Cabal refresh loader was still not strictly right-aligned after I moved it into the version row.
- **Root cause**: I asserted the loader's parent row but did not compare mounted regions; app-level `Horizontal` padding still left a one-cell right gap.
- **Future rule**: For Cabal alignment bugs, verify mounted widget regions (`region.right`, width, padding), not only source order or parentage.
- **Example**: The refresh loader test must force `#env-refresh` visible and assert `refresh_region.right == version_row_region.right`.

### M-20260624-12 — Verified DataTable widget width instead of rendered grid width
- **Date**: 2026-06-24
- **Situation**: User reported the Recent Projects table still did not use full width when content was short.
- **Root cause**: I asserted `DataTable` widget width/margins, but Textual auto-width columns rendered only to their content sum inside the wider widget.
- **Future rule**: For Cabal `DataTable` full-width fixes, compare `sum(column.get_render_width(table))`, `table.virtual_size.width`, and `table.content_region.width`.
- **Example**: The Recent Projects path column absorbs leftover width so `render_width == table.content_region.width` even for a one-row `C:/x` table.

### M-20260624-13 — Put EnvPanel row overrides only in component CSS
- **Date**: 2026-06-24
- **Situation**: User wanted the setup detail rows between Cabal and Source aligned to the same left edge.
- **Root cause**: I first changed `EnvPanel.DEFAULT_CSS`, but the app-level `Horizontal` rule loaded later still supplied side margin and padding.
- **Future rule**: For Cabal `Horizontal` alignment fixes, check mounted regions and put app-wide row exceptions in `CabalApp.CSS` when the global `Horizontal` rule is the source.
- **Example**: `#env-row-system` and sibling setup rows need app-level `margin: 1 0; padding: 0;` so their first cells align with `#env-version-meta` and `#env-paths`.
