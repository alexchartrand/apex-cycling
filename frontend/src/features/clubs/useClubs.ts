import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  acceptInvite,
  createClub,
  createInvite,
  createManagedAthlete,
  deleteManagedAthlete,
  linkSqorzAccount,
  listClubs,
  listClubTracks,
  listInvites,
  listMembers,
  listRoster,
  listSqorzAccounts,
  previewInvite,
  removeMember,
  revokeInvite,
  setMemberRole,
  unlinkSqorzAccount,
  updateClub,
} from "./api";
import type { ClubRole, InvitePayload, ManagedAthletePayload } from "./types";

export function useMyClubs() {
  return useQuery({ queryKey: ["clubs"], queryFn: listClubs });
}

export function useMembers(clubId: string) {
  return useQuery({ queryKey: ["clubs", clubId, "members"], queryFn: () => listMembers(clubId), enabled: clubId !== "" });
}

/** `enabled` is false for athletes, who can't see the roster. */
export function useRoster(clubId: string, enabled = true) {
  return useQuery({ queryKey: ["clubs", clubId, "roster"], queryFn: () => listRoster(clubId), enabled: enabled && clubId !== "" });
}

/** The rosters of several clubs at once (the clubs the user administers, for the athlete switcher). */
export function useRosters(clubIds: string[]) {
  return useQueries({
    queries: clubIds.map((clubId) => ({ queryKey: ["clubs", clubId, "roster"], queryFn: () => listRoster(clubId) })),
  });
}

/** The members of several clubs at once (to pick a coach from). */
export function useMemberLists(clubIds: string[]) {
  return useQueries({
    queries: clubIds.map((clubId) => ({ queryKey: ["clubs", clubId, "members"], queryFn: () => listMembers(clubId) })),
  });
}

export function useInvites(clubId: string, enabled: boolean) {
  return useQuery({ queryKey: ["clubs", clubId, "invites"], queryFn: () => listInvites(clubId), enabled: enabled && clubId !== "" });
}

export function useSqorzAccounts(clubId: string) {
  return useQuery({ queryKey: ["clubs", clubId, "sqorz-accounts"], queryFn: () => listSqorzAccounts(clubId), enabled: clubId !== "" });
}

export function useClubTracks(clubId: string) {
  return useQuery({ queryKey: ["club-tracks", clubId], queryFn: () => listClubTracks(clubId), enabled: clubId !== "" });
}

export function useInvitePreview(token: string) {
  return useQuery({
    queryKey: ["invite-preview", token],
    queryFn: () => previewInvite(token),
    enabled: token !== "",
    retry: false,
    // Previewing is free, but the answer changes once the link is used.
    staleTime: 0,
    gcTime: 0,
  });
}

/** A change to a club: every `["clubs", …]` query refetches, plus whatever else it touches. */
function useClubMutation<T, R>(mutationFn: (variables: T) => Promise<R>, alsoInvalidate: string[][] = []) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => Promise.all([["clubs"], ...alsoInvalidate].map((queryKey) => queryClient.invalidateQueries({ queryKey }))),
  });
}

export function useCreateClub() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createClub,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["clubs"] }),
  });
}

export function useUpdateClub(clubId: string) {
  return useClubMutation((payload: { name?: string; timezone?: string }) => updateClub(clubId, payload));
}

export function useSetMemberRole(clubId: string) {
  return useClubMutation(({ membershipId, role }: { membershipId: string; role: ClubRole }) =>
    setMemberRole(clubId, membershipId, role),
  );
}

export function useRemoveMember(clubId: string) {
  // Leaving or removing someone changes the roster, and a leaver's own club list.
  return useClubMutation((membershipId: string) => removeMember(clubId, membershipId), [["athletes"]]);
}

export function useCreateManagedAthlete(clubId: string) {
  return useClubMutation((payload: ManagedAthletePayload) => createManagedAthlete(clubId, payload));
}

export function useDeleteManagedAthlete(clubId: string) {
  return useClubMutation((athleteId: string) => deleteManagedAthlete(clubId, athleteId), [["coach-links"]]);
}

export function useCreateInvite(clubId: string) {
  return useClubMutation((payload: InvitePayload) => createInvite(clubId, payload));
}

export function useRevokeInvite(clubId: string) {
  return useClubMutation((inviteId: string) => revokeInvite(clubId, inviteId));
}

export function useAcceptInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (token: string) => acceptInvite(token),
    // Joining as an athlete puts my profile on the roster too.
    onSuccess: () => Promise.all([["clubs"], ["athletes"]].map((queryKey) => queryClient.invalidateQueries({ queryKey }))),
  });
}

export function useLinkSqorzAccount(clubId: string) {
  return useClubMutation((sqorzAccountId: string) => linkSqorzAccount(clubId, sqorzAccountId), [["club-tracks"]]);
}

export function useUnlinkSqorzAccount(clubId: string) {
  return useClubMutation((sqorzAccountId: string) => unlinkSqorzAccount(clubId, sqorzAccountId), [["club-tracks"], ["tracks"]]);
}
