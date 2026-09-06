// Opens one fetch-based SSE connection and yields parsed frames until the body ends or aborts.
import { apiAuthHeaders, resolveApiUrl } from "@/lib/runtimeConfig";
import { type ParsedSseFrame, SseFrameBuffer } from "@/lib/sseFrames";

export async function* openSseConnection(
  path: string,
  lastEventId: number | null,
  signal: AbortSignal,
): AsyncGenerator<ParsedSseFrame> {
  const headers: Record<string, string> = {
    ...apiAuthHeaders(),
    Accept: "text/event-stream",
  };
  if (lastEventId !== null) headers["Last-Event-ID"] = String(lastEventId);

  const response = await fetch(resolveApiUrl(path), { headers, signal });
  if (!response.ok || response.body === null) {
    throw new Error(`SSE connection to ${path} failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const frameBuffer = new SseFrameBuffer();
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) return;
      for (const frame of frameBuffer.push(decoder.decode(value, { stream: true }))) {
        yield frame;
      }
    }
  } finally {
    reader.releaseLock();
  }
}
