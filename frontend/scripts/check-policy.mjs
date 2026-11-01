import { readFile, readdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
export function checkPolicy({
  policy,
  css,
  blueprint,
  manifest,
  dependencies,
  headers,
}) {
  const errors = [];
  const normalize = (v) =>
    v.length === 4
      ? '#' + [...v.slice(1)].map((c) => c + c).join('')
      : v.toLowerCase();
  for (const [key, value] of Object.entries(policy.tokens)) {
    const actual = css.match(
      new RegExp('--' + key + ':\\s*(#[0-9a-fA-F]+)'),
    )?.[1];
    if (!actual || normalize(actual) !== value || !blueprint.includes(value))
      errors.push('Design token drift: ' + key);
  }
  for (const name of policy.requiredScripts)
    if (!manifest.scripts?.[name])
      errors.push('Required script missing: ' + name);
  if (
    Object.keys(dependencies).some((d) =>
      /^(?:@supabase\/|@prisma\/|prisma$|pg$|postgres$|drizzle-orm|kysely|typeorm|mysql|mongodb|better-sqlite3|sql.js)/.test(
        d,
      ),
    )
  )
    errors.push('Direct database dependency forbidden');
  if (/https?:\/\//.test(css))
    errors.push('External stylesheet asset forbidden');
  for (const rule of [
    "object-src 'none'",
    "frame-ancestors 'none'",
    "base-uri 'none'",
    'Cache-Control: no-store',
  ])
    if (!headers.includes(rule))
      errors.push('Security response header missing: ' + rule);
  if (headers.includes("'unsafe-eval'") || headers.includes("'unsafe-inline'"))
    errors.push('Unsafe CSP permission');
  return errors;
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const root = new URL('../', import.meta.url);
  const read = (path) => readFile(new URL(path, root), 'utf8');
  const manifest = JSON.parse(await read('package.json'));
  const policy = JSON.parse(await read('scripts/m3-policy.json'));
  const errors = checkPolicy({
    policy,
    manifest,
    dependencies: { ...manifest.dependencies, ...manifest.devDependencies },
    css: await read('src/app/theme.css'),
    blueprint: await read('BLUEPRINT.md'),
    headers: await read('security-headers.conf'),
  });
  for (const file of [
    'README.md',
    'DESIGN.md',
    'UX-CONTRACT.md',
    'AGENTS.md',
  ]) {
    const text = await read(file);
    if (!text.includes('BLUEPRINT.md') || text.split('\n').length > 10)
      errors.push('Competing UI guidance: ' + file);
  }
  const config = JSON.parse(await read('premium-ui.json'));
  if (config.canonicalMap !== 'BLUEPRINT.md')
    errors.push('Audit map must use blueprint');
  if (
    (await readdir(new URL('src', root))).some(
      (x) => !['app', 'features', 'shared'].includes(x),
    )
  )
    errors.push('Unowned source layer');
  if (errors.length) {
    console.error(errors.join('\n'));
    process.exitCode = 1;
  } else
    console.log('M3 contract, design, database and security policy passed');
}
