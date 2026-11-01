import ts from 'typescript';
import { readdir, readFile } from 'node:fs/promises';
import { dirname, resolve, relative, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
export function violations(path, code, root) {
  const rel = relative(root, path).replaceAll('\\', '/');
  const parts = rel.split('/');
  const layer = parts[0],
    feature = layer === 'features' ? parts[1] : undefined;
  const errors = [];
  const source = ts.createSourceFile(
    path,
    code,
    ts.ScriptTarget.Latest,
    true,
    extname(path) === '.tsx' ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const imports = [];
  function visit(node) {
    if (
      (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    )
      imports.push(node.moduleSpecifier.text);
    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword
    ) {
      const arg = node.arguments[0];
      if (!arg || !ts.isStringLiteral(arg))
        errors.push('computed imports forbidden');
      else imports.push(arg.text);
    }
    if (
      ts.isCallExpression(node) &&
      ts.isIdentifier(node.expression) &&
      ['fetch', 'eval', 'Function'].includes(node.expression.text) &&
      !(rel === 'shared/api/transport.ts' && node.expression.text === 'fetch')
    )
      errors.push('network/evaluation outside transport forbidden');
    if (
      ts.isIdentifier(node) &&
      ['localStorage', 'sessionStorage', 'indexedDB'].includes(node.text)
    )
      errors.push('persistent browser storage forbidden');
    if (
      ts.isPropertyAccessExpression(node) &&
      ['fetch', 'sendBeacon', 'XMLHttpRequest', 'WebSocket'].includes(
        node.name.text,
      )
    )
      errors.push('network shortcut forbidden');
    if (
      ts.isNewExpression(node) &&
      ts.isIdentifier(node.expression) &&
      ['Function', 'WebSocket', 'XMLHttpRequest'].includes(node.expression.text)
    )
      errors.push('evaluation/network constructor forbidden');
    if (
      ts.isJsxAttribute(node) &&
      ['dangerouslySetInnerHTML', 'style'].includes(node.name.getText(source))
    )
      errors.push('unsafe HTML or screen-local style bypass forbidden');
    if (
      ts.isPropertyAccessExpression(node) &&
      ['innerHTML', 'outerHTML', 'insertAdjacentHTML'].includes(node.name.text)
    )
      errors.push('raw HTML injection forbidden');
    if (
      ts.isElementAccessExpression(node) &&
      ts.isIdentifier(node.expression) &&
      ['window', 'globalThis', 'self'].includes(node.expression.text)
    ) {
      const key = node.argumentExpression;
      if (
        !key ||
        !ts.isStringLiteral(key) ||
        [
          'fetch',
          'localStorage',
          'sessionStorage',
          'indexedDB',
          'sendBeacon',
        ].includes(key.text)
      )
        errors.push('computed global or storage access forbidden');
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
  for (const spec of imports) {
    if (
      /^(?:@supabase\/|@prisma\/|prisma$|pg$|postgres$|drizzle-orm|kysely|typeorm|mysql|mongodb|better-sqlite3|sql.js)/.test(
        spec,
      )
    )
      errors.push('database access belongs to backend');
    if (!spec.startsWith('.')) {
      if (spec.startsWith('@/') || spec.startsWith('/'))
        errors.push('unresolved alias import');
      continue;
    }
    const target = relative(root, resolve(dirname(path), spec))
      .replaceAll('\\', '/')
      .split('/');
    if (target[0] === '..')
      errors.push('imports outside source root forbidden');
    if (layer === 'shared' && target[0] !== 'shared')
      errors.push('shared cannot import app/features');
    if (layer === 'features' && target[0] === 'app')
      errors.push('feature cannot import app');
    if (
      target[0] === 'features' &&
      (layer === 'app' || feature !== target[1]) &&
      target.length > 2 &&
      target[2] !== 'index'
    )
      errors.push('feature consumers must use public index');
    if (
      layer === 'features' &&
      target[0] === 'features' &&
      feature !== target[1]
    )
      errors.push('cross-feature orchestration belongs in app');
  }
  return errors.map((message) => `${rel}: ${message}`);
}
async function walk(dir) {
  const result = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = resolve(dir, entry.name);
    if (entry.isDirectory()) result.push(...(await walk(path)));
    else if (/\.tsx?$/.test(path) && !path.endsWith('.test.ts'))
      result.push(path);
  }
  return result;
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const root = fileURLToPath(new URL('../src', import.meta.url));
  const errors = [];
  for (const path of await walk(root))
    errors.push(...violations(path, await readFile(path, 'utf8'), root));
  if (errors.length) {
    console.error(errors.join('\n'));
    process.exitCode = 1;
  } else console.log('Frontend dependency and storage boundaries passed');
}
