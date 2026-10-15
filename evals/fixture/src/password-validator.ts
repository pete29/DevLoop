import type { PasswordRule } from "./password-rule";

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

export class PasswordValidator {
  private readonly rules: readonly PasswordRule[];

  constructor(rules: PasswordRule[]) {
    this.rules = [...rules];
  }

  validate(password: string): ValidationResult {
    const errors: string[] = [];

    for (const rule of this.rules) {
      const message = rule.check(password);
      if (message !== null) {
        errors.push(message);
      }
    }

    return {
      valid: errors.length === 0,
      errors,
    };
  }
}