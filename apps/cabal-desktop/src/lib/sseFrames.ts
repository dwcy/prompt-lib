// Pure SSE frame parsing: buffers streamed text and yields complete event/data/id frames.
export interface ParsedSseFrame {
  event: string;
  id: number | null;
  data: unknown;
}

const FRAME_SEPARATOR = "\n\n";

export class SseFrameBuffer {
  private buffer = "";

  push(chunk: string): ParsedSseFrame[] {
    this.buffer += chunk;
    const frames: ParsedSseFrame[] = [];
    let separatorIndex = this.buffer.indexOf(FRAME_SEPARATOR);
    while (separatorIndex !== -1) {
      const rawFrame = this.buffer.slice(0, separatorIndex);
      this.buffer = this.buffer.slice(separatorIndex + FRAME_SEPARATOR.length);
      const parsed = parseSseFrame(rawFrame);
      if (parsed !== null) frames.push(parsed);
      separatorIndex = this.buffer.indexOf(FRAME_SEPARATOR);
    }
    return frames;
  }
}

function parseSseFrame(rawFrame: string): ParsedSseFrame | null {
  let event = "message";
  let id: number | null = null;
  const dataLines: string[] = [];

  for (const line of rawFrame.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    } else if (line.startsWith("id:")) {
      const parsedId = Number.parseInt(line.slice("id:".length).trim(), 10);
      id = Number.isNaN(parsedId) ? null : parsedId;
    }
  }

  if (dataLines.length === 0) return null;
  try {
    return { event, id, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null;
  }
}
