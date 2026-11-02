import { expect, it } from 'vitest';
import { projectBox, projectRasterBox, parseRasterRegions } from './geometry';
it('projects all four corners through origin, rotation, scale and UserUnit', () => {
  expect(projectBox([0, 2, 2, 0, -300, -200], [140, 200, 260, 240])).toEqual([
    100, 80, 180, 320,
  ]);
  expect(projectBox([2.5, 0, 0, -2.5, 0, 2000], [140, 200, 260, 240])).toEqual([
    350, 1400, 650, 1500,
  ]);
  expect(projectBox([-2, 0, 0, 2, 1200, 0], [140, 200, 260, 240])).toEqual([
    680, 400, 920, 480,
  ]);
});
it('rejects missing, nonfinite and singular coordinate transforms', () => {
  for (const transform of [[], [0, 0, 0, 0, 0, 0], [1, 0, 0, 1, NaN, 0]])
    expect(() => projectBox(transform, [1, 2, 3, 4])).toThrow();
});

it('preserves a valid zero-origin source box', () => {
  expect(projectBox([1, 0, 0, -1, 0, 800], [0, 0, 120, 40])).toEqual([
    0, 760, 120, 800,
  ]);
});

it('independently projects cropped raster points across rotation and zoom without DPR drift', () => {
  const region = {
    region_id: 'a'.repeat(64),
    original_sha256: 'b'.repeat(64),
    page_number: 6,
    bbox: [10, 20, 30, 40] as [number, number, number, number],
    image_size: [100, 200] as [number, number],
    crop_box: [200, 300, 300, 500] as [number, number, number, number],
    rotation: 0 as const,
    user_unit: 2,
    cropbox_rasterized: true as const,
  };
  const page = {
    width: 500,
    height: 1000,
    rotation: 0,
    view: [200, 300, 300, 500],
    userUnit: 2,
    transform: [5, 0, 0, -5, -1000, 2500],
    text: '',
    textBoxes: [],
  };
  expect(projectRasterBox(region, page)).toEqual([50, 100, 150, 200]);
  expect(
    projectRasterBox(region, {
      ...page,
      width: 1000,
      height: 500,
      rotation: 90,
    }),
  ).toEqual([800, 50, 900, 150]);
  expect(
    projectRasterBox(region, {
      ...page,
      width: 1000,
      height: 500,
      rotation: 270,
    }),
  ).toEqual([100, 350, 200, 450]);
  // Backing pixels and DPR do not enter the CSS-coordinate projection.
  expect(
    projectRasterBox(region, { ...page, width: 1000, height: 2000 }),
  ).toEqual([100, 200, 300, 400]);
  expect(
    projectRasterBox(region, { ...page, view: [0, 0, 100, 200] }),
  ).toBeNull();
  expect(projectRasterBox(region, { ...page, userUnit: 1 })).toBeNull();
  expect(
    projectRasterBox({ ...region, bbox: [10, 20, 300, 40] }, page),
  ).toBeNull();
});

it('raster payload cannot cross a snapshot, original hash or source version', () => {
  const expected = {
    snapshot: 'a'.repeat(64),
    sha256: 'b'.repeat(64),
    version: 'old',
  };
  const payload = {
    schema: 'caseproof-raster-overlays-v1',
    snapshot_hash: expected.snapshot,
    original_sha256: expected.sha256,
    source_version_id: expected.version,
    interpretation: 'navigation_only_never_a_verdict',
    regions: [],
    unassessed_region_count: 2,
  };
  expect(parseRasterRegions(payload, expected).unassessed).toBe(2);
  expect(() =>
    parseRasterRegions({ ...payload, snapshot_hash: 'c'.repeat(64) }, expected),
  ).toThrow();
  expect(() =>
    parseRasterRegions(
      { ...payload, original_sha256: 'c'.repeat(64) },
      expected,
    ),
  ).toThrow();
  expect(() =>
    parseRasterRegions({ ...payload, source_version_id: 'new' }, expected),
  ).toThrow();
});
