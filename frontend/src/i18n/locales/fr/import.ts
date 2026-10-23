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
    helpTitle: "Où trouver le code ?",
    helpBody: "Il est imprimé sur le transpondeur lui-même et ressemble à deux lettres, un tiret et des chiffres (LS-03407). Si le vôtre n'a pas d'étiquette, demandez à votre club ou au chronométreur. Indiquez le premier jour où vous l'avez utilisé : les tours d'avant cette date ne vous sont pas attribués.",
  },
  found: {
    some_one: "{{laps}} tours trouvés dans {{count}} séance.",
    some_other: "{{laps}} tours trouvés dans {{count}} séances.",
    none: "Aucun tour pour l'instant. Ils apparaissent dès que vous avez roulé avec le transpondeur pendant la période indiquée.",
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
