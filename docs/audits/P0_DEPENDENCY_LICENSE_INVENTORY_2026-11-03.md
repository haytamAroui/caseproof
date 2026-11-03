# P0.4 dependency license inventory — 3 November 2026

Scope: exact lockfile metadata and installed package metadata for this development build; includes runtime, development and platform-conditional packages. This is an inventory, not legal clearance, a notice file, or verification of every transitive binary and bundled license. Review redistribution obligations before shipping. The CaseProof project license is not assessed here.

- Code baseline tested: `eafd389e325839c06390e74f32c2890f6b128195`; Python: 3.12.14 on Linux x86_64.
- `uv.lock` SHA-256: `e79dd8b17015a98943d67793304b6b1ab183088d8491c1a5cf49b7d7170340a4`; `frontend/package-lock.json` SHA-256: `20ec50ca2d7237be88ce1c7f5d85a2271eb2fad7cee9d48abfac372ba763184e`.
- Frontend declarations below come from every lockfile package entry, including platform-specific packages not installed here. Installed package metadata was compared with the lockfile.
- Python declarations come from installed distributions at the locked version. Platform-conditional colorama, tzdata, and pyee 13.0.1 were downloaded to a separate temporary target for metadata inspection; this did not change the project environment. Local project entry is not a third-party distribution.
- AGPL text search over declarations found no match. This is not proof of license compliance: license files, embedded assets, binary components, combined expressions, redistribution and NOTICE obligations require human review.

Frontend: **237** locked package paths; 205 installed; 32 not installed; 0 version/license mismatches; 0 missing lockfile license declarations.

License declaration counts: `Apache-2.0`: 20, `BSD-2-Clause`: 6, `BSD-3-Clause`: 3, `BlueOak-1.0.0`: 1, `CC-BY-4.0`: 1, `ISC`: 10, `MIT`: 180, `MPL-2.0`: 14, `PSF-2.0`: 1, `Python-2.0`: 1.

