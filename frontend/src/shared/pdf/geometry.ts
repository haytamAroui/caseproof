export type Box = readonly [number, number, number, number];
export interface PdfPageResult {
  width: number;
  height: number;
  rotation: number;
  view: number[];
  userUnit: number;
  transform: number[];
  text: string;
  textBoxes: { text: string; box: Box }[];
}
export function projectBox(transform: readonly number[], box: Box): Box {
  if (
    transform.length !== 6 ||
    [...transform, ...box].some((n) => !Number.isFinite(n)) ||
    Math.abs(transform[0]! * transform[3]! - transform[1]! * transform[2]!) <
      1e-12 ||
    box[0] >= box[2] ||
    box[1] >= box[3]
  )
    throw new Error('Unsupported page geometry.');
  const [a, b, c, d, e, f] = transform as [
    number,
    number,
    number,
    number,
    number,
    number,
  ];
  const points = [
    [box[0], box[1]],
    [box[2], box[1]],
    [box[2], box[3]],
    [box[0], box[3]],
  ].map(([x, y]) => [a * x! + c * y! + e, b * x! + d * y! + f]);
  return [
    Math.min(...points.map((p) => p[0]!)),
    Math.min(...points.map((p) => p[1]!)),
    Math.max(...points.map((p) => p[0]!)),
    Math.max(...points.map((p) => p[1]!)),
  ];
}

export interface DocumentInspection {
  pages: number;
  open(bytes: Uint8Array): Promise<void>;
  render(
    canvas: HTMLCanvasElement,
    page: number,
    zoom: number,
    rotation: number,
    dpr: number,
    layoutWidth?: number,
  ): Promise<PdfPageResult>;
  cancelRender(): void;
  close(): Promise<void>;
}

/** Raster coordinates are page-image pixels, never PDF user-space points. */
export interface RasterRegion {
  region_id: string;
  original_sha256: string;
  page_number: number;
  bbox: [number, number, number, number];
  image_size: [number, number];
  crop_box: [number, number, number, number];
  rotation: 0 | 90 | 180 | 270;
  user_unit: number;
  cropbox_rasterized: true;
  ocr_word?: { text: string; bbox: [number, number, number, number] };
}

export function parseRasterRegions(
  value: unknown,
  expected: { snapshot: string; sha256: string; version: string },
): { regions: RasterRegion[]; unassessed: number } {
  if (!value || typeof value !== 'object')
    throw new Error('Raster metadata unavailable');
  const response = value as Record<string, unknown>;
  if (
    response.schema !== 'caseproof-raster-overlays-v1' ||
    response.snapshot_hash !== expected.snapshot ||
    response.original_sha256 !== expected.sha256 ||
    response.source_version_id !== expected.version ||
    response.interpretation !== 'navigation_only_never_a_verdict' ||
    !Array.isArray(response.regions) ||
    response.regions.length > 96 ||
    !Number.isInteger(response.unassessed_region_count) ||
    (response.unassessed_region_count as number) < 0 ||
    (response.unassessed_region_count as number) > 96
  )
    throw new Error('Raster metadata inconsistent with source');
  const regions = response.regions as RasterRegion[];
  const ids = new Set<string>();
  for (const region of regions) {
    if (
      !region ||
      typeof region !== 'object' ||
      !/^[0-9a-f]{64}$/.test(region.region_id) ||
      ids.has(region.region_id) ||
      region.original_sha256 !== expected.sha256 ||
      !Number.isInteger(region.page_number) ||
      region.page_number < 1 ||
      region.page_number > 200 ||
      !Array.isArray(region.bbox) ||
      region.bbox.length !== 4 ||
      !Array.isArray(region.image_size) ||
      region.image_size.length !== 2 ||
      !Array.isArray(region.crop_box) ||
      region.crop_box.length !== 4 ||
      ![0, 90, 180, 270].includes(region.rotation) ||
      !Number.isFinite(region.user_unit) ||
      region.user_unit <= 0 ||
      region.user_unit > 75 ||
      region.cropbox_rasterized !== true
    )
      throw new Error('Invalid raster region');
    ids.add(region.region_id);
    if (region.ocr_word !== undefined) {
      const word = region.ocr_word;
      if (
        !word ||
        typeof word.text !== 'string' ||
        word.text.length < 1 ||
        word.text.length > 256 ||
        !Array.isArray(word.bbox) ||
        word.bbox.length !== 4 ||
        !word.bbox.every(Number.isInteger) ||
        word.bbox[0] < 0 ||
        word.bbox[1] < 0 ||
        word.bbox[0] >= word.bbox[2] ||
        word.bbox[1] >= word.bbox[3] ||
        word.bbox[2] > region.image_size[0] ||
        word.bbox[3] > region.image_size[1]
      )
        throw new Error('Invalid OCR word geometry');
    }
  }
  return { regions, unassessed: response.unassessed_region_count as number };
}

