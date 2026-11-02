import { describe, expect, it } from 'vitest';
import { recoveryDestination } from './recovery';
const matter = '/matters/11111111-1111-4111-8111-111111111111';
const report = `${matter}/briefs/22222222-2222-4222-8222-222222222222`;
describe('private session recovery navigation', () => {
  it('retains only a read-only matter/report binding', () => {
    expect(recoveryDestination(matter, '?title=private')).toBe(matter);
    expect(
      recoveryDestination(
        report,
        `?snapshot=${'a'.repeat(64)}&token=private&finding=private`,
      ),
    ).toBe(`${report}?snapshot=${'a'.repeat(64)}`);
  });
  it.each([
    '//outside.test',
    'https://outside.test',
    '/matters/new',
    `${matter}/sources`,
    `${matter}/inventory`,
    '/reports/open',
    '/matters/not-a-uuid',
  ])('discards unsupported destination %s', (path) => {
    expect(recoveryDestination(path, '?operation=private')).toBeNull();
  });
  it.each(['', '?snapshot=private', `?snapshot=${'a'.repeat(65)}`])(
    'discards invalid report binding %s',
    (search) => {
      expect(recoveryDestination(report, search)).toBeNull();
    },
  );
});
