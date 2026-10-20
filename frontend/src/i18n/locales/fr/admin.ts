import type { LocaleNamespace } from "../types";
import type en from "../en/admin";

export default {
  title: "Administration",
  description: "Le processus d'arrière-plan est-il vivant, quelles synchronisations échouent et qui s'est inscrit récemment.",
  loadFailed: "Impossible de charger l'état",
  counts: { users: "Comptes", athletes: "Athlètes", clubs: "Clubs", transponders: "Transpondeurs actifs" },
  worker: {
    title: "Processus d'arrière-plan",
    state: { ok: "En marche", stale: "Ne répond plus", never: "Jamais démarré" },
    never: "Aucun signal de vie n'a encore été enregistré. Vérifiez que le conteneur du worker est démarré.",
    lastSeen: "Dernier signal de vie",
    started: "Démarré",
    lastPoll: "Dernière interrogation de sqorz",
    pollSummary: "{{when}} — {{count}} connexion(s), {{failures}} en échec",
    noPoll: "Pas encore terminée",
  },
  failures: {
    title: "Synchronisations en échec",
    none: "Aucune synchronisation en échec",
    transponder: "Transpondeur",
    when: "Quand",
    http: "HTTP",
    error: "Erreur",
  },
  users: {
    title: "Derniers comptes",
    user: "Compte",
    joined: "Inscrit le",
    status: "Statut",
    admin: "Admin",
    inactive: "Inactif",
  },
} satisfies LocaleNamespace<typeof en>;
