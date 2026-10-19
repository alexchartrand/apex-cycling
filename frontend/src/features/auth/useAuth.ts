import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../api/client";
import { clearApiCache } from "../../pwa/apiCache";
import { fetchCurrentUser, login, logout, signup } from "./api";
import type { LoginPayload, SignupPayload } from "./types";

export const CURRENT_USER_KEY = ["auth", "me"];

export function useCurrentUser() {
  return useQuery({
    queryKey: CURRENT_USER_KEY,
    queryFn: fetchCurrentUser,
    retry: false,
    // A 401 just means "not logged in", and a TypeError means the server is
    // unreachable (offline) -- ProtectedRoute handles both; anything else is
    // a real bug for the error boundary.
    throwOnError: (error) => !(error instanceof ApiError && error.status === 401) && !(error instanceof TypeError),
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
    onSuccess: async () => {
      await clearApiCache();
      queryClient.setQueryData(CURRENT_USER_KEY, null);
      // Drop every other cached query too: the next user on this device must
      // not see the previous user's sessions. (Not queryClient.clear(): that
      // would also detach ProtectedRoute's observer of the "me" query, so it
      // would never see the null and redirect to /login.)
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== CURRENT_USER_KEY[0] });
    },
  });
}
