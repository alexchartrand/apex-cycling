import type { LocaleNamespace } from "../types";
import type en from "../en/auth";

export default {
  layout: {
    tagline: "Chaque tour. Chaque intermédiaire. Chaque record.",
    features: {
      sqorz: "Vos tours de transpondeur sqorz, importés automatiquement",
      records: "Vos records au 200 m lancé, au kilo et en poursuite, suivis pour vous",
      tools: "Outils de CdA, de braquet et de tableau de marche pensés pour la piste",
    },
  },
  login: {
    title: "Connexion",
    subtitle: "Content de vous revoir sur la piste.",
    email: "Courriel",
    password: "Mot de passe",
    rememberMe: "Rester connecté",
    submit: "Se connecter",
    submitting: "Connexion…",
    noAccount: "Pas de compte?",
    signupLink: "Créer un compte",
    errors: {
      invalidCredentials: "Courriel ou mot de passe incorrect.",
      tooManyAttempts: "Trop de tentatives. Attendez une minute et réessayez.",
    },
  },
  signup: {
    title: "Créer votre compte",
    subtitle: "Aucun club ni invitation requis — importez vos tours sqorz dès maintenant.",
    displayName: "Nom affiché",
    email: "Courriel",
    password: "Mot de passe",
    confirmPassword: "Confirmer le mot de passe",
    submit: "Créer le compte",
    submitting: "Création du compte…",
    haveAccount: "Vous avez déjà un compte?",
    loginLink: "Se connecter",
    passwordNeeds: "Le mot de passe doit contenir :",
    mismatch: "Les mots de passe ne correspondent pas.",
    errors: {
      emailTaken: "Un compte existe déjà avec ce courriel.",
      tooManyAttempts: "Trop de tentatives d'inscription. Attendez une minute et réessayez.",
    },
  },
  passwordRules: {
    length: "Au moins {{count}} caractères",
    classes: "Au moins {{count}} parmi : minuscule, majuscule, chiffre, symbole",
  },
  logout: "Se déconnecter",
} satisfies LocaleNamespace<typeof en>;
