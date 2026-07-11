// Node-side MSW server instance used by tests/setup.ts.
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
