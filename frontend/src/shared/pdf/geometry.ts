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
