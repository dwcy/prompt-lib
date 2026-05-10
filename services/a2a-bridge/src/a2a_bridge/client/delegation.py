"""DelegationClient — outbound A2A peer streaming (T027).

Opens a JSON-RPC ``tasks/sendSubscribe`` over HTTPS to a peer A2A adapter,
parses the server-sent event stream, and yields each event as a parsed dict.
The exception hierarchy lets callers (the Typer CLI in T028, future Claude
adapter in Phase 4) distinguish connect failures, auth failures, and protocol
violations so they can map to deterministic exit codes.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx

_JSONRPC_PATH = "/jsonrpc"


class DelegationError(Exception):
    """Base class for delegation client failures."""


class DelegationConnectError(DelegationError):
    """Raised when the peer cannot be reached (connect refused, DNS, network)."""


class DelegationAuthError(DelegationError):
    """Raised when the peer rejects the bearer token (HTTP 401)."""


class DelegationProtocolError(DelegationError):
    """Raised when the peer responds with a non-2xx status, malformed SSE, or
    an unexpected event shape."""


class DelegationClient:
    def __init__(
        self,
        *,
        peer_url: str,
        peer_bearer_token: str,
        timeout_seconds: float = 300.0,
    ) -> None:
        self._peer_url = peer_url.rstrip("/")
        self._peer_bearer_token = peer_bearer_token
        self._timeout = httpx.Timeout(connect=5.0, read=timeout_seconds, write=5.0, pool=5.0)

    async def delegate(self, prompt: str) -> AsyncIterator[dict[str, Any]]:
        request_body: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tasks/sendSubscribe",
            "params": {"task": {"messages": [{"role": "user", "content": prompt}]}},
        }
        headers = {
            "Authorization": f"Bearer {self._peer_bearer_token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        url = f"{self._peer_url}{_JSONRPC_PATH}"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream(
                    "POST", url, json=request_body, headers=headers
                ) as response:
                    if response.status_code == 401:
                        raise DelegationAuthError("peer rejected bearer token")
                    if response.status_code != 200:
                        raise DelegationProtocolError(
                            f"unexpected status {response.status_code}"
                        )

                    async for event in self._parse_sse(response):
                        yield event
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise DelegationConnectError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise DelegationProtocolError(str(exc)) from exc

    async def _parse_sse(self, response: httpx.Response) -> AsyncIterator[dict[str, Any]]:
        pending_event: str | None = None
        pending_data: list[str] = []

        async for line in response.aiter_lines():
            if line == "":
                if pending_event is not None and pending_data:
                    raw = "\n".join(pending_data)
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        raise DelegationProtocolError(f"malformed SSE data: {raw!r}") from exc
                    yield {"event": pending_event, "data": payload}
                pending_event = None
                pending_data = []
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                pending_event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                pending_data.append(line[len("data:") :].lstrip())
