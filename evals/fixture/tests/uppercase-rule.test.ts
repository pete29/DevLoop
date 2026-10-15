import { describe, it, expect } from 'vitest';
import { UppercaseRule } from '../src/uppercase-rule';

describe('UppercaseRule', () => {
  const expectedMessage = "Hasło musi zawierać co najmniej jedną wielką literę";

  it('returns null when the password contains an uppercase letter (including Polish characters)', () => {
    const rule = new UppercaseRule();

    expect(rule.check('abcDef')).toBeNull();
    expect(rule.check('A')).toBeNull();
    expect(rule.check('abcŁ')).toBeNull();
    expect(rule.check('123!Z')).toBeNull();
  });

  it('returns the error message when the password has no uppercase letters', () => {
    const rule = new UppercaseRule();

    expect(rule.check('abcdef')).toBe(expectedMessage);
    expect(rule.check('zażółć')).toBe(expectedMessage);
  });

  it('returns the error message for empty, digit-only and symbol-only passwords', () => {
    const rule = new UppercaseRule();

    expect(rule.check('')).toBe(expectedMessage);
    expect(rule.check('1234567890')).toBe(expectedMessage);
    expect(rule.check('!@# $%^&*')).toBe(expectedMessage);
  });
});