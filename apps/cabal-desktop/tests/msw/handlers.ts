// MSW request handlers for the envelope-v2 API surface: health, action prepare/execute, jobs, streams.
// The exported `handlers` array is a safe happy-path baseline; tests override per scenario via
// `server.use(...)` with the factory functions below.
import { type HttpHandler, HttpResponse, http } from "msw";
import type { ToolCatalogPayload, ToolDetail, ToolStatusEntry } from "@/api/tools";
import {
  buildConfirmationTicket,
  buildHealthPayload,
  buildJobRecord,
  buildOverviewPayload,
  buildProjectContext,
  buildSseStream,
  type SseFrameInput,
  wrapEnvelope,
} from "./fixtures";

export const handlers: HttpHandler[] = [
  http.get("/api/health", () => HttpResponse.json(wrapEnvelope(buildHealthPayload()))),

  http.post("/api/actions/:actionId/prepare", ({ params }) =>
    HttpResponse.json(
      wrapEnvelope(buildConfirmationTicket({ action_id: String(params.actionId) })),
    ),
  ),

  http.post("/api/actions/:actionId/execute", () =>
    HttpResponse.json(wrapEnvelope({ job_id: null })),
  ),

  http.get("/api/jobs/:jobId", ({ params }) =>
    HttpResponse.json(wrapEnvelope(buildJobRecord("queued", { job_id: String(params.jobId) }))),
  ),

  // T032/T036 baseline: a project already selected, so <App/> renders the normal shell (not the
  // gate) unless a test explicitly overrides this with selected_at: null.
  http.get("/api/project", () => HttpResponse.json(wrapEnvelope(buildProjectContext()))),

  http.get("/api/overview", () => HttpResponse.json(wrapEnvelope(buildOverviewPayload()))),

  http.get("/api/dashboard", () => HttpResponse.json(wrapEnvelope({}))),

  http.get("/api/diagnostics", () => HttpResponse.json(wrapEnvelope({ events: [] }))),
];

export function toolsCatalogHandler(payload: ToolCatalogPayload): HttpHandler {
  return http.get("/api/tools", () => HttpResponse.json(wrapEnvelope(payload)));
}

export function toolsStatusHandler(items: ToolStatusEntry[]): HttpHandler {
  return http.get("/api/tools/status", () => HttpResponse.json(wrapEnvelope({ items })));
}

export function toolDetailHandler(key: string, detail: ToolDetail): HttpHandler {
  return http.get(`/api/tools/${key}`, () => HttpResponse.json(wrapEnvelope(detail)));
}

export function jobStreamHandler(
  jobId: string,
  frames: SseFrameInput[],
  options: { keepOpen?: boolean } = {},
): HttpHandler {
  return http.get(`/api/jobs/${jobId}/stream`, () => {
    const stream = buildSseStream(frames, options);
    return new HttpResponse(stream, {
      headers: { "Content-Type": "text/event-stream" },
    });
  });
}

export function diagnosticsStreamHandler(
  frames: SseFrameInput[],
  options: { keepOpen?: boolean } = {},
): HttpHandler {
  return http.get("/api/diagnostics/stream", () => {
    const stream = buildSseStream(frames, options);
    return new HttpResponse(stream, {
      headers: { "Content-Type": "text/event-stream" },
    });
  });
}
