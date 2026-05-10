# A2A Bridge v1 — Error Codes

Error responses follow JSON-RPC 2.0:

```json
{
  "jsonrpc": "2.0",
  "id": "<echoed or null if request was unparseable>",
  "error": {
    "code": <int>,
    "message": "<short human-readable summary>",
    "data": { "<optional structured data>": "<value>" }
  }
}
```

| Code | JSON-RPC name | When v1 emits it | `data` payload |
|---|---|---|---|
| `-32700` | Parse error | Request body is not valid JSON | none |
| `-32600` | Invalid Request | Body is JSON but missing required JSON-RPC fields (`jsonrpc`, `method`) | `{ missing: ["<field>", ...] }` |
| `-32601` | Method not found | `method` is anything other than `tasks/sendSubscribe`, `tasks/get`, `tasks/cancel` | `{ method: "<received method>" }` |
| `-32602` | Invalid params | Method is recognised but `params` fails per-method validation (see `jsonrpc-methods.md`) | per-method-defined `data` (e.g. `{ reason: "task_not_found" }`) |
| `-32603` | Internal error | Adapter encountered an unexpected exception not covered by the above | `{ ref: "<UUID for log correlation>" }` (the actual exception is NEVER returned in `data`) |

## HTTP-level errors (NOT JSON-RPC errors)

These are returned at the HTTP layer before any JSON-RPC processing happens.

| HTTP status | When v1 emits it | Body |
|---|---|---|
| `401 Unauthorized` | Missing `Authorization` header, or token mismatch | `{ "error": "unauthorized" }` (plain JSON, NOT a JSON-RPC envelope, because we have no request id to echo) |
| `405 Method Not Allowed` | Non-POST request to `/jsonrpc` | (FastAPI default) |
| `415 Unsupported Media Type` | `Content-Type` is not `application/json` on POST | `{ "error": "expected application/json" }` |

## Conformance notes

- We do NOT use JSON-RPC error code ranges other than the standard codes above. The A2A v1.0.0 spec leaves application-specific error codes optional; we explicitly defer that surface to v2.
- The `data` field NEVER contains stack traces, internal hostnames, or token values. Internal errors carry a UUID `ref` that callers can quote in support requests; the actual exception detail goes only to the adapter's stdout log.
