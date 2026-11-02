import { describe, expect, it } from 'vitest';
import validateDossier from './generated-validator.js';
import validateViewer from './viewer-generated-validator.js';
import validateConfirmation from './confirmation-generated-validator.js';
import type { DossierView, FindingView } from './generated';

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
    expect(validateDossier({ ...dossier, future_extension: { version: 2 },
      findings: [{ ...finding, future_detail: 'allowed' }] })).toBe(true);
  });

  it('rejects missing required fields, invalid enum states and malformed references', () => {
    const { snapshot_hash: _unused, ...missing } = dossier;
    expect(validateDossier(missing)).toBe(false);
    expect(validateDossier({ ...dossier, findings: [{ ...finding, identity: 'verified' }] })).toBe(false);
    expect(validateDossier({ ...dossier, findings: [{ ...finding, reference_id: '' }] })).toBe(false);
  });

  it('validates viewer page constraints and rejects unknown fields', () => {
    const viewer = {
      schema: 'caseproof-viewer-v1', case_id: 'case', brief_id: 'brief',
      snapshot_hash: 'a'.repeat(64), reference_id: 'r1', version_id: 'v1',
      original_sha256: 'b'.repeat(64), byte_length: 100,
      page_mapping: 'mapped', pdf_page: 1, legacy_region_count: 0,
      geometry_policy: 'derived_pdf_text_only_legacy_raster_not_projected',
    };
    expect(validateViewer(viewer)).toBe(true);
    expect(validateViewer({ ...viewer, pdf_page: 0 })).toBe(false);
    expect(validateViewer({ ...viewer, unexpected: true })).toBe(false);
  });

  it('rejects unknown fields on the inventory confirmation contract', () => {
    expect(validateConfirmation({ bundle_signature: 'a'.repeat(64), unexpected: true })).toBe(false);
  });
});

function supportsFinding(f: FindingView): boolean {
  switch (f.support) {
    case 'supported': return true;
    case 'qualified':
    case 'contradicted':
    case 'not_assessed': return false;
    default: {
      const exhaustive: never = f.support;
      return exhaustive;
    }
  }
}
it('generated TypeScript support union is exhaustive', () => {
  expect(supportsFinding(finding)).toBe(true);
});
