import type { PasswordRule } from "./password-rule";

export class MinLengthRule implements PasswordRule {
  readonly name = "min-length";

  private readonly minLength = 8;

  validate(password: string): string | null {
    if (password.length < this.minLength) {
      return `Hasło musi mieć co najmniej ${this.minLength} znaków.`;
    }
    return null;
  }

  check(password: string): string | null {
    return this.validate(password);
  }
}