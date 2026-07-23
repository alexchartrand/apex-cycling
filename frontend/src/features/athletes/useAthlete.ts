import { useQuery } from "@tanstack/react-query";
import { fetchMyAthlete } from "./api";

export function useMyAthlete() {
  return useQuery({
    queryKey: ["athletes", "me"],
    queryFn: fetchMyAthlete,
  });
}
