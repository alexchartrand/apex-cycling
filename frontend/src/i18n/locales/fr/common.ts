import type { LocaleNamespace } from "../types";
import type en from "../en/common";

export default {
  appName: "ApexCycling",
  loading: "Chargement…",
  retry: "Réessayer",
  cancel: "Annuler",
  save: "Enregistrer",
  saving: "Enregistrement…",
  close: "Fermer",
  delete: "Supprimer",
  edit: "Modifier",
  back: "Retour",
  none: "Aucun",
  unknownError: "Une erreur est survenue. Veuillez réessayer.",
  networkError: "Impossible de joindre le serveur. Vérifiez votre connexion.",
  loadError: "Impossible de charger ce contenu. Rechargez la page.",
  offlineTitle: "Vous êtes hors ligne",
  crashTitle: "Un problème est survenu",
  crashDescription: "Une erreur inattendue a interrompu cette page. Un rechargement règle généralement le problème.",
  reloadApp: "Recharger ApexCycling",
  language: "Langue",
  languages: { fr: "Français", en: "English" },
  theme: "Thème",
  themes: { system: "Système", light: "Papier", dark: "Nuit" },
  units: { s: "s", kmh: "km/h", km: "km", m: "m", w: "W", kg: "kg", bpm: "bpm", rpm: "rpm", h: "h" },
} satisfies LocaleNamespace<typeof en>;
