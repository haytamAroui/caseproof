import { PdfInspection } from '../../src/shared/pdf/engine';
import type { PdfPageResult } from '../../src/shared/pdf/geometry';
let inspection: PdfInspection | null = null;
window.f2Harness = {
  redPixels() {
    const canvas = document.querySelector('canvas')!,
      ctx = canvas.getContext('2d')!;
    const pixels = ctx.getImageData(270, 770, 250, 80).data;
    let red = 0;
    for (let i = 0; i < pixels.length; i += 4)
      if (pixels[i]! > 180 && pixels[i + 1]! < 100 && pixels[i + 2]! < 100)
        red++;
    return red;
  },
  probe(box: number[]) {
    return measureBlackBox(document.querySelector('canvas')!, box);
  },
  async serverProbe(file: string, box: number[]) {
    const response = await fetch('/workspace/fixtures/' + file);
    const image = await createImageBitmap(await response.blob());
    const canvas = document.createElement('canvas');
    canvas.width = image.width;
    canvas.height = image.height;
    canvas.getContext('2d')!.drawImage(image, 0, 0);
    image.close();
    document.body.append(canvas);
    const measured = measureBlackBox(canvas, box);
    canvas.remove();
    return measured;
  },

  async open(name: string) {
    if (!/^[a-zA-Z0-9]+$/.test(name)) throw new Error('Fixture name required');
    if (inspection) await inspection.close();
    inspection = new PdfInspection();
    const response = await fetch(`/workspace/fixtures/${name}.pdf`);
    const started = performance.now();
    await inspection.open(new Uint8Array(await response.arrayBuffer()));
    return { pages: inspection.pages, openMs: performance.now() - started };
  },
  async render(page: number, zoom = 2, rotation = 0, dpr = 1) {
    if (!inspection) throw new Error('No fixture');
    const started = performance.now();
    const value = await inspection.render(
      document.querySelector('canvas')!,
      page,
      zoom,
      rotation,
      dpr,
    );
    return { ...value, renderMs: performance.now() - started };
  },
  async close() {
    if (inspection) await inspection.close();
    return {
      pages: inspection?.pages,
      disposalFailed: inspection?.disposalFailed,
    };
  },
};
declare global {
  interface Window {
    f2Harness: {
      redPixels(): number;
      probe(box: number[]): {
        bounds: number[];
        size: number[];
        cssScale: number;
      };
      serverProbe(
        file: string,
        box: number[],
      ): Promise<{ bounds: number[]; size: number[]; cssScale: number }>;
      open(name: string): Promise<{ pages: number; openMs: number }>;
      render(
        page: number,
        zoom?: number,
        rotation?: number,
        dpr?: number,
      ): Promise<PdfPageResult & { renderMs: number }>;
      close(): Promise<{
        pages: number | undefined;
        disposalFailed: boolean | undefined;
      }>;
    };
  }
}

function measureBlackBox(canvas: HTMLCanvasElement, expected: number[]) {
  const ctx = canvas.getContext('2d')!;
  const [x1, y1, x2, y2] = expected as [number, number, number, number];
  const left = Math.max(0, Math.floor(x1 - 10)),
    top = Math.max(0, Math.floor(y1 - 10));
  const width = Math.ceil(x2 + 10) - left,
    height = Math.ceil(y2 + 10) - top;
  const data = ctx.getImageData(left, top, width, height).data;
  let minX = Infinity,
    minY = Infinity,
    maxX = -1,
    maxY = -1;
  for (let y = 0; y < height; y++)
    for (let x = 0; x < width; x++) {
      const at = (y * width + x) * 4;
      if (data[at]! < 20 && data[at + 1]! < 20 && data[at + 2]! < 20) {
        minX = Math.min(minX, left + x);
        minY = Math.min(minY, top + y);
        maxX = Math.max(maxX, left + x + 1);
        maxY = Math.max(maxY, top + y + 1);
      }
    }
  return {
    cssScale: canvas.getBoundingClientRect().width / canvas.width,
    bounds: [minX, minY, maxX, maxY],
    size: [canvas.width, canvas.height],
  };
}
