import { it, expect } from 'vitest';
import { checkPolicy } from './check-policy.mjs';
import { violations } from './check-boundaries.mjs';
const good = {
  policy: { tokens: { accent: '#103a4b' }, requiredScripts: ['build'] },
  css: ':root{--accent:#103a4b}',
  blueprint: '#103a4b',
  manifest: { scripts: { build: 'vite build' } },
  dependencies: { react: '19' },
  headers:
    "object-src 'none'; frame-ancestors 'none'; base-uri 'none'; Cache-Control: no-store",
};
it('accepts consistent contracts', () => expect(checkPolicy(good)).toEqual([]));
it.each([
  { css: ':root{--accent:#ffffff}' },
  { blueprint: 'stale' },
  { manifest: { scripts: {} } },
  { dependencies: { '@supabase/supabase-js': 'latest' } },
  { css: '@import url(https://outside.test/a.css)' },
  { headers: "script-src 'unsafe-eval'" },
])('rejects policy drift %o', (change) =>
  expect(checkPolicy({ ...good, ...change }).length).toBeGreaterThan(0),
);
it.each([
  "import {x} from '@supabase/supabase-js';",
  "import {x} from 'pg';",
  "window['fetch']('/private');",
  'const x=<div dangerouslySetInnerHTML={{__html: source}}/>;',
  "const x=<div style={{color:'green'}}/>;",
])('rejects shortcut %s', (code) =>
  expect(
    violations('/src/features/review/Bad.tsx', code, '/src').length,
  ).toBeGreaterThan(0),
);
