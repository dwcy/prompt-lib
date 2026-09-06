// Global Vitest setup: jest-dom matchers + MSW server lifecycle for every test file.
import "@testing-library/jest-dom/vitest";

import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./msw/server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// jsdom hardcodes offsetWidth/offsetHeight (and getBoundingClientRect) to 0 for every element, so
// @tanstack/react-virtual (used by every virtualized table: Tools, Sessions, Codex ledger, ...)
// measures a zero-height viewport via `element.offsetHeight` and renders no rows at all. A real
// browser reports real layout dimensions and rows appear; these stubs restore that for tests that
// assert on row content. The ResizeObserver stub must actually invoke its callback with a
// `borderBoxSize` entry (the shape virtual-core reads) — merely defining ResizeObserver, even as a
// no-op, makes the virtualizer skip its synchronous offsetHeight fallback and wait on an
// observation that would otherwise never arrive.
const VIRTUALIZED_VIEWPORT_HEIGHT = 600;
const VIRTUALIZED_VIEWPORT_WIDTH = 800;

Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
  configurable: true,
  get: () => VIRTUALIZED_VIEWPORT_HEIGHT,
});
Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
  configurable: true,
  get: () => VIRTUALIZED_VIEWPORT_WIDTH,
});

function stubRect(): DOMRect {
  return {
    width: VIRTUALIZED_VIEWPORT_WIDTH,
    height: VIRTUALIZED_VIEWPORT_HEIGHT,
    top: 0,
    left: 0,
    bottom: VIRTUALIZED_VIEWPORT_HEIGHT,
    right: VIRTUALIZED_VIEWPORT_WIDTH,
    x: 0,
    y: 0,
    toJSON() {
      return this;
    },
  };
}
Element.prototype.getBoundingClientRect = stubRect;

class ResizeObserverStub {
  constructor(private readonly callback: ResizeObserverCallback) {}

  observe(target: Element): void {
    queueMicrotask(() => {
      const borderBoxSize = [
        { blockSize: VIRTUALIZED_VIEWPORT_HEIGHT, inlineSize: VIRTUALIZED_VIEWPORT_WIDTH },
      ] as unknown as ResizeObserverEntry["borderBoxSize"];
      const entry = { target, contentRect: stubRect(), borderBoxSize } as ResizeObserverEntry;
      this.callback([entry], this as unknown as ResizeObserver);
    });
  }

  unobserve(): void {}
  disconnect(): void {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;
