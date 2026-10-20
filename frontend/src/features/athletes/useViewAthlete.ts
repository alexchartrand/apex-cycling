import { useNavigate } from "react-router-dom";
import { useMyAthlete } from "./useAthlete";
import { setViewingAthleteId } from "./viewing";

/** Switch to an athlete's data and go to `to` (their dashboard by default). */
export function useViewAthlete() {
  const navigate = useNavigate();
  const me = useMyAthlete().data;
  return (athleteId: string, to = "/") => {
    setViewingAthleteId(athleteId === me?.id ? null : athleteId);
    navigate(to);
  };
}
