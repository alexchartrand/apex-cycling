import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { addComment, deleteComment, editComment, listComments, markThreadRead } from "./api";

export function useComments(athleteId: string, eventId: string) {
  return useQuery({
    queryKey: ["comments", athleteId, eventId],
    queryFn: () => listComments(athleteId, eventId),
    enabled: athleteId !== "" && eventId !== "",
  });
}

/** A change to a thread refetches threads and the inbox (my own message counts as read; a deletion can clear unread ones). */
function useThreadMutation<T>(mutationFn: (variables: T) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["comments"] }),
  });
}

export function useAddComment(athleteId: string, eventId: string) {
  return useThreadMutation((body: string) => addComment(athleteId, eventId, body));
}

export function useEditComment(athleteId: string, eventId: string) {
  return useThreadMutation(({ id, body }: { id: string; body: string }) => editComment(athleteId, eventId, id, body));
}

export function useDeleteComment(athleteId: string, eventId: string) {
  return useThreadMutation((id: string) => deleteComment(athleteId, eventId, id));
}

export function useMarkThreadRead(athleteId: string, eventId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => markThreadRead(athleteId, eventId),
    // Only the inbox changes; the thread itself is the same.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["comments", "inbox"] }),
  });
}
