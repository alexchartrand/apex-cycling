import type { LocaleNamespace } from "../types";
import type en from "../en/insights";

export default {
  banner: "Faits marquants de cette séance",
  whatsNew: { title: "Nouveautés", eyebrow: "Derniers faits marquants", more_one: "{{count}} autre fait marquant", more_other: "{{count}} autres faits marquants" },
  title: {
    personal_record: "Nouveau record · {{event}}",
    season_best: "Meilleur de la saison · {{event}}",
    best_nth_lap: "Meilleur tour {{n}} de la saison",
    most_consistent: "Effort le plus régulier de la saison",
  },
  detail: {
    personal_record: "{{start}} · {{time}}, {{faster}} de mieux que {{previous}}",
    season_best: "{{start}} · {{time}}, {{faster}} de mieux que votre meilleur de la saison ({{previous}})",
    best_nth_lap: "Effort {{start}} · {{time}}, {{faster}} de mieux qu'avant ({{previous}})",
    most_consistent: "{{start}} · {{count}} tours, temps au tour à moins de {{spread}} % d'écart",
  },
  milestone: "premier temps sous {{milestone}}",
  toast: {
    title_one: "{{count}} nouveau fait marquant",
    title_other: "{{count}} nouveaux faits marquants",
  },
} satisfies LocaleNamespace<typeof en>;
