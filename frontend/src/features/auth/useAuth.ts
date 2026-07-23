import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../api/client";
import { fetchCurrentUser, login, logout, signup } from "./api";
import type { LoginPayload, SignupPayload } from "./types";

const CURRENT_USER_KEY = ["auth", "me"];

export function useCurrentUser() {
  return useQuery({
    queryKey: CURRENT_USER_KEY,
    queryFn: fetchCurrentUser,
    retry: false,
    // A 401 just means "not logged in" -- not a transient error worth
    // surfacing as query.isError to the UI.
    throwOnError: (error) => !(error instanceof ApiError && error.status === 401),
  });
}

export function useSignup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SignupPayload) => signup(payload),
    onSuccess: (user) => queryClient.setQueryData(CURRENT_USER_KEY, user),
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LoginPayload) => login(payload),
    onSuccess: (user) => queryClient.setQueryData(CURRENT_USER_KEY, user),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logout,
    onSuccess: () => queryClient.setQueryData(CURRENT_USER_KEY, null),
  });
}
