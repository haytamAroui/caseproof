import { describe, it, expect } from 'vitest';
import { violations } from './check-boundaries.mjs';
describe('architecture negative controls', () => {
  it.each([
    ['shared/ui/x.ts', "import {x} from '../../features/review';"],
    ['features/evidence/x.ts', "import {x} from '../../app/query';"],
    ['app/x.ts', "import {x} from '../features/verification/api';"],
    ['features/evidence/x.ts', "fetch('/v2/private');"],
    ['shared/ui/x.ts', "window.localStorage.setItem('token','secret');"],
    ['app/x.ts', 'import(target);'],
  ])('rejects %s', (file, code) =>
    expect(violations('/src/' + file, code, '/src').length).toBeGreaterThan(0),
  );
  it('allows composition via public feature entry', () =>
    expect(
      violations(
        '/src/app/x.ts',
        "import {Screen} from '../features/verification';",
        '/src',
      ),
    ).toEqual([]));
});
