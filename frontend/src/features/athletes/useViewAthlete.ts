import { useNavigate } from "react-router-dom";
import { coachAthletePath } from "./athleteScope";
import { useMyAthlete } from "./useAthlete";
import { useSwitchOptions } from "./useSwitchOptions";
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

/**
 * Open an athlete page (`/sessions/…`) whoever's it is: my own, a roster
 * athlete through the switch, else an athlete I coach, read-only under
 * `/coach/athletes/:id`.
 */
export function useOpenAthletePage() {
  const navigate = useNavigate();
  const view = useViewAthlete();
  const me = useMyAthlete().data;
  const options = useSwitchOptions();
  return (athleteId: string, to: string) => {
    if (athleteId === me?.id || options.some((option) => option.athleteId === athleteId)) view(athleteId, to);
    else navigate(coachAthletePath(athleteId, to));
  };
}
