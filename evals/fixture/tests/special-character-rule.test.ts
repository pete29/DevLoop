import { describe, it, expect } from 'vitest';
import { SpecialCharacterRule } from '../src/special-character-rule';

describe('SpecialCharacterRule', () => {
  const expectedMessage = 'Hasło musi zawierać co najmniej jeden znak specjalny';

  it('returns null when the password contains an ASCII special character or whitespace', () => {
    const rule = new SpecialCharacterRule();

    expect(rule.check('abc123!')).toBeNull();
    expect(rule.check('abc#')).toBeNull();
    expect(rule.check('abc def')).toBeNull();
    expect(rule.check('_')).toBeNull();
  });

  it('returns the error message when the password has only letters and digits, including Polish letters', () => {
    const rule = new SpecialCharacterRule();

    expect(rule.check('Abc12345')).toBe(expectedMessage);
    expect(rule.check('zażółćGęśląJaźń123')).toBe(expectedMessage);
    expect(rule.check('')).toBe(expectedMessage);
  });

  it('treats non-ASCII symbols as special and is stateless across repeated calls', () => {
    const rule = new SpecialCharacterRule();

    expect(rule.check('abc€')).toBeNull();
    expect(rule.check('abc€')).toBeNull();
    expect(rule.check('abc')).toBe(expectedMessage);
    expect(rule.check('abc')).toBe(expectedMessage);
  });
});