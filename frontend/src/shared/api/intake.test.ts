import { expect, it } from 'vitest';
import { parseIntake, parseCreated, parseOrganizations } from './intake';
const id = '11111111-1111-4111-8111-111111111111';
it('rejects foreign, nil, duplicate and unknown intake contracts', () => {
  const empty = {
    schema: 'caseproof-workspace-intake-v1',
    case_id: id,
    sources: [],
    entries: [],
    readback_complete: false,
    inventory_complete: false,
  };
  expect(parseIntake(empty, id).readback_complete).toBe(false);
  expect(() =>
    parseIntake(
      { ...empty, case_id: '22222222-2222-4222-8222-222222222222' },
      id,
    ),
  ).toThrow();
  expect(() =>
    parseIntake({ ...empty, readback_complete: true }, id),
  ).toThrow();
  expect(() => parseIntake({ ...empty, schema: 'future' }, id)).toThrow();
  expect(() =>
    parseCreated(
      { schema: 'caseproof-workspace-created-v1', case_id: id, request_id: id },
      'other',
    ),
  ).toThrow();
  expect(() =>
    parseOrganizations({
      schema: 'caseproof-workspace-create-orgs-v1',
      organizations: [
        { org_id: id, name: 'Synthetic' },
        { org_id: id, name: 'Duplicate' },
      ],
    }),
  ).toThrow();
});
