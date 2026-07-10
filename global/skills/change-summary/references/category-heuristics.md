# Drawing categories from a diff

There is no fixed taxonomy. Look at the actual file list and group by whatever clustering is real — usually a mix of directory and shared purpose. Examples of categories that emerge naturally, not exhaustive: hook/automation logic, settings/config, dead-code removal, project rules/docs, individual skills, individual agents, model/tooling assignment, generated output.

## Rules of thumb

- **A category needs at least two files pulling in the same direction**, or one file important enough to deserve its own header. Don't invent a category for a single unrelated straggler — fold it into a nearby category or an "Other" group.
- **Order categories by what a reviewer needs to know first.** Behavior-affecting logic changes before docs/rules changes before pure config/tooling changes. Put deletions of dead code near the top if they're a meaningful part of the story — "this used to exist and doesn't anymore" is often the single most important fact in a diff.
- **If everything in the diff is one kind of thing** (a pure docs PR, a single bug fix touching one file), skip grouping entirely — one table, no category headers, is the right call. Grouping five files that are all "the fix" into artificial sub-buckets is padding, not clarity.
- **Batches of files with identical reasoning are a category of one row, not one category per file.** If eleven files lost the same hardcoded pin for the same reason, that's one row in one category — not eleven rows or eleven categories.
