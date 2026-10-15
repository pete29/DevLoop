import type { PasswordRule } from "./password-rule";

export class DigitRule implements PasswordRule {
  private static readonly DIGIT_PATTERN = /[0-9]/;

  private readonly message: string;

  constructor(message: string = "Hasło musi zawierać co najmniej jedną cyfrę.") {
    this.message = message;
  }

  check(password: string): string | null {
    return DigitRule.DIGIT_PATTERN.test(password) ? null : this.message;
  }
}