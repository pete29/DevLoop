import type { PasswordRule } from './password-rule';

/**
 * Reguła wymagająca co najmniej jednego znaku specjalnego,
 * czyli znaku, który nie jest ani literą, ani cyfrą.
 */
export class SpecialCharacterRule implements PasswordRule {
  private static readonly SPECIAL_CHARACTER_PATTERN = /[^\p{L}\p{N}]/u;

  private readonly message = 'Hasło musi zawierać co najmniej jeden znak specjalny';

  check(password: string): string | null {
    return SpecialCharacterRule.SPECIAL_CHARACTER_PATTERN.test(password)
      ? null
      : this.message;
  }
}