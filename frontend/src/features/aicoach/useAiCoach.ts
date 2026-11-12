import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  decideProposal,
  deleteConversation,
  fetchAdminAi,
  fetchAiAccess,
  fetchCoachProfile,
  fetchConversation,
  fetchProposal,
  giveConsent,
  listConversations,
  listProposals,
  listReports,
  requestReport,
  saveCoachProfile,
  sendMessage,
  startConversation,
  updateAdminAi,
  withdrawConsent,
} from "./api";
import type { CoachProfile, CoachSettings, Conversation, ProposalStatus, Turn } from "./types";

const key = (athleteId: string, ...rest: unknown[]) => ["ai-coach", athleteId, ...rest];

export function useAiAccess(athleteId: string | undefined) {
  return useQuery({
    queryKey: key(athleteId ?? "", "access"),
    queryFn: () => fetchAiAccess(athleteId!),
    enabled: !!athleteId,
    staleTime: 5 * 60_000,
  });
}

export function useConsent(athleteId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (args: { give: true } | { give: false; deleteHistory: boolean }) =>
      args.give ? giveConsent(athleteId) : withdrawConsent(athleteId, args.deleteHistory),
    onSuccess: (access) => {
      queryClient.setQueryData(key(athleteId, "access"), access);
      queryClient.invalidateQueries({ queryKey: key(athleteId) });
    },
  });
}

export function useCoachProfile(athleteId: string, enabled = true) {
  return useQuery({ queryKey: key(athleteId, "profile"), queryFn: () => fetchCoachProfile(athleteId), enabled });
}

export function useSaveCoachProfile(athleteId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { answers?: CoachProfile; settings?: CoachSettings }) => saveCoachProfile(athleteId, payload),
    onSuccess: (profile) => queryClient.setQueryData(key(athleteId, "profile"), profile),
  });
}

export function useConversations(athleteId: string, enabled = true) {
  return useQuery({ queryKey: key(athleteId, "conversations"), queryFn: () => listConversations(athleteId), enabled });
}

export function useConversation(athleteId: string, conversationId: string | null) {
  return useQuery({
    queryKey: key(athleteId, "conversation", conversationId),
    queryFn: () => fetchConversation(athleteId, conversationId!),
    enabled: !!conversationId,
  });
}

/** What a turn may have changed besides the conversation: proposals, the intake, the usage meter. */
function useAfterTurn(athleteId: string) {
  const queryClient = useQueryClient();
  return (turn: Turn) => {
    queryClient.setQueryData<Conversation | undefined>(key(athleteId, "conversation", turn.conversation_id), (old) =>
      old ? { ...old, messages: [...old.messages, ...turn.messages] } : old,
    );
    queryClient.invalidateQueries({ queryKey: key(athleteId, "conversation", turn.conversation_id) });
    queryClient.invalidateQueries({ queryKey: key(athleteId, "conversations") });
    queryClient.invalidateQueries({ queryKey: key(athleteId, "proposals") });
    queryClient.invalidateQueries({ queryKey: key(athleteId, "profile") });
    queryClient.invalidateQueries({ queryKey: key(athleteId, "access") });
  };
}

export function useStartConversation(athleteId: string) {
  const afterTurn = useAfterTurn(athleteId);
  return useMutation({
    mutationFn: (payload: { kind: "chat" | "intake"; content?: string }) => startConversation(athleteId, payload),
    onSuccess: afterTurn,
  });
}

export function useSendMessage(athleteId: string) {
  const afterTurn = useAfterTurn(athleteId);
  return useMutation({
    mutationFn: ({ conversationId, content }: { conversationId: string; content: string }) =>
      sendMessage(athleteId, conversationId, content),
    onSuccess: afterTurn,
  });
}

export function useDeleteConversation(athleteId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteConversation(athleteId, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key(athleteId, "conversations") }),
  });
}

export function useProposals(athleteId: string, status?: ProposalStatus) {
  return useQuery({
    queryKey: key(athleteId, "proposals", status ?? "all"),
    queryFn: () => listProposals(athleteId, status),
    enabled: athleteId !== "",
  });
}

export function useProposal(athleteId: string, proposalId: string | null) {
  return useQuery({
    queryKey: key(athleteId, "proposals", "one", proposalId),
    queryFn: () => fetchProposal(athleteId, proposalId!),
    enabled: !!proposalId,
  });
}

export function useDecideProposal(athleteId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "accept" | "reject" }) => decideProposal(athleteId, id, decision),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: key(athleteId) });
      // Accepting writes the calendar (and the library, for saved workouts).
      queryClient.invalidateQueries({ queryKey: ["planned-sessions", athleteId] });
      queryClient.invalidateQueries({ queryKey: ["workouts"] });
    },
  });
}

export function useReports(athleteId: string, enabled = true) {
  return useQuery({ queryKey: key(athleteId, "reports"), queryFn: () => listReports(athleteId), enabled: enabled && athleteId !== "" });
}

export function useRequestReport(athleteId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => requestReport(athleteId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: key(athleteId, "reports") });
      queryClient.invalidateQueries({ queryKey: key(athleteId, "proposals") });
      queryClient.invalidateQueries({ queryKey: key(athleteId, "access") });
    },
  });
}

export function useAdminAi(q: string) {
  return useQuery({ queryKey: ["admin", "ai-coach", q], queryFn: () => fetchAdminAi(q) });
}

export function useUpdateAdminAi() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ athleteId, ...payload }: { athleteId: string; enabled?: boolean; monthly_token_cap?: number }) =>
      updateAdminAi(athleteId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "ai-coach"] });
      queryClient.invalidateQueries({ queryKey: ["ai-coach"] });
    },
  });
}
