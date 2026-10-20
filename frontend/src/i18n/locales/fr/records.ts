import type { LocaleNamespace } from "../types";
import type en from "../en/records";

export default {
  events: {
    f200: "200 m lancé",
    lap: "Tour lancé",
    "500m": "500 m",
    "750m": "750 m",
    "1km": "1 km",
    "2km": "Poursuite 2 km",
    "3km": "Poursuite 3 km",
    "4km": "Poursuite 4 km",
  },
  startTypes: { standing: "Départ arrêté", flying: "Départ lancé", unknown: "Départ inconnu" },
  badge: "Record",
} satisfies LocaleNamespace<typeof en>;
