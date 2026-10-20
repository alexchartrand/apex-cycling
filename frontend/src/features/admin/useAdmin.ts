import { useQuery } from "@tanstack/react-query";
import { fetchAdminOverview } from "./api";

/** The worker beats every minute; look again at about that pace while the page is open. */
const REFRESH_MS = 30_000;

export function useAdminOverview() {
  return useQuery({ queryKey: ["admin", "overview"], queryFn: fetchAdminOverview, refetchInterval: REFRESH_MS });
}
