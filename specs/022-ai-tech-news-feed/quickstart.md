# Quickstart: AI Technology News Feed

1. Start the existing Cabal Desktop backend and frontend using the repository's web UI launcher.
2. Open the AI Technology News module from the desktop navigation.
3. Trigger a refresh and confirm that official AI, repository, Hacker News, security, package, and Azure status sources report independently.
4. Use category and source filters to inspect AI news, security advisories, package risks, Azure incidents, and Hacker News.
5. Disable one source and verify that its items disappear while other source results remain available.
6. Save an item, mark another read, reload the module, and verify both states persist.
7. Simulate a failed source and confirm that the UI shows its health state and continues displaying healthy source results.

## Acceptance dataset

The test fixture should include one item from each source category, one duplicate URL, one malformed item, one unavailable source, one permission-gated Azure source, and advisory metadata for a package vulnerability.
