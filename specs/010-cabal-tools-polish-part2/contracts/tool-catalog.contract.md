# Contract: Tool Catalog Metadata

## Purpose

Ensure every Tools view row is backed by complete metadata before UI or installer changes are implemented.

## Required catalog invariants

- Every key in the rendered category map resolves to exactly one `ToolDefinition`.
- Every `ToolDefinition` has `key`, `label`, `category`, `description`, `source_status`, and `install_channel`.
- Every `ToolDefinition` has a `source_url` when `source_status == "verified"`.
- Automated install/update actions are disabled when `source_status != "verified"`.
- Existing tool keys remain stable unless a migration note is added to tasks.
- Descriptions are concise and non-empty.
- Source links are official homepage/docs/repository/package/release pages, not search results.

## Required new entries

### Local AI

- `lm-studio`
- `hermes-agent`
- `opencode`
- existing `ollama`
- existing `vllm`

### IDEs / Editors

- `zed`
- `rider`
- `visualstudio`
- existing `cursor`
- existing `windsurf`
- existing `antigravity`
- existing `vscode`

### Databases

- `turso-libsql`
- `duckdb`
- `sqlite`
- `redis`
- `mariadb`
- `qdrant`
- `weaviate`
- `milvus`
- existing Postgres/Supabase/Neon/sqlcmd-related entries must be retained or reclassified

### Database Clients

- `ssms`
- `dbeaver`

### Azure Local Tools

- `azure-sql-local`
- `cosmos-db-emulator`
- `azurite`

### Developer Tools

- `postman`
- `hugo`
- `uvicorn`

## Expected contract tests

- `test_all_rendered_tools_have_metadata`
- `test_all_tools_have_description_and_source_status`
- `test_source_required_tools_disable_automation`
- `test_requested_tools_are_in_expected_categories`
- `test_existing_tools_are_not_dropped`
- `test_no_secret_shaped_literals_in_tool_metadata`