/** Projection is valid only when independent PDF.js page metadata agrees with
 * the raster's CropBox, rotation and UserUnit. No guessed page offsets. */
export function projectRasterBox(
  region: RasterRegion,
  page: PdfPageResult,
): Box | null {
  const [x0, y0, x1, y1] = region.bbox;
  const [rw, rh] = region.image_size;
  const [left, bottom, right, top] = region.crop_box;
  const nums = [
    ...region.bbox,
    ...region.image_size,
    ...region.crop_box,
    region.user_unit,
    ...page.view,
    ...page.transform,
    page.width,
    page.height,
    page.userUnit,
    page.rotation,
  ];
  if (
    nums.some((n) => !Number.isFinite(n)) ||
    page.view.length !== 4 ||
    page.transform.length !== 6 ||
    page.width <= 0 ||
    page.height <= 0 ||
    rw < 1 ||
    rh < 1 ||
    rw > 5000 ||
    rh > 6500 ||
    rw * rh > 16_000_000 ||
    ![x0, y0, x1, y1, rw, rh].every(Number.isInteger) ||
    x0 < 0 ||
    y0 < 0 ||
    x0 >= x1 ||
    y0 >= y1 ||
    x1 > rw ||
    y1 > rh ||
    right <= left ||
    top <= bottom ||
    ![0, 90, 180, 270].includes(page.rotation) ||
    region.cropbox_rasterized !== true ||
    Math.abs(page.userUnit - region.user_unit) > 1e-6 ||
    [left, bottom, right, top].some(
      (n, i) => Math.abs(n - page.view[i]!) > 0.05,
    )
  )
    return null;
  const rotated = region.rotation === 90 || region.rotation === 270;
  const nativeW = rotated ? top - bottom : right - left;
  const nativeH = rotated ? right - left : top - bottom;
  if (
    Math.abs(rw / rh - nativeW / nativeH) > Math.max(0.02, 3 / Math.min(rw, rh))
  )
    return null;
  const delta = (((page.rotation - region.rotation) % 360) + 360) % 360;
  const corners = [
    [x0 / rw, y0 / rh],
    [x1 / rw, y0 / rh],
    [x1 / rw, y1 / rh],
    [x0 / rw, y1 / rh],
  ];
  const mapped = corners.map(([x, y]) => {
    if (delta === 90) return [(1 - y!) * page.width, x! * page.height];
    if (delta === 180) return [(1 - x!) * page.width, (1 - y!) * page.height];
    if (delta === 270) return [y! * page.width, (1 - x!) * page.height];
    return [x! * page.width, y! * page.height];
  });
  const bounds: Box = [
    Math.min(...mapped.map((p) => p[0]!)),
    Math.min(...mapped.map((p) => p[1]!)),
    Math.max(...mapped.map((p) => p[0]!)),
    Math.max(...mapped.map((p) => p[1]!)),
  ];
  return bounds.every(Number.isFinite) ? bounds : null;
}
