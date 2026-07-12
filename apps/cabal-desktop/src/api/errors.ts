// Typed ApiError for envelope error codes + the schema-version mismatch registry the shell subscribes to.
import type { EnvelopeError } from "@/api/schemas";

export class ApiError extends Error {
  readonly httpStatus: number;
  readonly code: string;
  readonly extra: Record<string, unknown>;

  constructor(httpStatus: number, envelopeError: EnvelopeError) {
    super(envelopeError.message);
    this.name = "ApiError";
    this.httpStatus = httpStatus;
    this.code = envelopeError.code;
    this.extra = extraFields(envelopeError);
  }
}

function extraFields(envelopeError: EnvelopeError): Record<string, unknown> {
  const extra: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(envelopeError)) {
    if (key !== "code" && key !== "message") extra[key] = value;
  }
  return extra;
}

type SchemaMismatchListener = (receivedVersion: string) => void;

const schemaMismatchListeners = new Set<SchemaMismatchListener>();

export function onSchemaMismatch(listener: SchemaMismatchListener): () => void {
  schemaMismatchListeners.add(listener);
  return () => schemaMismatchListeners.delete(listener);
}

export function reportSchemaMismatch(receivedVersion: string): void {
  for (const listener of schemaMismatchListeners) listener(receivedVersion);
}
