import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getPreferences, getPushConfig, getUnreadCount, listNotifications, markRead, savePreferences } from "./api";

const REFRESH_MS = 60_000;

export const unreadKey = ["notifications", "unread"] as const;

export function useUnreadCount(): number {
  const query = useQuery({ queryKey: unreadKey, queryFn: getUnreadCount, refetchInterval: REFRESH_MS });
  return query.data ?? 0;
}

/** The list is only fetched while the bell's panel is open. */
export function useNotificationList(enabled: boolean) {
  return useQuery({ queryKey: ["notifications", "list"], queryFn: listNotifications, enabled, refetchOnMount: "always" });
}

export function useMarkRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ids?: string[]) => markRead(ids),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });
}

export function useNotificationPreferences() {
  return useQuery({ queryKey: ["notifications", "preferences"], queryFn: getPreferences });
}

export function useSaveNotificationPreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: savePreferences,
    onSuccess: (saved) => queryClient.setQueryData(["notifications", "preferences"], saved),
  });
}

export function usePushConfig() {
  return useQuery({ queryKey: ["notifications", "push-config"], queryFn: getPushConfig, staleTime: Infinity });
}