| Package path | Version | Declared license | Observed |
| --- | --- | --- | --- |
| `@apidevtools/json-schema-ref-parser` | `11.9.3` | `MIT` | installed |
| `@axe-core/playwright` | `4.14.0` | `MPL-2.0` | installed |
| `@babel/code-frame` | `7.29.7` | `MIT` | installed |
| `@babel/compat-data` | `7.29.7` | `MIT` | installed |
| `@babel/core` | `7.29.7` | `MIT` | installed |
| `@babel/generator` | `7.29.12` | `MIT` | installed |
| `@babel/helper-compilation-targets` | `7.29.7` | `MIT` | installed |
| `@babel/helper-globals` | `7.29.7` | `MIT` | installed |
| `@babel/helper-module-imports` | `7.29.7` | `MIT` | installed |
| `@babel/helper-module-transforms` | `7.29.7` | `MIT` | installed |
| `@babel/helper-string-parser` | `7.29.11` | `MIT` | installed |
| `@babel/helper-validator-identifier` | `7.29.7` | `MIT` | installed |
| `@babel/helper-validator-option` | `7.29.7` | `MIT` | installed |
| `@babel/helpers` | `7.29.10` | `MIT` | installed |
| `@babel/parser` | `7.29.12` | `MIT` | installed |
| `@babel/template` | `7.29.7` | `MIT` | installed |
| `@babel/traverse` | `7.29.12` | `MIT` | installed |
| `@babel/types` | `7.29.11` | `MIT` | installed |
| `@cacheable/memory` | `2.2.0` | `MIT` | installed |
| `@cacheable/utils` | `2.5.0` | `MIT` | installed |
| `@eslint-community/eslint-utils` | `4.10.1` | `MIT` | installed |
| `@eslint-community/eslint-utils/node_modules/eslint-visitor-keys` | `3.4.3` | `Apache-2.0` | installed |
| `@eslint-community/regexpp` | `4.12.2` | `MIT` | installed |
| `@eslint/config-array` | `0.23.5` | `Apache-2.0` | installed |
| `@eslint/config-helpers` | `0.7.0` | `Apache-2.0` | installed |
| `@eslint/core` | `1.2.1` | `Apache-2.0` | installed |
| `@eslint/js` | `10.0.1` | `MIT` | installed |
| `@eslint/object-schema` | `3.0.5` | `Apache-2.0` | installed |
| `@eslint/plugin-kit` | `0.7.3` | `Apache-2.0` | installed |
| `@humanfs/core` | `0.19.2` | `Apache-2.0` | installed |
| `@humanfs/node` | `0.16.8` | `Apache-2.0` | installed |
| `@humanfs/types` | `0.15.0` | `Apache-2.0` | installed |
| `@humanwhocodes/module-importer` | `1.0.1` | `Apache-2.0` | installed |
| `@humanwhocodes/retry` | `0.4.3` | `Apache-2.0` | installed |
| `@jridgewell/gen-mapping` | `0.3.13` | `MIT` | installed |
| `@jridgewell/remapping` | `2.3.5` | `MIT` | installed |
| `@jridgewell/resolve-uri` | `3.1.2` | `MIT` | installed |
| `@jridgewell/sourcemap-codec` | `1.6.0` | `MIT` | installed |
| `@jridgewell/trace-mapping` | `0.3.31` | `MIT` | installed |
| `@jsdevtools/ono` | `7.1.3` | `MIT` | installed |
| `@keyv/bigmap` | `1.3.1` | `MIT` | installed |
| `@keyv/serialize` | `1.1.1` | `MIT` | installed |
| `@napi-rs/canvas` | `1.1.0` | `MIT` | installed |
| `@napi-rs/canvas-android-arm64` | `1.1.0` | `MIT` | platform/not installed |
| `@napi-rs/canvas-darwin-arm64` | `1.1.0` | `MIT` | platform/not installed |
| `@napi-rs/canvas-darwin-x64` | `1.1.0` | `MIT` | platform/not installed |
| `@napi-rs/canvas-linux-arm-gnueabihf` | `1.1.0` | `MIT` | platform/not installed |
| `@napi-rs/canvas-linux-arm64-gnu` | `1.1.0` | `MIT` | platform/not installed |
| `@napi-rs/canvas-linux-arm64-musl` | `1.1.0` | `MIT` | platform/not installed |
| `@napi-rs/canvas-linux-riscv64-gnu` | `1.1.0` | `MIT` | platform/not installed |
| `@napi-rs/canvas-linux-x64-gnu` | `1.1.0` | `MIT` | installed |
| `@napi-rs/canvas-linux-x64-musl` | `1.1.0` | `MIT` | installed |
| `@napi-rs/canvas-win32-arm64-msvc` | `1.1.0` | `MIT` | platform/not installed |
| `@napi-rs/canvas-win32-x64-msvc` | `1.1.0` | `MIT` | platform/not installed |
| `@oxc-project/types` | `0.156.0` | `MIT` | installed |
| `@playwright/test` | `1.64.1` | `Apache-2.0` | installed |
| `@remix-run/route-pattern` | `0.22.1` | `MIT` | installed |
| `@rolldown/binding-android-arm-eabi` | `1.2.16` | `MIT` | platform/not installed |
| `@rolldown/binding-android-arm64` | `1.2.16` | `MIT` | platform/not installed |
| `@rolldown/binding-darwin-arm64` | `1.2.16` | `MIT` | platform/not installed |
| `@rolldown/binding-darwin-x64` | `1.2.16` | `MIT` | platform/not installed |
| `@rolldown/binding-freebsd-x64` | `1.2.16` | `MIT` | platform/not installed |
| `@rolldown/binding-linux-arm-gnueabihf` | `1.2.16` | `MIT` | platform/not installed |
| `@rolldown/binding-linux-arm64-gnu` | `1.2.16` | `MIT` | platform/not installed |
| `@rolldown/binding-linux-arm64-musl` | `1.2.16` | `MIT` | platform/not installed |
| `@rolldown/binding-linux-ppc64-gnu` | `1.2.16` | `MIT` | platform/not installed |
| `@rolldown/binding-linux-s390x-gnu` | `1.2.16` | `MIT` | platform/not installed |
| `@rolldown/binding-linux-x64-gnu` | `1.2.16` | `MIT` | installed |
| `@rolldown/binding-linux-x64-musl` | `1.2.16` | `MIT` | installed |
| `@rolldown/binding-openharmony-arm64` | `1.2.16` | `MIT` | platform/not installed |
| `@rolldown/binding-win32-arm64-msvc` | `1.2.16` | `MIT` | platform/not installed |
| `@rolldown/binding-win32-x64-msvc` | `1.2.16` | `MIT` | platform/not installed |
| `@rolldown/pluginutils` | `1.0.1` | `MIT` | installed |
| `@tanstack/query-core` | `5.105.0` | `MIT` | installed |
| `@tanstack/react-query` | `5.105.0` | `MIT` | installed |
| `@types/chai` | `5.2.3` | `MIT` | installed |
| `@types/deep-eql` | `4.0.2` | `MIT` | installed |
| `@types/esrecurse` | `4.3.1` | `MIT` | installed |
| `@types/estree` | `1.0.10` | `MIT` | installed |
| `@types/json-schema` | `7.0.15` | `MIT` | installed |
| `@types/lodash` | `4.17.27` | `MIT` | installed |
| `@types/node` | `26.6.6` | `MIT` | installed |
| `@types/react` | `19.3.0` | `MIT` | installed |
| `@types/react-dom` | `19.3.0` | `MIT` | installed |
| `@typescript-eslint/eslint-plugin` | `8.72.1` | `MIT` | installed |
| `@typescript-eslint/eslint-plugin/node_modules/ignore` | `7.0.14` | `MIT` | installed |
| `@typescript-eslint/parser` | `8.72.1` | `MIT` | installed |
| `@typescript-eslint/project-service` | `8.72.1` | `MIT` | installed |
| `@typescript-eslint/scope-manager` | `8.72.1` | `MIT` | installed |
| `@typescript-eslint/tsconfig-utils` | `8.72.1` | `MIT` | installed |
| `@typescript-eslint/type-utils` | `8.72.1` | `MIT` | installed |
| `@typescript-eslint/types` | `8.72.1` | `MIT` | installed |
| `@typescript-eslint/typescript-estree` | `8.72.1` | `MIT` | installed |
| `@typescript-eslint/typescript-estree/node_modules/semver` | `7.8.5` | `ISC` | installed |
| `@typescript-eslint/utils` | `8.72.1` | `MIT` | installed |
| `@typescript-eslint/visitor-keys` | `8.72.1` | `MIT` | installed |
| `@vitejs/plugin-react` | `6.1.2` | `MIT` | installed |
| `@vitest/mocker` | `5.0.5` | `MIT` | installed |
| `@vitest/spy` | `5.0.5` | `MIT` | installed |
| `acorn` | `8.19.0` | `MIT` | installed |
| `acorn-jsx` | `5.3.2` | `MIT` | installed |
| `ajv` | `8.20.0` | `MIT` | installed |
| `argparse` | `2.0.1` | `Python-2.0` | installed |
| `assertion-error` | `2.0.1` | `MIT` | installed |
| `axe-core` | `4.14.0` | `MPL-2.0` | installed |
| `balanced-match` | `4.0.4` | `MIT` | installed |
| `baseline-browser-mapping` | `2.11.34` | `Apache-2.0` | installed |
| `brace-expansion` | `5.0.12` | `MIT` | installed |
| `browserslist` | `4.29.5` | `MIT` | installed |
| `cacheable` | `2.5.0` | `MIT` | installed |
| `caniuse-lite` | `1.0.30001820` | `CC-BY-4.0` | installed |
| `chai` | `6.3.0` | `MIT` | installed |
| `convert-source-map` | `2.0.0` | `MIT` | installed |
| `cookie-es` | `3.1.1` | `MIT` | installed |
| `cross-spawn` | `7.0.6` | `MIT` | installed |
| `csstype` | `3.2.3` | `MIT` | installed |
| `debug` | `4.4.3` | `MIT` | installed |
| `deep-is` | `0.1.4` | `MIT` | installed |
| `detect-libc` | `2.1.2` | `Apache-2.0` | installed |
| `electron-to-chromium` | `1.5.472` | `ISC` | installed |
| `es-module-lexer` | `2.3.2` | `MIT` | installed |
| `escalade` | `3.2.0` | `MIT` | installed |
| `escape-string-regexp` | `4.0.0` | `MIT` | installed |
| `eslint` | `10.14.0` | `MIT` | installed |
| `eslint-plugin-react-hooks` | `7.1.1` | `MIT` | installed |
| `eslint-scope` | `9.1.2` | `BSD-2-Clause` | installed |
| `eslint-visitor-keys` | `5.0.1` | `Apache-2.0` | installed |
| `eslint/node_modules/ajv` | `6.15.0` | `MIT` | installed |
| `eslint/node_modules/json-schema-traverse` | `0.4.1` | `MIT` | installed |
| `espree` | `11.2.0` | `BSD-2-Clause` | installed |
| `esquery` | `1.7.0` | `BSD-3-Clause` | installed |
| `esrecurse` | `4.3.0` | `BSD-2-Clause` | installed |
| `estraverse` | `5.3.0` | `BSD-2-Clause` | installed |
| `estree-walker` | `3.0.3` | `MIT` | installed |
| `esutils` | `2.0.3` | `BSD-2-Clause` | installed |
| `expect-type` | `1.4.0` | `Apache-2.0` | installed |
| `fast-deep-equal` | `3.1.3` | `MIT` | installed |
| `fast-json-stable-stringify` | `2.1.0` | `MIT` | installed |
| `fast-levenshtein` | `2.0.6` | `MIT` | installed |
| `fast-uri` | `3.1.9` | `BSD-3-Clause` | installed |
| `fdir` | `6.5.0` | `MIT` | installed |
| `file-entry-cache` | `11.1.5` | `MIT` | installed |
| `find-up` | `5.0.0` | `MIT` | installed |
| `flat-cache` | `6.1.23` | `MIT` | installed |
| `flatted` | `3.4.4` | `ISC` | installed |
| `fsevents` | `2.3.3` | `MIT` | platform/not installed |
| `gensync` | `1.0.0-beta.2` | `MIT` | installed |
| `glob-parent` | `6.0.2` | `ISC` | installed |
| `hashery` | `1.5.1` | `MIT` | installed |
| `hermes-estree` | `0.25.1` | `MIT` | installed |
| `hermes-parser` | `0.25.1` | `MIT` | installed |
| `hookified` | `1.15.1` | `MIT` | installed |
| `ignore` | `5.3.2` | `MIT` | installed |
| `imurmurhash` | `0.1.4` | `MIT` | installed |
| `is-extglob` | `2.1.1` | `MIT` | installed |
| `is-glob` | `4.0.3` | `MIT` | installed |
| `isexe` | `2.0.0` | `ISC` | installed |
| `js-tokens` | `4.0.0` | `MIT` | installed |
| `js-yaml` | `4.3.2` | `MIT` | installed |
| `jsesc` | `3.1.0` | `MIT` | installed |
| `json-schema-to-typescript` | `16.0.0` | `MIT` | installed |
| `json-schema-to-typescript/node_modules/argparse` | `3.0.4` | `PSF-2.0` | installed |
| `json-schema-to-typescript/node_modules/js-yaml` | `5.5.0` | `MIT` | installed |
| `json-schema-traverse` | `1.0.0` | `MIT` | installed |
| `json-stable-stringify-without-jsonify` | `1.0.1` | `MIT` | installed |
| `json5` | `2.2.3` | `MIT` | installed |
| `keyv` | `5.6.0` | `MIT` | installed |
| `levn` | `0.4.1` | `MIT` | installed |
| `lightningcss` | `1.33.0` | `MPL-2.0` | installed |
| `lightningcss-android-arm64` | `1.33.0` | `MPL-2.0` | platform/not installed |
| `lightningcss-darwin-arm64` | `1.33.0` | `MPL-2.0` | platform/not installed |
| `lightningcss-darwin-x64` | `1.33.0` | `MPL-2.0` | platform/not installed |
| `lightningcss-freebsd-x64` | `1.33.0` | `MPL-2.0` | platform/not installed |
| `lightningcss-linux-arm-gnueabihf` | `1.33.0` | `MPL-2.0` | platform/not installed |
| `lightningcss-linux-arm64-gnu` | `1.33.0` | `MPL-2.0` | platform/not installed |
| `lightningcss-linux-arm64-musl` | `1.33.0` | `MPL-2.0` | platform/not installed |
| `lightningcss-linux-x64-gnu` | `1.33.0` | `MPL-2.0` | installed |
| `lightningcss-linux-x64-musl` | `1.33.0` | `MPL-2.0` | installed |
| `lightningcss-win32-arm64-msvc` | `1.33.0` | `MPL-2.0` | platform/not installed |
| `lightningcss-win32-x64-msvc` | `1.33.0` | `MPL-2.0` | platform/not installed |
| `locate-path` | `6.0.0` | `MIT` | installed |
| `lodash` | `4.18.1` | `MIT` | installed |
| `lru-cache` | `5.1.1` | `ISC` | installed |
| `magic-string` | `1.4.5` | `MIT` | installed |
| `minimatch` | `10.2.6` | `BlueOak-1.0.0` | installed |
| `minimist` | `1.2.8` | `MIT` | installed |
| `ms` | `2.1.3` | `MIT` | installed |
| `nanoid` | `3.3.20` | `MIT` | installed |
| `natural-compare` | `1.4.0` | `MIT` | installed |
| `node-releases` | `2.0.63` | `MIT` | installed |
| `obug` | `3.0.0` | `MIT` | installed |
| `optionator` | `0.9.4` | `MIT` | installed |
| `p-limit` | `3.1.0` | `MIT` | installed |
| `p-locate` | `5.0.0` | `MIT` | installed |
| `path-exists` | `4.0.0` | `MIT` | installed |
| `path-key` | `3.1.1` | `MIT` | installed |
| `pdfjs-dist` | `6.5.438` | `Apache-2.0` | installed |
| `picocolors` | `1.1.1` | `ISC` | installed |
| `picomatch` | `4.0.7` | `MIT` | installed |
| `playwright` | `1.64.1` | `Apache-2.0` | installed |
| `playwright-core` | `1.64.1` | `Apache-2.0` | installed |
| `postcss` | `8.5.32` | `MIT` | installed |
| `prelude-ls` | `1.2.1` | `MIT` | installed |
| `prettier` | `3.9.10` | `MIT` | installed |
| `punycode` | `2.3.1` | `MIT` | installed |
| `qified` | `0.10.1` | `MIT` | installed |
| `qified/node_modules/hookified` | `2.2.0` | `MIT` | installed |
| `react` | `19.3.1` | `MIT` | installed |
| `react-dom` | `19.3.1` | `MIT` | installed |
| `react-router` | `8.5.1` | `MIT` | installed |
| `require-from-string` | `2.0.2` | `MIT` | installed |
| `rolldown` | `1.2.16` | `MIT` | installed |
| `scheduler` | `0.28.0` | `MIT` | installed |
| `semver` | `6.3.1` | `ISC` | installed |
| `shebang-command` | `2.0.0` | `MIT` | installed |
| `shebang-regex` | `3.0.0` | `MIT` | installed |
| `source-map-js` | `1.2.2` | `BSD-3-Clause` | installed |
| `std-env` | `4.3.0` | `MIT` | installed |
| `tinybench` | `6.2.2` | `MIT` | installed |
| `tinyexec` | `1.3.1` | `MIT` | installed |
| `tinyglobby` | `0.2.17` | `MIT` | installed |
| `ts-api-utils` | `2.5.0` | `MIT` | installed |
| `type-check` | `0.4.0` | `MIT` | installed |
| `typescript` | `6.0.3` | `Apache-2.0` | installed |
| `typescript-eslint` | `8.72.1` | `MIT` | installed |
| `undici-types` | `8.9.0` | `MIT` | installed |
| `update-browserslist-db` | `1.3.4` | `MIT` | installed |
| `uri-js` | `4.4.1` | `BSD-2-Clause` | installed |
| `vite` | `8.3.5` | `MIT` | installed |
| `vitest` | `5.0.5` | `MIT` | installed |
| `which` | `2.0.2` | `ISC` | installed |
| `why-is-node-running` | `3.2.1` | `MIT` | installed |
| `word-wrap` | `1.2.5` | `MIT` | installed |
| `yallist` | `3.1.1` | `ISC` | installed |
| `yocto-queue` | `0.1.0` | `MIT` | installed |
| `zod` | `4.6.7` | `MIT` | installed |
| `zod-validation-error` | `4.0.2` | `MIT` | installed |

