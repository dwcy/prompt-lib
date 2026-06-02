# Contract: mcp-bus Tool Surface

All tools are exposed over MCP stdio transport. Tool names, parameters, and return shapes below are authoritative — implementation and tests both conform to this document.

## Conventions

- All `*_id` values are integers, monotonically increasing per table.
- Timestamps are ISO-8601 UTC strings (e.g. `2026-06-01T14:30:00Z`).
- `content` and memory `value` are strings. Agents serialise structured data as JSON themselves.
- Errors raise an MCP tool error with a human-readable message; they do not return a partial object.

---

## Message bus

### `bus_post`
Post a message to a channel.

| Param | Type | Required | Notes |
|---|---|---|---|
| `channel` | string | yes | non-empty; created implicitly on first post |
| `content` | string | yes | the message body |
| `from_agent` | string | yes | identifier of the posting agent |
| `metadata` | object | no | arbitrary JSON object; defaults to `{}` |

**Returns:** `{ "message_id": <int> }`

### `bus_read`
Read messages from a channel, optionally only those newer than a cursor.

| Param | Type | Required | Notes |
|---|---|---|---|
| `channel` | string | yes | |
| `since_id` | int | no | return only messages with id > since_id; default null = from start |
| `limit` | int | no | max messages returned; default 20; max 100 |

**Returns:** `Message[]` ordered by id ascending:
```json
[
  {
    "message_id": 12,
    "channel": "contract",
    "from_agent": "python-architect",
    "content": "POST /api/orders ...",
    "metadata": {},
    "created_at": "2026-06-01T14:30:00Z"
  }
]
```

### `bus_channels`
List channels that have at least one message.

**Returns:** `string[]` — distinct channel names.

---

## Shared memory

### `mem_set`
Set a key in a namespace. Overwrites if the key exists.

| Param | Type | Required |
|---|---|---|
| `namespace` | string | yes |
| `key` | string | yes |
| `value` | string | yes |

**Returns:** `{ "ok": true }`

### `mem_get`
Get a key from a namespace.

| Param | Type | Required |
|---|---|---|
| `namespace` | string | yes |
| `key` | string | yes |

**Returns:** the value string, or `null` if the key does not exist.

### `mem_list`
List all keys in a namespace.

| Param | Type | Required |
|---|---|---|
| `namespace` | string | yes |

**Returns:** `string[]` — keys in the namespace (empty array if none).

### `mem_delete`
Delete a key from a namespace. No error if the key is absent.

| Param | Type | Required |
|---|---|---|
| `namespace` | string | yes |
| `key` | string | yes |

**Returns:** `{ "ok": true }`

---

## Agent registry

### `agent_register`
Register or update an agent's capabilities. Sets last-heartbeat to now.

| Param | Type | Required |
|---|---|---|
| `name` | string | yes |
| `capabilities` | string[] | yes |

**Returns:** `{ "ok": true }`

### `agent_list`
List all registered agents.

**Returns:** `Agent[]`:
```json
[
  {
    "name": "python-architect",
    "capabilities": ["fastapi", "sqlalchemy"],
    "last_heartbeat": "2026-06-01T14:30:00Z"
  }
]
```

### `agent_heartbeat`
Refresh an agent's last-heartbeat timestamp. Errors if the agent is not registered.

| Param | Type | Required |
|---|---|---|
| `name` | string | yes |

**Returns:** `{ "ok": true }`
