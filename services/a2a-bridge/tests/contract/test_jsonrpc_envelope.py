"""Contract tests for the JSON-RPC 2.0 envelope and error helpers (T011).

These tests pin the wire format of every JSON-RPC envelope the bridge ever
emits, per ``contracts/error-codes.md``. They target the parser and builder
helpers directly (no HTTP layer); the dispatcher itself lands in T020.

Per Constitution Principle III, this file lands BEFORE its implementation
(T013). Until then every test is expected to fail with ImportError on
``a2a_bridge.protocol.jsonrpc``.
"""

from __future__ import annotations

import uuid

import pytest


def _import_jsonrpc():
    from a2a_bridge.protocol import jsonrpc

    return jsonrpc


# ---------------------------------------------------------------------------
# ErrorCode constants
# ---------------------------------------------------------------------------


class TestErrorCodeConstants:
    def test_parse_error_code_is_minus_32700(self):
        jsonrpc = _import_jsonrpc()

        assert int(jsonrpc.ErrorCode.PARSE_ERROR) == -32700

    def test_invalid_request_code_is_minus_32600(self):
        jsonrpc = _import_jsonrpc()

        assert int(jsonrpc.ErrorCode.INVALID_REQUEST) == -32600

    def test_method_not_found_code_is_minus_32601(self):
        jsonrpc = _import_jsonrpc()

        assert int(jsonrpc.ErrorCode.METHOD_NOT_FOUND) == -32601

    def test_invalid_params_code_is_minus_32602(self):
        jsonrpc = _import_jsonrpc()

        assert int(jsonrpc.ErrorCode.INVALID_PARAMS) == -32602

    def test_internal_error_code_is_minus_32603(self):
        jsonrpc = _import_jsonrpc()

        assert int(jsonrpc.ErrorCode.INTERNAL_ERROR) == -32603


# ---------------------------------------------------------------------------
# parse_request — -32700 Parse error
# ---------------------------------------------------------------------------


class TestParseRequestParseError:
    def test_non_json_bytes_raise_parse_error(self):
        jsonrpc = _import_jsonrpc()

        with pytest.raises(jsonrpc.JsonRpcError) as exc_info:
            jsonrpc.parse_request(b"not json")

        assert exc_info.value.code == -32700

    def test_parse_error_message_is_parse_error(self):
        jsonrpc = _import_jsonrpc()

        with pytest.raises(jsonrpc.JsonRpcError) as exc_info:
            jsonrpc.parse_request(b"not json")

        assert exc_info.value.message == "Parse error"

    def test_parse_error_envelope_id_is_null(self):
        jsonrpc = _import_jsonrpc()

        try:
            jsonrpc.parse_request(b"{ broken")
        except jsonrpc.JsonRpcError as exc:
            envelope = exc.to_envelope(None)
        else:
            pytest.fail("expected JsonRpcError for unparseable JSON")

        assert envelope["id"] is None

    def test_parse_error_envelope_has_no_data_payload(self):
        jsonrpc = _import_jsonrpc()

        try:
            jsonrpc.parse_request(b"@@@")
        except jsonrpc.JsonRpcError as exc:
            envelope = exc.to_envelope(None)
        else:
            pytest.fail("expected JsonRpcError for unparseable JSON")

        assert "data" not in envelope["error"] or envelope["error"]["data"] in (None, {})


# ---------------------------------------------------------------------------
# parse_request — -32600 Invalid request
# ---------------------------------------------------------------------------


