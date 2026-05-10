"""Contract tests for the structured stdout logger (T006a).

These tests pin the wire format of every log line produced by the bridge:
one JSON object per line on stdout with required ``ts`` / ``level`` /
``event`` fields and a hard prohibition on bearer-token leakage.

Per Constitution Principle III, this file lands BEFORE its implementation
(T006b). Until then every test is expected to fail with ImportError.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

SECRET_TOKEN = "SECRET_TOKEN_12345_DO_NOT_LOG"
PEER = "claude-code"
TASK_ID = "11111111-2222-3333-4444-555555555555"


def _import_logger_module():
    from a2a_bridge.protocol import logging as logger_module

    return logger_module


def _parse_single_line(captured_out: str) -> dict:
    lines = [line for line in captured_out.splitlines() if line.strip()]
    assert len(lines) == 1, f"expected exactly one log line, got {len(lines)}: {lines!r}"
    return json.loads(lines[0])


def test_logger_module_exposes_all_required_helpers():
    module = _import_logger_module()

    assert hasattr(module, "get_logger")
    assert hasattr(module, "log_task_received")
    assert hasattr(module, "log_outbound_delegation")
    assert hasattr(module, "log_auth_ok")
    assert hasattr(module, "log_auth_fail")
    assert hasattr(module, "log_cli_exit")


def test_log_auth_ok_emits_single_json_line_with_required_fields(capsys):
    module = _import_logger_module()

    module.log_auth_ok(peer=PEER)

    captured = capsys.readouterr()
    payload = _parse_single_line(captured.out)
    assert payload["event"] == "auth.ok"
    assert payload["peer"] == PEER
    assert "level" in payload
    datetime.fromisoformat(payload["ts"])


def test_log_auth_fail_emits_single_json_line_with_required_fields(capsys):
    module = _import_logger_module()

    module.log_auth_fail(peer=PEER)

    captured = capsys.readouterr()
    payload = _parse_single_line(captured.out)
    assert payload["event"] == "auth.fail"
    assert payload["peer"] == PEER
    assert "level" in payload
    datetime.fromisoformat(payload["ts"])


def test_log_auth_ok_never_includes_bearer_token_in_output(capsys):
    module = _import_logger_module()

    module.log_auth_ok(peer=PEER, token=SECRET_TOKEN)

    captured = capsys.readouterr()
    assert SECRET_TOKEN not in captured.out
    assert SECRET_TOKEN not in captured.err


def test_log_auth_fail_never_includes_bearer_token_in_output(capsys):
    module = _import_logger_module()

    module.log_auth_fail(peer=PEER, token=SECRET_TOKEN)

    captured = capsys.readouterr()
    assert SECRET_TOKEN not in captured.out
    assert SECRET_TOKEN not in captured.err


def test_log_task_received_includes_task_id_and_peer(capsys):
    module = _import_logger_module()

    module.log_task_received(task_id=TASK_ID, peer=PEER)

    captured = capsys.readouterr()
    payload = _parse_single_line(captured.out)
    assert payload["task_id"] == TASK_ID
    assert payload["peer"] == PEER
    assert "event" in payload
    assert "level" in payload
    datetime.fromisoformat(payload["ts"])


def test_log_outbound_delegation_includes_task_id_and_peer(capsys):
    module = _import_logger_module()

    module.log_outbound_delegation(task_id=TASK_ID, peer=PEER)

    captured = capsys.readouterr()
    payload = _parse_single_line(captured.out)
    assert payload["task_id"] == TASK_ID
    assert payload["peer"] == PEER
    assert "event" in payload
    assert "level" in payload
    datetime.fromisoformat(payload["ts"])


@pytest.mark.parametrize("outcome", ["success", "failure", "timeout"])
def test_log_cli_exit_includes_task_id_outcome_and_exit_code(capsys, outcome):
    module = _import_logger_module()

    module.log_cli_exit(task_id=TASK_ID, outcome=outcome, exit_code=0)

    captured = capsys.readouterr()
    payload = _parse_single_line(captured.out)
    assert payload["task_id"] == TASK_ID
    assert payload["outcome"] == outcome
    assert payload["exit_code"] == 0
    assert "event" in payload
    assert "level" in payload
    datetime.fromisoformat(payload["ts"])


def test_all_helpers_emit_to_stdout_not_stderr(capsys):
    module = _import_logger_module()

    module.log_task_received(task_id=TASK_ID, peer=PEER)
    module.log_outbound_delegation(task_id=TASK_ID, peer=PEER)
    module.log_auth_ok(peer=PEER)
    module.log_auth_fail(peer=PEER)
    module.log_cli_exit(task_id=TASK_ID, outcome="success", exit_code=0)

    captured = capsys.readouterr()
    assert captured.out.strip() != ""
    assert captured.err.strip() == ""


def test_every_emitted_line_is_valid_json_with_required_keys(capsys):
    module = _import_logger_module()

    module.log_task_received(task_id=TASK_ID, peer=PEER)
    module.log_outbound_delegation(task_id=TASK_ID, peer=PEER)
    module.log_auth_ok(peer=PEER)
    module.log_auth_fail(peer=PEER)
    module.log_cli_exit(task_id=TASK_ID, outcome="success", exit_code=0)

    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 5

    for line in lines:
        payload = json.loads(line)
        assert "ts" in payload
        assert "level" in payload
        assert "event" in payload
        datetime.fromisoformat(payload["ts"])
