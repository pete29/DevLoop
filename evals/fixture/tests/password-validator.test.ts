import { describe, it, expect, vi } from 'vitest';
import { PasswordValidator } from '../src/password-validator';

type Rule = { check: (password: string) => string | null };

describe('PasswordValidator', () => {
  it('returns valid with no errors when every rule passes, or when there are no rules', () => {
    const check = vi.fn().mockReturnValue(null);
    const validator = new PasswordValidator([{ check }] as any);

    expect(validator.validate('abc')).toEqual({ valid: true, errors: [] });
    expect(check).toHaveBeenCalledWith('abc');
    expect(new PasswordValidator([]).validate('x')).toEqual({ valid: true, errors: [] });
  });

  it('collects error messages from failing rules in order and skips passing rules', () => {
    const rules: Rule[] = [
      { check: vi.fn().mockReturnValue('too short') },
      { check: vi.fn().mockReturnValue(null) },
      { check: vi.fn().mockReturnValue('needs digit') },
    ];
    const validator = new PasswordValidator(rules as any);

    const result = validator.validate('pw');

    expect(result.valid).toBe(false);
    expect(result.errors).toEqual(['too short', 'needs digit']);
    for (const rule of rules) {
      expect(rule.check).toHaveBeenCalledTimes(1);
      expect(rule.check).toHaveBeenCalledWith('pw');
    }
  });

  it('copies the rules array at construction so later mutation does not affect it', () => {
    const rules: Rule[] = [{ check: vi.fn().mockReturnValue('bad') }];
    const validator = new PasswordValidator(rules as any);

    rules.push({ check: vi.fn().mockReturnValue('another') });
    rules.length = 0;

    expect(validator.validate('x').errors).toEqual(['bad']);
  });
});