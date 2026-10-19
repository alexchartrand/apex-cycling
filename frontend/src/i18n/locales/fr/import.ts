import type { LocaleNamespace } from "../types";
import type en from "../en/import";

export default {
  title: "Importer",
  description: "Ajoutez vos données d'entraînement à ApexCycling.",
  comingSoon: "Bientôt disponible",
  sources: {
    sqorz: {
      title: "Transpondeur sqorz",
      description: "Indiquez le transpondeur utilisé et pendant quelle période. Les tours sont récupérés sur my.sqorz.com et vous sont attribués pour cette période.",
    },
    files: { title: "Fichiers FIT / TCX / GPX", description: "Téléversez les sorties de n'importe quel compteur pour ajouter puissance, fréquence cardiaque et cadence." },
    strava: { title: "Strava", description: "Synchronisez automatiquement les activités de votre compte Strava." },
    intervals: { title: "Intervals.icu", description: "Synchronisez activités et puissance avec une clé d'API Intervals.icu." },
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
