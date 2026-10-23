import type { LocaleNamespace } from "../types";
import type en from "../en/home";

export default {
  greeting: {
    morning: "Bonjour, {{name}}",
    afternoon: "Bon après-midi, {{name}}",
    evening: "Bonsoir, {{name}}",
  },
  week: {
    sessions: "Séances cette semaine",
    laps: "Tours cette semaine",
    distance: "{{distance}} sur piste",
    trackTime: "Temps sur piste",
    vsLastWeek: "vs semaine dernière",
  },
  latest: {
    eyebrow: "Dernière séance",
    open: "Ouvrir",
    tracks: "Pistes",
  },
  recent: { title: "Séances récentes", viewAll: "Tout voir" },
  sync: {
    title: "Synchronisation",
    lastSync: "Dernière synchro {{when}}",
    never: "Aucune synchro pour l'instant",
    failed: "La dernière synchro a échoué",
    activeTransponders_one: "{{count}} transpondeur synchronisé automatiquement",
    activeTransponders_other: "{{count}} transpondeurs synchronisés automatiquement",
    noActive: "Aucun transpondeur n'est synchronisé automatiquement.",
    manage: "Gérer les importations",
  },
  checklist: {
    eyebrow: "Pour commencer",
    title: "Configurez ApexCycling",
    progress: "{{done}} sur {{total}}",
    optional: "facultatif",
    done: "fait",
    hide: "Masquer cette liste",
    steps: {
      transponder: {
        title: "Connectez votre transpondeur",
        hint: "Vos tours sont importés après chaque séance.",
        action: "Connecter",
      },
      physiology: {
        title: "Ajoutez votre poids et votre FTP",
        hint: "Le poids donne les W/kg et le labo aéro ; la FTP ne sert que si vous vous entraînez avec la puissance.",
        action: "Ajouter",
      },
      club: { title: "Rejoignez votre club", hint: "Collez un lien d'invitation, ou créez le club.", action: "Ouvrir les clubs" },
      coach: { title: "Choisissez un entraîneur", hint: "Un entraîneur peut suivre vos séances et planifier les prochaines.", action: "Trouver un entraîneur" },
    },
  },
  onboarding: {
    title: "Bienvenue sur ApexCycling",
    description: "Associez le transpondeur sqorz que vous utilisez et vos tours seront importés automatiquement après chaque séance.",
    action: "Associer un transpondeur",
  },
} satisfies LocaleNamespace<typeof en>;
