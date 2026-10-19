import type { LocaleNamespace } from "../types";
import type en from "../en/settings";

export default {
  title: "Paramètres",
  profile: { title: "Profil", name: "Nom", email: "Courriel" },
  preferences: { title: "Préférences", language: "Langue", theme: "Thème" },
  more: "L'historique de poids et de FTP, le changement de mot de passe et l'export des données arrivent bientôt.",
} satisfies LocaleNamespace<typeof en>;
