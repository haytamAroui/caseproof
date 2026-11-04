// npm's audit JSON contains advisory metadata only. Never auto-waive.
import fs from 'node:fs';
function read(path) {
  let value;
  try {
    value = JSON.parse(fs.readFileSync(path, 'utf8'));
  } catch {
    throw Error('npm audit output missing or invalid');
  }
  if (
    !value ||
    typeof value !== 'object' ||
    !value.metadata?.vulnerabilities ||
    !value.vulnerabilities ||
    typeof value.vulnerabilities !== 'object'
  )
    throw Error('npm registry audit did not return actionable metadata');
  return value;
}
if (process.argv.length !== 4) throw Error('two audit paths required');
const all = read(process.argv[2]),
  prod = read(process.argv[3]);
function project(data) {
  const summary = data.metadata.vulnerabilities;
  const rows = Object.entries(data.vulnerabilities)
    .map(([name, v]) => ({
      package: name,
      severity: v.severity,
      direct: Boolean(v.isDirect),
      fix_available:
        v.fixAvailable === false ? 'none' : 'review_version_change',
    }))
    .sort((a, b) => a.package.localeCompare(b.package));
  return {
    counts: {
      low: summary.low || 0,
      moderate: summary.moderate || 0,
      high: summary.high || 0,
      critical: summary.critical || 0,
    },
    affected: rows,
  };
}
const full = project(all),
  production = project(prod);
console.log(
  'P6_NPM_AUDIT_SANITIZED',
  JSON.stringify({
    all: full,
    production,
    reported_scope: 'npm_registry_advisories_not_manual_security_review',
  }),
);
if (
  production.counts.moderate ||
  production.counts.high ||
  production.counts.critical
)
  throw Error(
    'Known production vulnerability requires remediation or documented exception',
  );
if (full.counts.high || full.counts.critical)
  throw Error('High/critical dev vulnerability requires remediation');
console.log('P6_PRODUCTION_DEPENDENCY_ADVISORY_GATE_PASSED');
if (full.counts.moderate)
  console.log('P6_DEV_MODERATE_ADVISORIES_REMAIN_FOR_INDEPENDENT_TRIAGE');
