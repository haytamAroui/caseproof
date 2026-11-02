import { describe, expect, it } from 'vitest';
import validateDossier from './generated-validator.js';
import validateViewer from './viewer-generated-validator.js';
import validateConfirmation from './confirmation-generated-validator.js';
import type { DossierView, FindingView } from './generated';
import { parseDossier } from './contracts';
import { assertConfirmationCommand } from './intake';

const finding: FindingView = {
  reference_id: 'r1',
  literal: 'Stuk 1',
  identity: 'resolved',
  page_mapping: 'mapped',
  fidelity: 'exact_match',
  support: 'supported',
};

const dossier: DossierView = {
  schema: 'caseproof-dossier-v1',
  case_id: 'case',
  brief_id: 'brief',
  snapshot_hash: 'a'.repeat(64),
  findings: [finding],
  coverage: {},
};

describe('Python-generated JSON Schema and AJV contract boundary', () => {
  it('accepts a valid dossier and its forward-compatible extensions', () => {
    expect(validateDossier(dossier)).toBe(true);
    expect(
      validateDossier({
        ...dossier,
        future_extension: { version: 2 },
        findings: [{ ...finding, future_detail: 'allowed' }],
      }),
    ).toBe(true);
  });

  it('rejects missing required fields, invalid enum states and malformed references', () => {
    const missing: Record<string, unknown> = { ...dossier };
    delete missing.snapshot_hash;
    expect(validateDossier(missing)).toBe(false);
    expect(
      validateDossier({
        ...dossier,
        findings: [{ ...finding, identity: 'verified' }],
      }),
    ).toBe(false);
    expect(
      validateDossier({
        ...dossier,
        findings: [{ ...finding, reference_id: '' }],
      }),
    ).toBe(false);
  });

  it('validates viewer page constraints and rejects unknown fields', () => {
    const viewer = {
      schema: 'caseproof-viewer-v1',
      case_id: 'case',
      brief_id: 'brief',
      snapshot_hash: 'a'.repeat(64),
      reference_id: 'r1',
      version_id: 'v1',
      original_sha256: 'b'.repeat(64),
      byte_length: 100,
      page_mapping: 'mapped',
      pdf_page: 1,
      legacy_region_count: 0,
      geometry_policy: 'derived_pdf_text_only_legacy_raster_not_projected',
    };
    expect(validateViewer(viewer)).toBe(true);
    expect(validateViewer({ ...viewer, pdf_page: 0 })).toBe(false);
    expect(validateViewer({ ...viewer, unexpected: true })).toBe(false);
  });

  it('rejects unknown fields on the inventory confirmation contract', () => {
    expect(
      validateConfirmation({
        bundle_signature: 'a'.repeat(64),
        unexpected: true,
      }),
    ).toBe(false);
  });
});

function supportsFinding(f: FindingView): boolean {
  switch (f.support) {
    case 'supported':
      return true;
    case 'qualified':
    case 'contradicted':
    case 'not_assessed':
      return false;
    default: {
      const exhaustive: never = f.support;
      return exhaustive;
    }
  }
}

it('generated TypeScript support union is exhaustive', () => {
  expect(supportsFinding(finding)).toBe(true);
});

it('refuses contradictory supplied page spaces without inventing physical pages', () => {
  const page_spaces = {
    pdf: { state: 'mapped', value: 6 },
    printed: { state: 'mapped', value: '4' },
    bundle: { state: 'unmapped', value: null },
  };
  expect(
    parseDossier({ ...dossier, findings: [{ ...finding, page_spaces }] })
      .findings,
  ).toHaveLength(1);
  for (const mutated of [
    { ...page_spaces, pdf: { state: 'mapped', value: null } },
    { ...page_spaces, pdf: { state: 'mapped', value: true } },
    { ...page_spaces, printed: { state: 'conflicting', value: '4' } },
    { ...page_spaces, printed: { state: 'mapped', value: 'p4' } },
    { ...page_spaces, bundle: { state: 'mapped', value: 12 } },
    { ...page_spaces, future: {} },
  ])
    expect(() =>
      parseDossier({
        ...dossier,
        findings: [{ ...finding, page_spaces: mutated }],
      }),
    ).toThrow();
  expect(() =>
    parseDossier({
      ...dossier,
      findings: [{ ...finding, page_mapping: 'unmapped', page_spaces }],
    }),
  ).toThrow();
});

it('enforces generated Roman page labels and versioned inventory exceptions at the AJV boundary', () => {
  const original = {
    bundle_signature: 'a'.repeat(64),
    request_id: '11111111-1111-4111-8111-111111111111',
    inventory_complete: false,
    entries: [
      {
        label: 'stuk',
        number: '1',
        source_version_id: null,
        pages: [
          {
            space: 'printed',
            label: 'iv',
            pdf_page: 6,
            rationale: 'Inspected page six',
          },
        ],
      },
    ],
    exceptions: [
      {
        version: 1,
        kind: 'detector_miss',
        citation: 'Annex 9',
        rationale: 'Human inspection required',
        review_state: 'review_needed',
      },
    ],
  };
  expect(validateConfirmation(original)).toBe(true);
  expect(assertConfirmationCommand(original)).toEqual(original);
  expect(validateConfirmation({ ...original, inventory_complete: true })).toBe(
    false,
  );
  expect(
    validateConfirmation({
      ...original,
      entries: [
        {
          ...original.entries[0],
          pages: [{ ...original.entries[0].pages[0], label: 'IC' }],
        },
      ],
    }),
  ).toBe(false);
  expect(
    validateConfirmation({
      ...original,
      exceptions: [{ ...original.exceptions[0], version: 2 }],
    }),
  ).toBe(false);
  expect(
    validateConfirmation({
      ...original,
      exceptions: [{ ...original.exceptions[0], review_state: 'verified' }],
    }),
  ).toBe(false);
  expect(() =>
    assertConfirmationCommand({
      ...original,
      exceptions: [
        original.exceptions[0],
        { ...original.exceptions[0], rationale: 'Other reviewer note' },
      ],
    }),
  ).toThrow();
  const mapped = {
    pdf: { state: 'mapped', value: 6 },
    printed: { state: 'mapped', value: 'iv' },
    bundle: { state: 'unmapped', value: null },
  };
  expect(
    parseDossier({
      ...dossier,
      findings: [{ ...finding, page_spaces: mapped }],
    }).findings,
  ).toHaveLength(1);
  for (const badLabel of ['IC', 'Iiv', '4a', 'Ⅳ', 'iv ', '1000000']) {
    expect(() =>
      parseDossier({
        ...dossier,
        findings: [
          {
            ...finding,
            page_spaces: {
              ...mapped,
              printed: { state: 'mapped', value: badLabel },
            },
          },
        ],
      }),
    ).toThrow();
  }
});
