import { apiFetch } from "../../api/client";
import type { CalendarFeedStatus, Competition, CompetitionWrite, Season, SeasonSummary, SeasonWrite } from "./types";

const base = (athleteId: string) => `/athletes/${athleteId}`;
const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

export const listSeasons = (athleteId: string) => apiFetch<Season[]>(`${base(athleteId)}/seasons`);
export const getSeason = (athleteId: string, seasonId: string) => apiFetch<SeasonSummary>(`${base(athleteId)}/seasons/${seasonId}`);
export const createSeason = (athleteId: string, payload: SeasonWrite) => apiFetch<Season>(`${base(athleteId)}/seasons`, json("POST", payload));
export const updateSeason = (athleteId: string, seasonId: string, payload: Partial<SeasonWrite>) =>
  apiFetch<Season>(`${base(athleteId)}/seasons/${seasonId}`, json("PATCH", payload));
export const deleteSeason = (athleteId: string, seasonId: string) => apiFetch<void>(`${base(athleteId)}/seasons/${seasonId}`, { method: "DELETE" });

export const listCompetitions = (athleteId: string) => apiFetch<Competition[]>(`${base(athleteId)}/competitions`);
export const createCompetition = (athleteId: string, payload: CompetitionWrite) =>
  apiFetch<Competition>(`${base(athleteId)}/competitions`, json("POST", payload));
export const updateCompetition = (athleteId: string, id: string, payload: CompetitionWrite) =>
  apiFetch<Competition>(`${base(athleteId)}/competitions/${id}`, json("PATCH", payload));
export const deleteCompetition = (athleteId: string, id: string) => apiFetch<void>(`${base(athleteId)}/competitions/${id}`, { method: "DELETE" });

export const getCalendarFeed = (athleteId: string) => apiFetch<CalendarFeedStatus>(`${base(athleteId)}/calendar-feed`);
export const makeCalendarFeed = (athleteId: string) => apiFetch<CalendarFeedStatus>(`${base(athleteId)}/calendar-feed`, { method: "POST" });
export const closeCalendarFeed = (athleteId: string) => apiFetch<void>(`${base(athleteId)}/calendar-feed`, { method: "DELETE" });
