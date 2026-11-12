import { describe, expect, it } from "vitest";
import { parseInline, parseMarkdown } from "./markdown";

describe("parseInline", () => {
  it("splits bold, italic and code from plain text", () => {
    expect(parseInline("Ride **3 × 10 min** at *tempo*, `Z3`.")).toEqual([
      { type: "text", text: "Ride " },
      { type: "strong", text: "3 × 10 min" },
      { type: "text", text: " at " },
      { type: "em", text: "tempo" },
      { type: "text", text: ", " },
      { type: "code", text: "Z3" },
      { type: "text", text: "." },
    ]);
  });

  it("leaves a lone asterisk and HTML alone as text", () => {
    expect(parseInline("2 * 3 <b>x</b>")).toEqual([{ type: "text", text: "2 * 3 <b>x</b>" }]);
  });
});

describe("parseMarkdown", () => {
  it("reads headings, paragraphs, lists and quotes", () => {
    const blocks = parseMarkdown("# Week 3\nGood work.\nKeep going.\n\n- one\n- two\n  wrapped\n1. first\n2. second\n> note\n#### small");
    expect(blocks.map((b) => b.type)).toEqual(["heading", "paragraph", "list", "list", "quote", "heading"]);
    expect(blocks[1]).toEqual({ type: "paragraph", content: [{ type: "text", text: "Good work. Keep going." }] });
    expect(blocks[2]).toMatchObject({ ordered: false, items: [[{ text: "one" }], [{ text: "two wrapped" }]] });
    expect(blocks[3]).toMatchObject({ ordered: true });
    expect(blocks[5]).toMatchObject({ level: 3 });
  });
});
