import { expect, it } from 'vitest';
import { pageSpaceLabel } from './pageSpaces';
it('keeps printed, PDF and bundle page spaces distinct without offset inference', () => {
  const spaces = {
    pdf: { state: 'mapped', value: 6 },
    printed: { state: 'mapped', value: '4' },
    bundle: { state: 'conflicting', value: null },
  };
  expect(pageSpaceLabel(spaces, 'printed', 6)).toBe('4');
  expect(pageSpaceLabel(spaces, 'bundle', 6)).toBe('Conflicting labels');
  expect(pageSpaceLabel(spaces, 'printed', 1)).toBe('Not assessed');
  expect(pageSpaceLabel(spaces, 'printed', null)).toBe('Not assessed');
});
it('does not guess from missing, malformed or contradictory metadata', () => {
  expect(pageSpaceLabel(undefined, 'printed', 6)).toBe('Not supplied');
  for (const value of ['<script>private</script>', 4, -1, '1'.repeat(7), null])
    expect(
      pageSpaceLabel(
        {
          pdf: { state: 'mapped', value: 6 },
          printed: { state: 'mapped', value },
        },
        'printed',
        6,
      ),
    ).toBe('Not assessed');
  expect(
    pageSpaceLabel(
      {
        pdf: { state: 'mapped', value: 6 },
        bundle: { state: 'unmapped', value: null },
      },
      'bundle',
      6,
    ),
  ).toBe('Unmapped');
});
