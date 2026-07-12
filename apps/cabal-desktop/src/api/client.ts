// Fetch wrapper resolving the backend base URL/auth and validating the SnapshotEnvelope v2 shape.
import type { ZodType } from "zod";
import { ApiError, reportSchemaMismatch } from "@/api/errors";
import { envelopeSchema, SCHEMA_VERSION, type SnapshotEnvelope } from "@/api/schemas";
import { apiAuthHeaders, resolveApiUrl } from "@/lib/runtimeConfig";

function extractMajor(version: string): number | null {
  const match = /v(\d+)/.exec(version);
  return match ? Number(match[1]) : null;
}

function assertCompatibleSchema(receivedVersion: string): void {
  const expectedMajor = extractMajor(SCHEMA_VERSION);
  const receivedMajor = extractMajor(receivedVersion);
  if (expectedMajor === null || receivedMajor === null || expectedMajor !== receivedMajor) {
    reportSchemaMismatch(receivedVersion);
    throw new ApiError(409, {
      code: "schema_version_mismatch",
      message: `Backend schema ${receivedVersion} is incompatible with this build (${SCHEMA_VERSION})`,
    });
  }
}

interface RequestInit {
  method: "GET" | "POST";
  body?: unknown;
  signal?: AbortSignal;
}

async function request<T>(
  path: string,
  dataSchema: ZodType<T>,
  init: RequestInit,
): Promise<SnapshotEnvelope<T>> {
  const response = await fetch(resolveApiUrl(path), {
    method: init.method,
    signal: init.signal,
    headers: {
      ...apiAuthHeaders(),
      ...(init.body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
  });

  const json: unknown = await response.json();
  const parsed = envelopeSchema(dataSchema).safeParse(json);
  if (!parsed.success) {
    throw new ApiError(response.status, {
      code: "invalid_envelope",
      message: `Response for ${path} did not match the expected v2 envelope shape`,
    });
  }

  assertCompatibleSchema(parsed.data.schema_version);

  if (!response.ok || parsed.data.status === "error") {
    const envelopeError = parsed.data.error ?? {
      code: "unknown_error",
      message: response.statusText || "Request failed",
    };
    throw new ApiError(response.status, envelopeError);
  }

  return parsed.data;
}

export function apiGet<T>(
  path: string,
  dataSchema: ZodType<T>,
  signal?: AbortSignal,
): Promise<SnapshotEnvelope<T>> {
  return request(path, dataSchema, { method: "GET", signal });
}

export function apiPost<T>(
  path: string,
  dataSchema: ZodType<T>,
  body?: unknown,
  signal?: AbortSignal,
): Promise<SnapshotEnvelope<T>> {
  return request(path, dataSchema, { method: "POST", body, signal });
}

export function requireData<T>(envelope: SnapshotEnvelope<T>, context: string): T {
  if (envelope.data === null) {
    throw new ApiError(500, {
      code: "invalid_envelope",
      message: `Missing data in ${context} response`,
    });
  }
  return envelope.data;
}
