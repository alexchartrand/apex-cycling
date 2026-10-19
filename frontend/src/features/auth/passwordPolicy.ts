// Keep in sync with backend/app/auth/schemas.py's SignupRequest password validator.
export const MIN_PASSWORD_LENGTH = 12;
export const MIN_CHARACTER_CLASSES = 3;

const CLASS_PATTERNS = [/[a-z]/, /[A-Z]/, /\d/, /[^a-zA-Z0-9]/];

export type PasswordRule = "length" | "classes";

/** The rules `password` fails, as codes the UI translates (see auth:passwordRules). */
export function failedPasswordRules(password: string): PasswordRule[] {
  const failed: PasswordRule[] = [];
  if (password.length < MIN_PASSWORD_LENGTH) failed.push("length");
  const classes = CLASS_PATTERNS.filter((pattern) => pattern.test(password)).length;
  if (classes < MIN_CHARACTER_CLASSES) failed.push("classes");
  return failed;
}

export function isPasswordStrong(password: string): boolean {
  return failedPasswordRules(password).length === 0;
}

export const PASSWORD_RULE_COUNTS: Record<PasswordRule, number> = {
  length: MIN_PASSWORD_LENGTH,
  classes: MIN_CHARACTER_CLASSES,
};

/** A strong new password that the confirmation field repeats exactly. */
export function isNewPasswordReady(password: string, confirmation: string): boolean {
  return isPasswordStrong(password) && password === confirmation;
}
