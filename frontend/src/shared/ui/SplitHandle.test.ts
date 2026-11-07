import { describe, expect, it } from 'vitest';
import { clampSplit } from './SplitHandle';

describe('CaseProof reading-panel bounds', () => {
  it('never permits panels outside the accessible resizing envelope', () => {
    expect(clampSplit(120, 240, 420)).toBe(240);
    expect(clampSplit(777, 240, 420)).toBe(420);
    expect(clampSplit(349.6, 240, 420)).toBe(350);
    expect(clampSplit(62.8, 30, 70)).toBe(63);
    expect(clampSplit(Number.NaN, 30, 70)).toBe(30);
  });
});