class TestParseRequestInvalidRequest:
    def test_missing_jsonrpc_field_raises_invalid_request(self):
        jsonrpc = _import_jsonrpc()

        with pytest.raises(jsonrpc.JsonRpcError) as exc_info:
            jsonrpc.parse_request(b'{"id": 1, "method": "tasks/get"}')

        assert exc_info.value.code == -32600
        assert "jsonrpc" in exc_info.value.data["missing"]

    def test_missing_method_field_raises_invalid_request(self):
        jsonrpc = _import_jsonrpc()

        with pytest.raises(jsonrpc.JsonRpcError) as exc_info:
            jsonrpc.parse_request(b'{"jsonrpc": "2.0", "id": 1}')

        assert exc_info.value.code == -32600
        assert "method" in exc_info.value.data["missing"]

    def test_missing_both_jsonrpc_and_method_lists_both(self):
        jsonrpc = _import_jsonrpc()

        with pytest.raises(jsonrpc.JsonRpcError) as exc_info:
            jsonrpc.parse_request(b'{"id": 1}')

        missing = exc_info.value.data["missing"]
        assert "jsonrpc" in missing
        assert "method" in missing

    def test_wrong_jsonrpc_version_raises_invalid_request(self):
        jsonrpc = _import_jsonrpc()

        with pytest.raises(jsonrpc.JsonRpcError) as exc_info:
            jsonrpc.parse_request(b'{"jsonrpc": "1.0", "id": 1, "method": "tasks/get"}')

        assert exc_info.value.code == -32600

    def test_invalid_request_envelope_echoes_id_when_present(self):
        jsonrpc = _import_jsonrpc()

        try:
            jsonrpc.parse_request(b'{"id": "req-7", "method": "tasks/get"}')
        except jsonrpc.JsonRpcError as exc:
            envelope = exc.to_envelope("req-7")
        else:
            pytest.fail("expected JsonRpcError for missing jsonrpc field")

        assert envelope["id"] == "req-7"


# ---------------------------------------------------------------------------
# Method not found — -32601
# ---------------------------------------------------------------------------


class TestMethodNotFoundEnvelope:
    def test_method_not_found_envelope_carries_method_in_data(self):
        jsonrpc = _import_jsonrpc()

        err = jsonrpc.JsonRpcError(
            code=jsonrpc.ErrorCode.METHOD_NOT_FOUND,
            message="Method not found",
            data={"method": "tasks/unknown"},
        )
        envelope = err.to_envelope("req-id")

        assert envelope["error"]["code"] == -32601
        assert envelope["error"]["data"]["method"] == "tasks/unknown"

    def test_method_not_found_envelope_id_is_echoed(self):
        jsonrpc = _import_jsonrpc()

        err = jsonrpc.JsonRpcError(
            code=jsonrpc.ErrorCode.METHOD_NOT_FOUND,
            message="Method not found",
            data={"method": "tasks/unknown"},
        )
        envelope = err.to_envelope("req-id")

        assert envelope["id"] == "req-id"


# ---------------------------------------------------------------------------
# Invalid params — -32602
# ---------------------------------------------------------------------------


class TestInvalidParamsEnvelope:
    def test_invalid_params_envelope_carries_structured_reason(self):
        jsonrpc = _import_jsonrpc()

        envelope = jsonrpc.build_error_response(
            "req-9",
            jsonrpc.ErrorCode.INVALID_PARAMS,
            "Invalid params",
            {"reason": "task_not_found"},
        )

        assert envelope["error"]["code"] == -32602
        assert envelope["error"]["data"] == {"reason": "task_not_found"}

    def test_invalid_params_envelope_echoes_id(self):
        jsonrpc = _import_jsonrpc()

        envelope = jsonrpc.build_error_response(
            42,
            jsonrpc.ErrorCode.INVALID_PARAMS,
            "Invalid params",
            {"reason": "task_already_terminal", "state": "completed"},
        )

        assert envelope["id"] == 42


# ---------------------------------------------------------------------------
# Internal error — -32603
# ---------------------------------------------------------------------------