## Python locked packages

| Package | Version | Metadata license declaration | Metadata source |
| --- | --- | --- | --- |
| `annotated-doc` | `0.0.5` | MIT | installed |
| `annotated-types` | `0.8.0` | MIT | installed |
| `anyio` | `4.15.1` | MIT | installed |
| `certifi` | `2026.10.19` | MPL-2.0 | installed |
| `charset-normalizer` | `3.5.2` | MIT | installed |
| `click` | `8.5.0` | BSD-3-Clause | installed |
| `colorama` | `0.4.6` | BSD License | separate temporary target |
| `defusedxml` | `0.7.1` | PSFL | installed |
| `exceptiondesk` | `0.1.0` | project package; not assessed | local project |
| `fastapi` | `0.157.0` | MIT | installed |
| `greenlet` | `3.5.6` | MIT AND PSF-2.0 | installed |
| `h11` | `0.16.0` | MIT | installed |
| `httpcore` | `1.0.9` | BSD-3-Clause | installed |
| `httpx` | `0.28.1` | BSD-3-Clause | installed |
| `idna` | `3.20` | BSD-3-Clause | installed |
| `iniconfig` | `2.3.1` | MIT | installed |
| `librt` | `0.16.0` | MIT | installed |
| `lxml` | `6.1.3` | BSD-3-Clause | installed |
| `mypy` | `1.20.2` | MIT | installed |
| `mypy-extensions` | `1.1.0` | MIT | installed |
| `opentelemetry-api` | `1.45.1` | Apache-2.0 | installed |
| `opentelemetry-sdk` | `1.45.1` | Apache-2.0 | installed |
| `opentelemetry-semantic-conventions` | `0.66b1` | Apache-2.0 | installed |
| `packaging` | `26.3` | Apache-2.0 OR BSD-2-Clause | installed |
| `pathspec` | `1.1.1` | Mozilla Public License 2.0 (MPL 2.0) | installed |
| `pillow` | `12.3.0` | MIT-CMU | installed |
| `playwright` | `1.64.1` | Apache-2.0 | installed |
| `pluggy` | `1.7.0` | MIT | installed |
| `psycopg` | `3.3.6` | LGPL-3.0-only | installed |
| `psycopg-binary` | `3.3.6` | LGPL-3.0-only | installed |
| `pydantic` | `2.14.1` | MIT | installed |
| `pydantic-core` | `2.50.1` | MIT | installed |
| `pyee` | `13.0.1` | MIT | separate temporary target |
| `pyee` | `14.0.0` | MIT | installed |
| `pygments` | `2.21.0` | BSD-2-Clause | installed |
| `pypdf` | `6.21.2` | BSD-3-Clause | installed |
| `pytest` | `9.1.1` | MIT | installed |
| `python-docx` | `1.2.0` | MIT | installed |
| `reportlab` | `4.5.1` | BSD license (see license.txt for details), Copyright (c) 2000-2025, ReportLab Inc. | installed |
| `ruff` | `0.17.1` | MIT | installed |
| `starlette` | `1.9.0` | BSD-3-Clause | installed |
| `typing-extensions` | `4.16.0` | PSF-2.0 | installed |
| `typing-inspection` | `0.4.4` | MIT | installed |
| `tzdata` | `2026.5` | Apache-2.0 | separate temporary target |
| `uvicorn` | `0.54.0` | BSD-3-Clause | installed |

AGPL-declaration matches: **0**. Packages marked MISSING or not inspected are not cleared. `psycopg` and `psycopg-binary` declare LGPL-3.0-only; frontend entries include MPL-2.0 and CC-BY-4.0. Their distribution and attribution obligations are not resolved by this scan.
