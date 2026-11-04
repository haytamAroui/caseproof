import { expect, it } from 'vitest';
import { boundedRedline } from './boundedRedline';
it('preserves exact before and after strings, including Unicode and disjoint edits', () => {
  for (const [before, after] of [
    ['Stuk 1, p. 4', 'Stuk 2, p. 6'],
    ['😀é', '😀é'],
    ['', 'new'],
    ['old', ''],
    ['same', 'same'],
  ]) {
    const result = boundedRedline(before!, after!);
    expect(result.prefix + result.removed + result.suffix).toBe(before);
    expect(result.prefix + result.added + result.suffix).toBe(after);
  }
});