class TestInternalErrorEnvelope:
    def test_internal_error_envelope_includes_uuid_ref(self):
        jsonrpc = _import_jsonrpc()

        envelope = jsonrpc.build_error_response(
            "req-id",
            jsonrpc.ErrorCode.INTERNAL_ERROR,
            "Internal error",
            None,
        )

        ref = envelope["error"]["data"]["ref"]
        assert uuid.UUID(ref)

    def test_internal_error_ref_is_unique_per_call(self):
        jsonrpc = _import_jsonrpc()

        first = jsonrpc.build_error_response(
            "req-id",
            jsonrpc.ErrorCode.INTERNAL_ERROR,
            "Internal error",
            None,
        )
        second = jsonrpc.build_error_response(
            "req-id",
            jsonrpc.ErrorCode.INTERNAL_ERROR,
            "Internal error",
            None,
        )

        assert first["error"]["data"]["ref"] != second["error"]["data"]["ref"]

    def test_internal_error_does_not_leak_exception_text(self):
        jsonrpc = _import_jsonrpc()

        envelope = jsonrpc.build_error_response(
            "req-id",
            jsonrpc.ErrorCode.INTERNAL_ERROR,
            "Internal error",
            {"exc": "ZeroDivisionError: division by zero"},
        )

        data = envelope["error"]["data"]
        assert "exc" not in data
        assert "ZeroDivisionError" not in repr(data)


# ---------------------------------------------------------------------------
# Envelope structural invariants — every error envelope
# ---------------------------------------------------------------------------


class TestErrorEnvelopeShape:
    def test_error_envelope_has_jsonrpc_2_0(self):
        jsonrpc = _import_jsonrpc()

        envelope = jsonrpc.build_error_response(
            1, jsonrpc.ErrorCode.INVALID_PARAMS, "Invalid params", {"reason": "x"}
        )

        assert envelope["jsonrpc"] == "2.0"

    def test_error_envelope_has_id_key(self):
        jsonrpc = _import_jsonrpc()

        envelope = jsonrpc.build_error_response(
            "abc", jsonrpc.ErrorCode.INVALID_PARAMS, "Invalid params", {"reason": "x"}
        )

        assert "id" in envelope
        assert envelope["id"] == "abc"

    def test_error_envelope_id_is_null_when_request_id_unknown(self):
        jsonrpc = _import_jsonrpc()

        envelope = jsonrpc.build_error_response(
            None, jsonrpc.ErrorCode.PARSE_ERROR, "Parse error", None
        )

        assert envelope["id"] is None

    def test_error_envelope_error_object_has_code_and_message(self):
        jsonrpc = _import_jsonrpc()

        envelope = jsonrpc.build_error_response(
            1, jsonrpc.ErrorCode.METHOD_NOT_FOUND, "Method not found", {"method": "foo"}
        )

        assert isinstance(envelope["error"]["code"], int)
        assert isinstance(envelope["error"]["message"], str)

    def test_error_envelope_has_no_result_key(self):
        jsonrpc = _import_jsonrpc()

        envelope = jsonrpc.build_error_response(
            1, jsonrpc.ErrorCode.METHOD_NOT_FOUND, "Method not found", {"method": "foo"}
        )

        assert "result" not in envelope


# ---------------------------------------------------------------------------
# Success envelope shape
# ---------------------------------------------------------------------------


class TestSuccessEnvelopeShape:
    def test_success_envelope_has_jsonrpc_2_0(self):
        jsonrpc = _import_jsonrpc()

        envelope = jsonrpc.build_success_response("req-1", {"task_id": "t-1"})

        assert envelope["jsonrpc"] == "2.0"

    def test_success_envelope_echoes_id(self):
        jsonrpc = _import_jsonrpc()

        envelope = jsonrpc.build_success_response("req-1", {"task_id": "t-1"})

        assert envelope["id"] == "req-1"

    def test_success_envelope_carries_result(self):
        jsonrpc = _import_jsonrpc()

        envelope = jsonrpc.build_success_response("req-1", {"task_id": "t-1"})

        assert envelope["result"] == {"task_id": "t-1"}

    def test_success_envelope_has_no_error_key(self):
        jsonrpc = _import_jsonrpc()

        envelope = jsonrpc.build_success_response("req-1", {"task_id": "t-1"})

        assert "error" not in envelope

    def test_success_envelope_supports_integer_id(self):
        jsonrpc = _import_jsonrpc()

        envelope = jsonrpc.build_success_response(42, {"ok": True})

        assert envelope["id"] == 42
