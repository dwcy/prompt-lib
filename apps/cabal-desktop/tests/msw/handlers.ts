// MSW request handlers for the envelope-v2 API surface: health, action prepare/execute, jobs, streams.
// The exported `handlers` array is a safe happy-path baseline; tests override per scenario via
// `server.use(...)` with the factory functions below.
import { type HttpHandler, HttpResponse, http } from "msw";
import {
  buildConfirmationTicket,
  buildHealthPayload,
  buildJobRecord,
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
];

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
