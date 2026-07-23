import { apiFetch } from "../../api/client";
import type { LoginPayload, SignupPayload, User } from "./types";

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
