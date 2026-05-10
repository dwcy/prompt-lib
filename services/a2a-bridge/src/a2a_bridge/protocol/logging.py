"""Structured stdout logger for the A2A bridge (T006b).

Every helper emits exactly one line of JSON to stdout with the keys mandated by
``contracts/`` and ``data-model.md``. The bearer token value is never accepted
or logged by any helper; unexpected keyword arguments are silently dropped to
keep accidental token leaks impossible at the source.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any, Literal

_LOGGERS: dict[str, logging.Logger] = {}


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = getattr(record, "a2a", None)
        if not isinstance(payload, dict):
            payload = {
                "ts": _now(),
                "level": record.levelname,
                "event": "log",
                "message": record.getMessage(),
            }
        return json.dumps(payload, separators=(",", ":"))


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def get_logger(name: str) -> logging.Logger:
    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(f"a2a_bridge.{name}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for existing in list(logger.handlers):
        logger.removeHandler(existing)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    logger.addHandler(handler)

    _LOGGERS[name] = logger
    return logger


def _emit(level: str, event: str, **fields: Any) -> None:
    payload: dict[str, Any] = {"ts": _now(), "level": level, "event": event}
    for key, value in fields.items():
        if value is not None:
            payload[key] = value
    print(json.dumps(payload, separators=(",", ":")), file=sys.stdout, flush=True)


def log_task_received(task_id: str, peer: str, **_: Any) -> None:
    _emit("INFO", "task.received", task_id=task_id, peer=peer)


def log_outbound_delegation(task_id: str, peer: str, **_: Any) -> None:
    _emit("INFO", "delegation.outbound", task_id=task_id, peer=peer)


def log_auth_ok(peer: str, **_: Any) -> None:
    _emit("INFO", "auth.ok", peer=peer)


def log_auth_fail(peer: str, reason: str | None = None, **_: Any) -> None:
    _emit("WARNING", "auth.fail", peer=peer, reason=reason)


def log_cli_exit(
    task_id: str,
    outcome: Literal["success", "failure", "timeout"],
    exit_code: int | None = None,
    **_: Any,
) -> None:
    level = "INFO" if outcome == "success" else "ERROR"
    _emit(level, "cli.exit", task_id=task_id, outcome=outcome, exit_code=exit_code)
