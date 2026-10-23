import type { LocaleNamespace } from "../types";
import type en from "../en/share";

export default {
  share: "Partager en image",
  saved: "Image enregistrée",
  savedDescription: "Cherchez-la dans vos téléchargements pour la publier.",
  failed: "Impossible de créer l'image.",
  brand: "ApexCycling",
  record: "Record · {{start}}",
  effort: "Effort · {{start}}",
  splits: "Temps au tour (s)",
  vsPrevious: "par rapport au record précédent",
  firstUnder: "premier temps sous {{milestone}}",
  average: "{{speed}} km/h de moyenne",
} satisfies LocaleNamespace<typeof en>;
