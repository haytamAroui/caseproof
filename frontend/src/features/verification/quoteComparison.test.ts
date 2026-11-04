import { describe, expect, it } from 'vitest';
import { quoteMatches } from './quoteComparison';

describe('bounded literal navigation', () => {
  it('retains exact occurrences and all original characters', () => {
    const result = quoteMatches('A €1 and A €1', 'A €1');
    expect(result.occurrences).toBe(2);
    expect(result.segments.map((segment) => segment.text).join('')).toBe(
      'A €1 and A €1',
    );
    expect(result.segments.filter((segment) => segment.matched)).toHaveLength(
      2,
    );
    expect(quoteMatches('A €1', 'A €2').occurrences).toBe(0);
  });
  it('counts overlapping occurrences without duplicating characters', () => {
    const result = quoteMatches('aaaa', 'aaa');
    expect(result.occurrences).toBe(2);
    expect(result.segments).toEqual([{ text: 'aaaa', matched: true }]);
    expect(quoteMatches('é', 'e\u0301').occurrences).toBe(0);
    expect(quoteMatches('text', '').occurrences).toBe(0);
  });
});
