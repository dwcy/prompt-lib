# -*- coding: utf-8 -*-
"""Fast, cheap C# backend generation: a route/architect/gate/write/verify pipeline.

Design tree: `specs/018-dotnet-codegen/`. The pipeline attacks four cost centres — output
tokens, input tokens, round trips, and retries — with machinery rather than prompt discipline.

Language-agnostic machinery (`pipeline`, `context.bands`, `edits.applier`, `providers`, `ledger`)
is deliberately separated from the C#-specific adapters (`context.map_csharp`,
`edits.anchor_csharp`, `verify.dotnet`) so a second language target adds siblings rather than
touching the core. Only C#/.NET is implemented here.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
