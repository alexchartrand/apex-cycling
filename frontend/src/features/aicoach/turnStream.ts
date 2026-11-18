import type { Turn } from "./types";

/** What a streamed turn sends (backend `coach_ai/router.py::_stream_turn`). */
export type TurnEvent =
  | { type: "thinking" }
  | { type: "text"; text: string }
  | { type: "tool"; name: string }
  | { type: "done"; turn: Turn }
  | { type: "error"; detail: string };

/** Splits server-sent events out of the text chunks a fetch body arrives in.
 *  Only `data:` lines matter; `: keep-alive` comments are skipped. */
export function sseParser(onEvent: (event: TurnEvent) => void): (chunk: string, end?: boolean) => void {
  let buffer = "";
  const flush = (block: string) => {
    const data = block
      .split(/\r?\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).replace(/^ /, ""))
      .join("\n");
    if (!data) return;
    try {
      onEvent(JSON.parse(data) as TurnEvent);
    } catch {
      // a malformed event is dropped; the turn still ends with done/error
    }
  };
  return (chunk, end = false) => {
    buffer += chunk;
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? "";
    blocks.forEach(flush);
    if (end && buffer) {
      flush(buffer);
      buffer = "";
    }
  };
}

/** The reply as the athlete sees it while it is written. */
export interface LiveReply {
  /** The answer so far; the text of a round that turned into a tool call is dropped. */
  text: string;
  phase: "waiting" | "thinking" | "tool" | "writing";
  /** The tool being run, while `phase` is "tool". */
  tool: string | null;
}

export const LIVE_START: LiveReply = { text: "", phase: "waiting", tool: null };

export function liveReply(state: LiveReply, event: TurnEvent): LiveReply {
  switch (event.type) {
    case "thinking":
      return { ...state, phase: state.text ? state.phase : "thinking" };
    case "text":
      return { text: state.text + event.text, phase: "writing", tool: null };
    case "tool":
      return { text: "", phase: "tool", tool: event.name };
    default:
      return state;
  }
}
