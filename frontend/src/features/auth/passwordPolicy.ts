// Keep in sync with backend/app/auth/schemas.py's SignupRequest password validator.
export const MIN_PASSWORD_LENGTH = 12;
export const MIN_CHARACTER_CLASSES = 3;

const CLASS_PATTERNS = [/[a-z]/, /[A-Z]/, /\d/, /[^a-zA-Z0-9]/];

export function passwordStrengthErrors(password: string): string[] {
  const errors: string[] = [];
  if (password.length < MIN_PASSWORD_LENGTH) {
    errors.push(`At least ${MIN_PASSWORD_LENGTH} characters`);
  }
  const classes = CLASS_PATTERNS.filter((pattern) => pattern.test(password)).length;
  if (classes < MIN_CHARACTER_CLASSES) {
    errors.push(`At least ${MIN_CHARACTER_CLASSES} of: lowercase, uppercase, digit, symbol`);
  }
  return errors;
}

export function isPasswordStrong(password: string): boolean {
  return passwordStrengthErrors(password).length === 0;
}
