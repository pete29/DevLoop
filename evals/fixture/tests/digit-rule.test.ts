import { describe, it, expect } from 'vitest';
import { DigitRule } from '../src/digit-rule';

describe('DigitRule', () => {
  it('returns null when the password contains at least one digit', () => {
    const rule = new DigitRule();

    expect(rule.check('abc1def')).toBeNull();
    expect(rule.check('0')).toBeNull();
    expect(rule.check('9abc')).toBeNull();
  });

  it('returns the default message when the password has no digits', () => {
    const rule = new DigitRule();
    const expected = 'Hasło musi zawierać co najmniej jedną cyfrę.';

    expect(rule.check('abcdef')).toBe(expected);
    expect(rule.check('')).toBe(expected);
    expect(rule.check('!@#$ ęółż')).toBe(expected);
  });

  it('returns a custom message when provided to the constructor', () => {
    const rule = new DigitRule('Need a digit');

    expect(rule.check('nodigits')).toBe('Need a digit');
    expect(rule.check('with5digit')).toBeNull();
  });
});