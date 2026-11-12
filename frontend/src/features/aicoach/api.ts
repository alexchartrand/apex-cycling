import { apiFetch } from "../../api/client";
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

export const startConversation = (athleteId: string, payload: { kind: "chat" | "intake"; content?: string }) =>
  apiFetch<Turn>(`${base(athleteId)}/conversations`, { method: "POST", body: JSON.stringify(payload) });

export const sendMessage = (athleteId: string, conversationId: string, content: string) =>
  apiFetch<Turn>(`${base(athleteId)}/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });

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
