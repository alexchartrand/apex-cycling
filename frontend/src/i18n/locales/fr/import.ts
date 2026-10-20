import type { LocaleNamespace } from "../types";
import type en from "../en/import";

export default {
  title: "Importer",
  description: "Ajoutez vos données d'entraînement à ApexCycling.",
  sources: {
    sqorz: {
      title: "Transpondeur sqorz",
      description: "Indiquez le transpondeur utilisé et pendant quelle période. Les tours sont récupérés sur my.sqorz.com et vous sont attribués pour cette période.",
    },
  },
  form: {
    title: "Ajouter un transpondeur",
    transponder: "Code du transpondeur",
    transponderHint: "Tel qu'imprimé sur le transpondeur, p. ex. LS-03407.",
    start: "Premier jour d'utilisation",
    end: "Dernier jour",
    keepSyncing: "Je l'utilise encore — synchroniser automatiquement",
    submit: "Ajouter le transpondeur",
  },
  assignments: {
    title: "Vos transpondeurs",
    empty: "Aucun transpondeur déclaré pour l'instant.",
    syncing: "En synchro",
    ended: "Terminé",
    range: "{{start}} → {{end}}",
    rangeOngoing: "Depuis le {{start}}",
    syncNow: "Synchroniser",
    stop: "Arrêter la synchro",
    stopTitle: "Arrêter la synchro de {{code}}?",
    stopDescription: "Les tours déjà importés sont conservés. Les tours faits avec ce transpondeur à partir de demain ne vous seront plus attribués.",
  },
  runs: {
    title: "Synchronisations récentes",
    empty: "Aucune synchro pour l'instant — ajoutez un transpondeur pour en lancer une.",
    success: "Réussie",
    pending: "En cours",
    failed: "Échec",
  },
  toasts: {
    added: "Transpondeur ajouté",
    addedDescription: "Vos tours sont en cours d'importation.",
    synced: "Synchronisation terminée",
    syncFailed: "Échec de la synchronisation",
    stopped: "Synchro automatique arrêtée",
  },
} satisfies LocaleNamespace<typeof en>;
