import capacity from './capacity-policy.json';
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


it('shares conservative intake and export caps from the generated Python policy', () => {
  expect(capacity.schema).toBe('caseproof-capacity-envelope-v1');
  expect(capacity.approval).toBe('development_only_not_pilot_approved');
  expect(capacity.source_count).toBe(4);
  expect(capacity.max_source_bytes).toBe(5_242_880);
  expect(capacity.max_intake_bytes).toBe(12_000_000);
  expect(capacity.max_inventory_bytes).toBe(1_048_576);
  expect(capacity.max_pdf_pages_per_source).toBe(64);
  expect(capacity.max_export_json_bytes).toBe(2_000_000);
  expect(capacity.max_export_markdown_bytes).toBe(2_000_000);
  expect(capacity.max_export_docx_bytes).toBe(5_242_880);
});
