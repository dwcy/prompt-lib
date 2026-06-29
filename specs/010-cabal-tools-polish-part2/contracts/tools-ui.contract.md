# Contract: Tools View UI Behavior

## Purpose

Define how the Tools view exposes descriptions, source links, copy behavior, version selectors, and long-running actions.

## Rendering contract

For every rendered tool row:

- Show label.
- Show short description.
- Show current status.
- Show read-more/source action when source metadata exists.
- Show install/update/manual/source-required action according to status.
- Show version selector only for tools with version providers.
- Keep unsupported-platform rows visible but disabled with explanation.

## Copy contract

- Ctrl+C and Ctrl+Shift+C copy selected Tools view text.
- Selected text may come from descriptions, source URLs, status text, version text, or error output.
- If no Tools text is selected, existing app copy behavior remains unchanged.
- Copied error/status text must be redacted.

## Worker contract

- Initial render must not wait for network version metadata.
- Version checks run in a background worker.
- Container status checks run in a background worker.
- Install/update actions report progress without freezing navigation.

## Expected contract tests

- `test_tools_screen_renders_descriptions`
- `test_tools_screen_renders_read_more_actions`
- `test_read_more_uses_source_url`
- `test_tools_screen_copies_selected_description_text`
- `test_tools_screen_copies_install_error_text`
- `test_version_selector_renders_for_runtime_tools`
- `test_source_required_row_disables_install_button`
- `test_long_running_version_check_does_not_block_initial_render`
