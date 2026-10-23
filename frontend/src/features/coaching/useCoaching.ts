import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  acceptCoachLink,
  fetchDashboard,
  fetchSquad,
  listCoachedAthletes,
  listCoachInbox,
  listCommentInbox,
  listMyCoaches,
  requestCoachLink,
  revokeCoachLink,
} from "./api";
import type { CoachLinkRequest } from "./types";

/** How often the "waiting for you" counters look for news while the app is open. */
const INBOX_REFRESH_MS = 60_000;

export function useCoachedAthletes() {
  return useQuery({ queryKey: ["coach-links", "athletes"], queryFn: listCoachedAthletes });
}

/** My coaches (or those of a managed athlete I run), active and waiting. */
export function useMyCoaches(athleteId?: string) {
  return useQuery({ queryKey: ["coach-links", "coaches", athleteId ?? "me"], queryFn: () => listMyCoaches(athleteId) });
}

export function useCoachInbox() {
  return useQuery({ queryKey: ["coach-links", "inbox"], queryFn: listCoachInbox, refetchInterval: INBOX_REFRESH_MS });
}

export function useCoachDashboard() {
  return useQuery({ queryKey: ["coach-links", "dashboard"], queryFn: fetchDashboard });
}

/** Every coached athlete's best at one event; `trackId` "" = anywhere. */
export function useSquad(eventKey: string, startType: string, trackId: string) {
  return useQuery({
    queryKey: ["coach-links", "squad", eventKey, startType, trackId],
    queryFn: () => fetchSquad(eventKey, startType, trackId),
    placeholderData: (previous) => previous,
  });
}

export function useCommentInbox() {
  return useQuery({ queryKey: ["comments", "inbox"], queryFn: listCommentInbox, refetchInterval: INBOX_REFRESH_MS });
}

/** Everything waiting for the user in the Coaching section: link requests plus threads with new comments. */
export function useCoachingBadgeCount(): number {
  const requests = useCoachInbox();
  const comments = useCommentInbox();
  return (requests.data?.length ?? 0) + (comments.data?.length ?? 0);
}

function useLinkMutation<T>(mutationFn: (variables: T) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    // Links change who can be switched to, what the dashboard lists and which comments are reachable.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["coach-links"] }),
  });
}

export function useRequestCoachLink() {
  return useLinkMutation((payload: CoachLinkRequest) => requestCoachLink(payload));
}

export function useAcceptCoachLink() {
  return useLinkMutation((linkId: string) => acceptCoachLink(linkId));
}

export function useRevokeCoachLink() {
  const queryClient = useQueryClient();
  return useLinkMutation(async (linkId: string) => {
    await revokeCoachLink(linkId);
    await queryClient.invalidateQueries({ queryKey: ["comments", "inbox"] });
  });
}
