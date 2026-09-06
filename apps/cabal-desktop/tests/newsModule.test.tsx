import { describe, expect, it } from "vitest";
import { newsPayloadSchema } from "@/api/schemas";
import { NEWS_CATEGORIES } from "@/modules/news/NewsModule";

describe("AI technology news contract", () => {
  it("exposes the planned filter categories", () => {
    expect(NEWS_CATEGORIES).toContain("security");
    expect(NEWS_CATEGORIES).toContain("cloud");
    expect(NEWS_CATEGORIES).toContain("community");
  });

  it("accepts normalized item and source payloads", () => {
    const result = newsPayloadSchema.safeParse({ items: [], sources: [] });
    expect(result.success).toBe(true);
  });
});
