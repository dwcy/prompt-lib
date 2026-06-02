from __future__ import annotations

from mcp_bus.paths import ensure_db
from mcp_bus.server import mcp


def main() -> None:
    ensure_db()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
