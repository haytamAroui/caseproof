import Ajv from 'ajv/dist/2020.js';
import standalone from 'ajv/dist/standalone/index.js';
import { compile } from 'json-schema-to-typescript';
import { readFile, writeFile } from 'node:fs/promises';
for (const [name, type, stem] of [
  ['dossier', 'DossierView', 'generated'],
  ['matters', 'MatterCatalogView', 'matters-generated'],
]) {
  const source = new URL(
      `../src/shared/api/${name}.schema.json`,
      import.meta.url,
    ),
    target = new URL(`../src/shared/api/${stem}.ts`, import.meta.url);
  const content = await compile(
    JSON.parse(await readFile(source, 'utf8')),
    type,
    { bannerComment: `/* Generated from Python ${type}. Do not edit. */` },
  );
  if (process.argv.includes('--check')) {
    if ((await readFile(target, 'utf8')) !== content)
      throw Error('Generated TypeScript drift');
  } else await writeFile(target, content);

  const schema = JSON.parse(await readFile(source, 'utf8'));
  const ajv = new Ajv({ strict: false, code: { source: true, esm: true } });
  let validator = standalone(ajv, ajv.compile(schema));
  validator =
    "import lengthModule from 'ajv/dist/runtime/ucs2length.js';\nconst unicodeLength = typeof lengthModule === 'function' ? lengthModule : lengthModule.default;\n" +
    validator.replaceAll(
      'require("ajv/dist/runtime/ucs2length").default',
      'unicodeLength',
    );
  const output = new URL(
    `../src/shared/api/${stem}-validator.js`,
    import.meta.url,
  );
  const declaration = new URL(
    `../src/shared/api/${stem}-validator.d.ts`,
    import.meta.url,
  );
  const declarationText = `import type {${type}} from './${stem}';\nexport default function validate(value:unknown):value is ${type};\n`;
  for (const [path, text] of [
    [output, validator],
    [declaration, declarationText],
  ]) {
    if (process.argv.includes('--check')) {
      if ((await readFile(path, 'utf8')) !== text)
        throw Error('Generated validator drift');
    } else await writeFile(path, text);
  }
}
