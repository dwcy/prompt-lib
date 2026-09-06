# Feed API Contract

The module exposes an internal read-oriented API following the existing web UI backend conventions.

## Endpoints

- `GET /api/news/sources` — returns source definitions and health metadata.
- `GET /api/news/items?source=&category=&read=&saved=&cursor=` — returns normalized items and applied filters.
- `POST /api/news/refresh` — starts or requests a refresh and returns refresh status.
- `PUT /api/news/sources/{source_id}` — updates the local enabled state only.
- `PUT /api/news/items/{item_id}/state` — updates local read/saved state.

## Contract rules

- A source failure is represented inside the source result and does not fail the entire collection response.
- External feed content is returned as data; no HTML/script-bearing field is trusted by the client.
- Item URLs remain canonical HTTP(S) URLs and are opened externally by the desktop UI.
- Filter responses include enough metadata to render the active filter and result count.
