import type { LocaleNamespace } from "../types";
import type en from "../en/notifications";

export default {
  bell: "Notifications",
  bellUnread_one: "Notifications, {{count}} non lue",
  bellUnread_other: "Notifications, {{count}} non lues",
  title: "Notifications",
  markAllRead: "Tout marquer comme lu",
  empty: "Vous êtes à jour.",
  loadError: "Impossible de charger vos notifications.",
  settingsLink: "Réglages des notifications",
  newPr: {
    one: "Nouveau record · {{event}}",
    many: "{{count}} nouveaux records",
    body: "{{session}} · {{time}}",
  },
  syncFailed: { title: "Échec de la synchronisation", body: "Transpondeur {{code}} : {{error}}" },
  comment: { title: "{{author}} a commenté", body: "{{session}} : {{excerpt}}" },
  coachRequest: {
    title: "Demande d'entraînement",
    fromAthlete: "{{name}} aimerait que vous l'entraîniez.",
    fromCoach: "{{name}} aimerait vous entraîner.",
  },
  planAdded: { title: "Nouvelle séance planifiée", body: "{{author}} a planifié « {{title}} » le {{date}}." },
  channels: { in_app: "Dans l'app", push: "Push", email: "Courriel" },
  kinds: {
    new_pr: { label: "Nouveaux records", hint: "Quand une synchronisation apporte un meilleur temps." },
    comment: { label: "Commentaires", hint: "Quelqu'un écrit dans un fil de vos séances." },
    coach_request: { label: "Demandes d'entraînement", hint: "Un entraîneur ou un athlète demande à se lier à vous." },
    plan_added: { label: "Séances planifiées", hint: "Quelqu'un ajoute une séance à votre calendrier." },
    sync_failed: { label: "Problèmes de synchronisation", hint: "Un transpondeur ne se synchronise pas. Envoyé une fois par série d'échecs." },
  },
  settings: {
    title: "Notifications",
    description: "Choisissez ce dont vous voulez être informé et où. La cloche est toujours dans l'app ; le push et le courriel doivent être configurés sur le serveur.",
    event: "Événement",
    notSetUp: "(non configuré)",
  },
  push: {
    title: "Push sur cet appareil",
    description: "Recevez une notification sur ce téléphone ou cet ordinateur même quand ApexCycling n'est pas ouvert. Chaque appareil s'active séparément.",
    enable: "Activer sur cet appareil",
    disable: "Désactiver sur cet appareil",
    on: "Cet appareil reçoit les notifications push.",
    serverOff: "Le push n'est pas encore configuré sur ce serveur.",
    unsupported: "Ce navigateur ne peut pas recevoir de notifications push. Sur iPhone, ajoutez d'abord ApexCycling à l'écran d'accueil.",
    blocked: "Les notifications sont bloquées pour ce site. Autorisez-les dans les réglages du site de votre navigateur, puis revenez.",
    failed: "Impossible de changer le push sur cet appareil.",
  },
} satisfies LocaleNamespace<typeof en>;
