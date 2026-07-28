import { useState } from "react";
import { Card, Select } from "../components/ui";
import { useMyAthlete } from "../features/athletes/useAthlete";
import { ActiveImportPanel } from "../features/connections/ActiveImportPanel";
import { SqorzImportPanel } from "../features/connections/SqorzImportPanel";
import { StravaImportPanel } from "../features/connections/StravaImportPanel";
import "./ImportPage.css";

type ImportSource = "active" | "sqorz" | "strava";

const SOURCE_HELP: Record<ImportSource, string> = {
  active: "Imports currently syncing automatically. Stop one if you no longer want it to keep running.",
  sqorz: "Report the transponder(s) you've used to pull your training data from sqorz.",
  strava: "Connect a Strava account to import your rides.",
};

export function ImportPage() {
  const athlete = useMyAthlete();
  const [source, setSource] = useState<ImportSource>("sqorz");

  return (
    <div>
      <h1>Import</h1>
      {athlete.isLoading && <p>Loading…</p>}
      {athlete.isError && <p role="alert">Could not load your athlete profile. Try reloading the page.</p>}

      {athlete.data && (
        <Card>
          <Select
            className="import-page__source"
            label="Import source"
            value={source}
            onChange={(e) => setSource(e.target.value as ImportSource)}
          >
            <option value="active">Active Import</option>
            <option value="sqorz">Sqorz</option>
            <option value="strava">Strava</option>
          </Select>
          <p className="ui-card__hint">{SOURCE_HELP[source]}</p>

          {source === "active" && <ActiveImportPanel athleteId={athlete.data.id} />}
          {source === "sqorz" && <SqorzImportPanel athleteId={athlete.data.id} />}
          {source === "strava" && <StravaImportPanel />}
        </Card>
      )}
    </div>
  );
}
