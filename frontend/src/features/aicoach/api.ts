import { ApiError, apiFetch, apiRequest } from "../../api/client";
import { sseParser, type TurnEvent } from "./turnStream";
import type {
  AdminAiOverview,
  AdminAiRow,
  AiAccess,
  AiReport,
  CoachProfileRead,
  Conversation,
  ConversationSummary,
  CoachProfile,
  CoachSettings,
  Proposal,
  ProposalStatus,
  Turn,
} from "./types";

const base = (athleteId: string) => `/athletes/${athleteId}/ai-coach`;

export const fetchAiAccess = (athleteId: string) => apiFetch<AiAccess>(base(athleteId));

export const giveConsent = (athleteId: string) => apiFetch<AiAccess>(`${base(athleteId)}/consent`, { method: "POST" });

export const withdrawConsent = (athleteId: string, deleteHistory: boolean) =>
  apiFetch<AiAccess>(`${base(athleteId)}/consent/withdraw`, {
    method: "POST",
    body: JSON.stringify({ delete_history: deleteHistory }),
  });

export const fetchCoachProfile = (athleteId: string) => apiFetch<CoachProfileRead>(`${base(athleteId)}/profile`);

export const saveCoachProfile = (athleteId: string, payload: { answers?: CoachProfile; settings?: CoachSettings }) =>
  apiFetch<CoachProfileRead>(`${base(athleteId)}/profile`, { method: "PUT", body: JSON.stringify(payload) });

export const listConversations = (athleteId: string) => apiFetch<ConversationSummary[]>(`${base(athleteId)}/conversations`);

export const fetchConversation = (athleteId: string, id: string) =>
  apiFetch<Conversation>(`${base(athleteId)}/conversations/${id}`);

const ERROR_STATUS: Record<string, number> = { ai_coach_cap_reached: 429, ai_coach_failed: 502 };

/** Posts a turn asking for server-sent events: `onEvent` gets the reply as it is
 *  written, the promise the stored turn. A failure mid-stream rejects with the
 *  same `ApiError` the plain JSON answer would have given. */
async function streamTurn(path: string, body: unknown, onEvent: (event: TurnEvent) => void): Promise<Turn> {
  const response = await apiRequest(path, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { Accept: "text/event-stream" },
  });
  if (!response.body || !response.headers.get("Content-Type")?.includes("text/event-stream")) {
    return (await response.json()) as Turn;
  }
  let outcome: TurnEvent | null = null;
  const feed = sseParser((event) => {
    if (event.type === "done" || event.type === "error") outcome = event;
    else onEvent(event);
  });
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    feed(value);
  }
  feed("", true);
  const last = outcome as TurnEvent | null;
  if (last?.type === "done") return last.turn;
  const detail = last?.type === "error" ? last.detail : "ai_coach_failed";
  throw new ApiError(ERROR_STATUS[detail] ?? 502, detail);
}

export type StartPayload = { kind: "chat" | "intake"; content?: string; training_plan_id?: string };

export const startConversation = (
  athleteId: string,
  payload: StartPayload,
  onEvent: (event: TurnEvent) => void,
) => streamTurn(`${base(athleteId)}/conversations`, payload, onEvent);

export const sendMessage = (athleteId: string, conversationId: string, content: string, onEvent: (event: TurnEvent) => void) =>
  streamTurn(`${base(athleteId)}/conversations/${conversationId}/messages`, { content }, onEvent);

export const deleteConversation = (athleteId: string, id: string) =>
  apiFetch<void>(`${base(athleteId)}/conversations/${id}`, { method: "DELETE" });

export const listProposals = (athleteId: string, status?: ProposalStatus) =>
  apiFetch<Proposal[]>(`${base(athleteId)}/proposals${status ? `?status=${status}` : ""}`);

export const fetchProposal = (athleteId: string, id: string) => apiFetch<Proposal>(`${base(athleteId)}/proposals/${id}`);

export const decideProposal = (athleteId: string, id: string, decision: "accept" | "reject") =>
  apiFetch<Proposal>(`${base(athleteId)}/proposals/${id}/${decision}`, { method: "POST" });

export const listReports = (athleteId: string) => apiFetch<AiReport[]>(`${base(athleteId)}/reports`);

export const requestReport = (athleteId: string) => apiFetch<AiReport>(`${base(athleteId)}/reports`, { method: "POST" });

export const fetchAdminAi = (q: string) =>
  apiFetch<AdminAiOverview>(`/admin/ai-coach${q.trim() ? `?q=${encodeURIComponent(q.trim())}` : ""}`);

export const updateAdminAi = (athleteId: string, payload: { enabled?: boolean; monthly_token_cap?: number }) =>
  apiFetch<AdminAiRow>(`/admin/ai-coach/${athleteId}`, { method: "PUT", body: JSON.stringify(payload) });
