import { apiFetch, apiRequest } from "../../api/client";
import type { LoginPayload, Preferences, SignupPayload, User } from "./types";

export function fetchCurrentUser(): Promise<User> {
  return apiFetch<User>("/auth/me");
}

export function signup(payload: SignupPayload): Promise<User> {
  return apiFetch<User>("/auth/signup", { method: "POST", body: JSON.stringify(payload) });
}

export function login(payload: LoginPayload): Promise<User> {
  return apiFetch<User>("/auth/login", { method: "POST", body: JSON.stringify(payload) });
}

export function logout(): Promise<void> {
  return apiFetch<void>("/auth/logout", { method: "POST" });
}

export function updatePreferences(payload: Preferences): Promise<User> {
  return apiFetch<User>("/auth/me/preferences", { method: "PATCH", body: JSON.stringify(payload) });
}

export function changePassword(payload: { current_password: string; new_password: string }): Promise<User> {
  return apiFetch<User>("/auth/change-password", { method: "POST", body: JSON.stringify(payload) });
}

export function requestPasswordReset(email: string): Promise<{ email_enabled: boolean }> {
  return apiFetch("/auth/password-reset/request", { method: "POST", body: JSON.stringify({ email }) });
}

export function checkPasswordResetToken(token: string): Promise<{ email: string }> {
  return apiFetch("/auth/password-reset/check", { method: "POST", body: JSON.stringify({ token }) });
}

export function confirmPasswordReset(payload: { token: string; new_password: string }): Promise<User> {
  return apiFetch<User>("/auth/password-reset/confirm", { method: "POST", body: JSON.stringify(payload) });
}

export function deleteAccount(password: string): Promise<void> {
  return apiFetch<void>("/auth/delete-account", { method: "POST", body: JSON.stringify({ password }) });
}

/** Downloads the "export my data" zip through the browser. */
export async function downloadDataExport(): Promise<void> {
  const response = await apiRequest("/auth/me/export");
  const filename =
    /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") ?? "")?.[1] ?? "apexcycling-export.zip";
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
