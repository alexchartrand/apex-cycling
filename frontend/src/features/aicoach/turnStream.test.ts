import { describe, expect, it } from "vitest";
import { LIVE_START, liveReply, sseParser, type TurnEvent } from "./turnStream";

describe("sseParser", () => {
  it("reads events split across chunks and skips keep-alive comments", () => {
    const events: TurnEvent[] = [];
    const feed = sseParser((event) => events.push(event));
    feed('data: {"type":"thinking"}\n\n: keep-alive\n\ndata: {"type":"te');
    feed('xt","text":"Bon"}\n\ndata: {"type":"text","text":"jour"}\n');
    expect(events).toEqual([{ type: "thinking" }, { type: "text", text: "Bon" }]);
    feed("\n");
    expect(events.at(-1)).toEqual({ type: "text", text: "jour" });
  });

  it("flushes a last event without its blank line and drops malformed ones", () => {
    const events: TurnEvent[] = [];
    const feed = sseParser((event) => events.push(event));
    feed("data: {oops}\r\n\r\n");
    feed('data: {"type":"error","detail":"ai_coach_failed"}', true);
    expect(events).toEqual([{ type: "error", detail: "ai_coach_failed" }]);
  });
});

describe("liveReply", () => {
  it("drops a tool round's text and shows the answer as it comes", () => {
    const steps: TurnEvent[] = [
      { type: "thinking" },
      { type: "text", text: "Je regarde." },
      { type: "tool", name: "get_plans" },
      { type: "thinking" },
      { type: "text", text: "Rien " },
      { type: "thinking" },
      { type: "text", text: "de prévu." },
    ];
    const seen = steps.reduce<ReturnType<typeof liveReply>[]>((all, event) => [...all, liveReply(all.at(-1) ?? LIVE_START, event)], []);
    expect(seen.map((s) => s.phase)).toEqual(["thinking", "writing", "tool", "thinking", "writing", "writing", "writing"]);
    expect(seen[2]).toEqual({ text: "", phase: "tool", tool: "get_plans" });
    expect(seen.at(-1)?.text).toBe("Rien de prévu.");
  });
});
