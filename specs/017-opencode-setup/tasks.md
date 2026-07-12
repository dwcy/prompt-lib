# Tasks: OpenCode Setup

## Phase 1: Setup

- [X] T001 Create feature branch `feat/opencode-setup` after fast-forwarding `main` - Owner: main
- [X] T002 Add Spec Kit artifacts under `specs/017-opencode-setup/` - Owner: main

## Phase 2: Core Implementation

- [X] T003 Add curated OpenCode assets in `global/opencode/` - Owner: @python-architect
- [X] T004 Add OpenCode path, status, conversion, preview, and apply helpers in `setup/src/cabal/opencode_setup/` - Owner: @python-architect
- [X] T005 Add OpenCode Setup Textual screen in `setup/src/cabal/views/opencode_setup.py` - Owner: @python-architect
- [X] T006 Wire OpenCode Setup into Cabal Home and app imports - Owner: @python-architect
- [X] T007 Preserve unrelated existing JSON keys when applying OpenCode config - Owner: @python-architect

## Phase 3: Tests

- [X] T008 Add helper tests in `setup/tests/test_opencode_setup.py` - Owner: @python-tester
- [X] T009 Add Textual smoke test in `setup/tests/test_opencode_screen.py` - Owner: @python-tester
- [X] T010 Run focused OpenCode test command - Owner: main

## Phase 4: Validation

- [X] T011 Verify local `main` was fast-forwarded and local `.claude/settings.local.json` stayed modified - Owner: main
- [X] T012 Keep implementation sequential; no parallel worktree isolation required - Owner: main
- [X] T013 Split OpenCode CLI/Desktop naming and add desktop app installer action - Owner: main
