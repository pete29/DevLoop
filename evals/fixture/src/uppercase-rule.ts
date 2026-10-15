import type { PasswordRule } from "./password-rule";

/**
 * Reguła wymagająca co najmniej jednej wielkiej litery w haśle.
 *
 * Zwraca komunikat błędu, gdy hasło nie zawiera żadnej wielkiej litery,
 * a w przeciwnym razie `null`.
 */
export class UppercaseRule implements PasswordRule {
  private readonly message = "Hasło musi zawierać co najmniej jedną wielką literę";

  check(password: string): string | null {
    for (let i = 0; i < password.length; i++) {
      const char = password.charAt(i);
      if (char !== char.toLowerCase() && char === char.toUpperCase()) {
        return null;
      }
    }
    return this.message;
  }
}