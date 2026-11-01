import { expect, it } from 'vitest';
import { projectBox } from './geometry';
it('projects all four corners through origin, rotation, scale and UserUnit', () => {
  expect(projectBox([0, 2, 2, 0, -300, -200], [140, 200, 260, 240])).toEqual([
    100, 80, 180, 320,
  ]);
  expect(projectBox([2.5, 0, 0, -2.5, 0, 2000], [140, 200, 260, 240])).toEqual([
    350, 1400, 650, 1500,
  ]);
  expect(projectBox([-2, 0, 0, 2, 1200, 0], [140, 200, 260, 240])).toEqual([
    680, 400, 920, 480,
  ]);
});
it('rejects missing, nonfinite and singular coordinate transforms', () => {
  for (const transform of [[], [0, 0, 0, 0, 0, 0], [1, 0, 0, 1, NaN, 0]])
    expect(() => projectBox(transform, [1, 2, 3, 4])).toThrow();
});
