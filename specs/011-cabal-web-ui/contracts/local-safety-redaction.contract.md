# Contract: Local Safety and Redaction

## Scope

This contract protects the local workstation while the browser UI is introduced. It applies to backend routes, serializers, diagnostics, static frontend rendering, and tests.

## Local Binding

- Default bind host must be `127.0.0.1`.
- The launch command may accept a different host only with an explicit flag.
- The UI must display the active backend URL.
- MVP must not implement remote authentication, public hosting, or LAN discovery.

## Read-Only Boundary

The backend must not expose browser-triggered endpoints for:

- installing tools
- updating tools
- removing tools
- editing `global/`
- editing `.mcp.json`
- changing git config
- running arbitrary shell commands
- exporting or deleting files

If a future action button is visible, it must be disabled or routed to explanatory guidance until a separate action-safety contract exists.

## Redaction Requirements

Recursive redaction must run before JSON serialization and before diagnostics reach the UI.

At minimum, redact:

- GitHub classic and fine-grained token shapes.
- OpenAI/Anthropic-style API key shapes.
- `TOKEN`, `SECRET`, `PASSWORD`, and `API_KEY` assignment-like values.
- Bearer token values.
- Query-string values for token-like parameter names.
- Long credential-looking header values.

Replacement marker: `[redacted]`.

## URL Safety

- Links may include official tool sources, dashboards, or generated repo-relative docs.
- Links must not include token-like query parameters.
- File paths should be repo-relative when possible.
- Absolute local paths may be shown only when they are useful diagnostics and have passed redaction.

## Diagnostics

Diagnostics must include:

- `section`
- `severity`
- `message`
- `timestamp`
- `retryable`

Diagnostics must not include:

- raw environment dumps
- full subprocess command output before redaction
- access tokens
- refresh tokens
- API keys
- passwords

## Contract Tests

Tests must verify:

- Mutating methods are rejected.
- The default host is localhost-only.
- Known token fixtures are redacted in nested dicts, lists, URLs, and diagnostic text.
- API responses do not contain raw fixture tokens.
- Static frontend fixtures or mock payloads do not contain real-looking secrets.
