// Zod schemas for markdown the backend already parsed into typed blocks (cabal.skill_structure):
// a preamble plus flat sections carrying their heading level. Shared by every endpoint that
// serves a markdown document.
import { z } from "zod";

export const markdownBlockSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("paragraph"), text: z.string() }),
  z.object({ type: z.literal("code"), language: z.string().nullable(), text: z.string() }),
  z.object({
    type: z.literal("list"),
    ordered: z.boolean(),
    items: z.array(z.object({ text: z.string(), depth: z.number() })),
  }),
  z.object({
    type: z.literal("table"),
    header: z.array(z.string()),
    rows: z.array(z.array(z.string())),
  }),
  z.object({ type: z.literal("quote"), text: z.string() }),
  z.object({ type: z.literal("divider") }),
]);

export const markdownSectionSchema = z.object({
  level: z.number(),
  title: z.string(),
  anchor: z.string(),
  blocks: z.array(markdownBlockSchema),
});

export const markdownDocumentSchema = z.object({
  preamble: z.array(markdownBlockSchema),
  sections: z.array(markdownSectionSchema),
});

export type MarkdownBlock = z.infer<typeof markdownBlockSchema>;
export type MarkdownSection = z.infer<typeof markdownSectionSchema>;
export type MarkdownDocument = z.infer<typeof markdownDocumentSchema>;
