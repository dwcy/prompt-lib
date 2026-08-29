# Source Adapter Contract

Each adapter produces a normalized `FeedSource` result and zero or more `FeedItem` values.

- Adapters must never raise a provider error into the aggregate refresh path.
- Adapters must return a health state, last successful refresh time when known, and a safe user-facing hint.
- Adapters must preserve source attribution and canonical links.
- Adapters must reject executable or trusted interpretation of feed text.
- Security adapters may populate advisory identifiers, packages, ecosystems, severities, and exploit status only when supplied by the source.
- Azure adapters must distinguish public status data from permission-required service health.
