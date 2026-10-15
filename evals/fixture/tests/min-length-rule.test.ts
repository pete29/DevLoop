import { describe, it, expect } from 'vitest';
import { MinLengthRule } from '../src/min-length-rule';

describe('MinLengthRule', () => {
  it('exposes the rule name "min-length"', () => {
    const rule = new MinLengthRule();
    expect(rule.name).toBe('min-length');
  });

  it('returns an error message for passwords shorter than 8 characters', () => {
    const rule = new MinLengthRule();
    const message = 'Hasło musi mieć co najmniej 8 znaków.';

    expect(rule.validate('')).toBe(message);
    expect(rule.validate('1234567')).toBe(message);
  });

  it('returns null for passwords of 8 or more characters and check delegates to validate', () => {
    const rule = new MinLengthRule();

    expect(rule.validate('12345678')).toBeNull();
    expect(rule.validate('a much longer password')).toBeNull();
    expect(rule.check('12345678')).toBeNull();
    expect(rule.check('short')).toBe(rule.validate('short'));
  });
});