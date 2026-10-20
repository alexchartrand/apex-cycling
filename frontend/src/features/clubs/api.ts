import { apiFetch } from "../../api/client";
import type { Athlete } from "../athletes/types";
import type { TrackSummary } from "../training/types";
import type {
  Club,
  ClubRole,
  Invite,
  InviteCreated,
  InvitePayload,
  InvitePreview,
  ManagedAthletePayload,
  Member,
  RosterAthlete,
  SqorzAccount,
} from "./types";

const json = (body: unknown): RequestInit => ({ body: JSON.stringify(body) });

export function listClubs(): Promise<Club[]> {
  return apiFetch<Club[]>("/clubs");
}

export function createClub(payload: { name: string; timezone: string }): Promise<Club> {
  return apiFetch<Club>("/clubs", { method: "POST", ...json(payload) });
}

export function updateClub(clubId: string, payload: { name?: string; timezone?: string }): Promise<Club> {
  return apiFetch<Club>(`/clubs/${clubId}`, { method: "PATCH", ...json(payload) });
}

export function listMembers(clubId: string): Promise<Member[]> {
  return apiFetch<Member[]>(`/clubs/${clubId}/members`);
}

export function setMemberRole(clubId: string, membershipId: string, role: ClubRole): Promise<{ role: ClubRole }> {
  return apiFetch(`/clubs/${clubId}/members/${membershipId}`, { method: "PATCH", ...json({ role }) });
}

/** An admin removes anyone; anyone can remove themselves (leave). */
export function removeMember(clubId: string, membershipId: string): Promise<void> {
  return apiFetch<void>(`/clubs/${clubId}/members/${membershipId}`, { method: "DELETE" });
}

export function listRoster(clubId: string): Promise<RosterAthlete[]> {
  return apiFetch<RosterAthlete[]>(`/clubs/${clubId}/athletes`);
}

export function createManagedAthlete(clubId: string, payload: ManagedAthletePayload): Promise<Athlete> {
  return apiFetch<Athlete>(`/clubs/${clubId}/athletes`, { method: "POST", ...json(payload) });
}

export function deleteManagedAthlete(clubId: string, athleteId: string): Promise<void> {
  return apiFetch<void>(`/clubs/${clubId}/athletes/${athleteId}`, { method: "DELETE" });
}

export function listInvites(clubId: string): Promise<Invite[]> {
  return apiFetch<Invite[]>(`/clubs/${clubId}/invites`);
}

export function createInvite(clubId: string, payload: InvitePayload): Promise<InviteCreated> {
  return apiFetch<InviteCreated>(`/clubs/${clubId}/invites`, { method: "POST", ...json(payload) });
}

export function revokeInvite(clubId: string, inviteId: string): Promise<void> {
  return apiFetch<void>(`/clubs/${clubId}/invites/${inviteId}`, { method: "DELETE" });
}

// The token travels in the body, not the path, so it stays out of access logs.
export function previewInvite(token: string): Promise<InvitePreview> {
  return apiFetch<InvitePreview>("/invites/preview", { method: "POST", ...json({ token }) });
}

export function acceptInvite(token: string): Promise<Club> {
  return apiFetch<Club>("/invites/accept", { method: "POST", ...json({ token }) });
}

export function listSqorzAccounts(clubId: string): Promise<SqorzAccount[]> {
  return apiFetch<SqorzAccount[]>(`/clubs/${clubId}/sqorz-accounts`);
}

export function linkSqorzAccount(clubId: string, sqorzAccountId: string): Promise<SqorzAccount> {
  return apiFetch<SqorzAccount>(`/clubs/${clubId}/sqorz-accounts`, {
    method: "POST",
    ...json({ sqorz_account_id: sqorzAccountId }),
  });
}

export function unlinkSqorzAccount(clubId: string, sqorzAccountId: string): Promise<void> {
  return apiFetch<void>(`/clubs/${clubId}/sqorz-accounts/${encodeURIComponent(sqorzAccountId)}`, { method: "DELETE" });
}

export function listClubTracks(clubId: string): Promise<TrackSummary[]> {
  return apiFetch<TrackSummary[]>(`/clubs/${clubId}/tracks`);
}
