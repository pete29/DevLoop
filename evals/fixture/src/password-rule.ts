/**
 * Kontrakt reguły walidacji hasła.
 *
 * Każda reguła implementuje metodę `check`, która zwraca:
 * - komunikat błędu (string), gdy hasło NIE spełnia reguły,
 * - `null`, gdy hasło spełnia regułę.
 *
 * Dzięki temu walidator może przyjmować dowolne nowe reguły
 * bez konieczności modyfikowania jego kodu.
 */
export interface PasswordRule {
  check(password: string): string | null;
}