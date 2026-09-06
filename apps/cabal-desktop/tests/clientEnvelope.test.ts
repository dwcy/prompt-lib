// Unit test: a non-JSON response body (proxy error page, pre-handshake asset protocol)
// must surface as a typed envelope error, not a raw SyntaxError.
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { z } from "zod";
import { apiGet } from "@/api/client";
import { ApiError } from "@/api/errors";
import { server } from "./msw/server";

describe("apiGet envelope parsing", () => {
  it("reports a non-JSON body as an invalid_envelope ApiError", async () => {
    server.use(
      http.get("/api/health", () =>
        HttpResponse.text("Cabal backend handshake unavailable", { status: 502 }),
      ),
    );

    const failure = await apiGet("/api/health", z.unknown()).catch((error) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).code).toBe("invalid_envelope");
  });
});
