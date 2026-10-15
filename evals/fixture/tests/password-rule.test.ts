import { describe, it, expect, vi } from 'vitest';
import type { PasswordRule } from '../src/password-rule';

describe('PasswordRule contract', () => {
  it('returns an error message string when the password does not satisfy the rule', () => {
    const minLengthRule: PasswordRule = {
      check(password: string) {
        return password.length >= 8 ? null : 'Hasło jest za krótkie';
      },
    };

    const result = minLengthRule.check('abc');

    expect(result).toBe('Hasło jest za krótkie');
    expect(typeof result).toBe('string');
  });

  it('returns null when the password satisfies the rule', () => {
    const minLengthRule: PasswordRule = {
      check(password: string) {
        return password.length >= 8 ? null : 'Hasło jest za krótkie';
      },
    };

    expect(minLengthRule.check('dlugiehaslo123')).toBeNull();
  });

  it('can be implemented by a mock and is called with the given password', () => {
    const checkMock: ReturnType<typeof vi.fn> = vi.fn().mockReturnValue(null);
    const rule: PasswordRule = { check: checkMock as unknown as PasswordRule['check'] };

    const result = rule.check('Secret123!');

    expect(checkMock).toHaveBeenCalledTimes(1);
    expect(checkMock).toHaveBeenCalledWith('Secret123!');
    expect(result).toBeNull();
  });
});