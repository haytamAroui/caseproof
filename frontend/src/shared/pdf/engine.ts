/** Candidate PDF.js adapter. Adoption follows the same-fixture comparison. */
import { getDocument, PDFWorker, AnnotationMode } from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import type {
  PDFDocumentProxy,
  PDFPageProxy,
  RenderTask,
  TextItem,
} from 'pdfjs-dist/types/src/display/api';
import { projectBox } from './geometry';
import type { Box, PdfPageResult } from './geometry';
export class PdfInspection {
  private worker = new Worker(workerUrl, { type: 'module' });
  private pdfWorker = PDFWorker.create({ port: this.worker });
  private task: ReturnType<typeof getDocument> | null = null;
  private doc: PDFDocumentProxy | null = null;
  private renderTask: RenderTask | null = null;
  private page: PDFPageProxy | null = null;
  private closed = false;
  private canvas: HTMLCanvasElement | null = null;
  private generation = 0;
  pages = 0;
  async open(bytes: Uint8Array): Promise<void> {
    if (this.closed || !bytes.length || bytes.length > 20_000_000)
      throw new Error('PDF exceeds the inspection budget.');
    this.task = getDocument({
      data: bytes,
      worker: this.pdfWorker,
      useWasm: false,
      enableXfa: false,
      useWorkerFetch: false,
      disableFontFace: true,
      useSystemFonts: true,
      isOffscreenCanvasSupported: false,
      isImageDecoderSupported: false,
      disableAutoFetch: true,
      disableRange: true,
      disableStream: true,
      maxImageSize: 16_000_000,
      canvasMaxAreaInBytes: 64_000_000,
      stopAtErrors: true,
      verbosity: 0,
    });
    this.doc = await this.task.promise;
    if (
      this.closed ||
      !Number.isInteger(this.doc.numPages) ||
      this.doc.numPages < 1 ||
      this.doc.numPages > 200
    ) {
      void this.close();
      throw new Error('PDF page count exceeds the inspection budget.');
    }
    this.pages = this.doc.numPages;
  }
  async render(
    canvas: HTMLCanvasElement,
    number: number,
    zoom: number,
    rotation: number,
    dpr: number,
    layoutWidth?: number,
  ): Promise<PdfPageResult> {
    const generation = ++this.generation;
    if (this.canvas) this.canvas.width = 0;
    this.canvas = canvas;
    this.renderTask?.cancel();
    this.page?.cleanup();
    this.page = null;
    if (
      !this.doc ||
      this.closed ||
      !Number.isInteger(number) ||
      number < 1 ||
      number > this.pages ||
      ![0, 90, 180, 270].includes(rotation) ||
      zoom < 0.5 ||
      zoom > 2 ||
      dpr < 1 ||
      dpr > 3
    )
      throw new Error('Unsupported page inspection request.');
    const page = await this.doc.getPage(number);
    if (generation !== this.generation || this.closed)
      throw new Error('Page selection changed.');
    this.page = page;
    const nativeViewport = page.getViewport({
      scale: 1,
      rotation: (page.rotate + rotation) % 360,
    });
    if (
      layoutWidth !== undefined &&
      (!Number.isFinite(layoutWidth) || layoutWidth < 100 || layoutWidth > 2000)
    )
      throw new Error('Unsupported layout size.');
    const viewport = page.getViewport({
      scale:
        zoom *
        (layoutWidth === undefined ? 1 : layoutWidth / nativeViewport.width),
      rotation: (page.rotate + rotation) % 360,
    });
    if (
      ![viewport.width, viewport.height].every(
        (n) => Number.isFinite(n) && n > 0 && n <= 6500,
      ) ||
      viewport.width * viewport.height * dpr * dpr > 16_000_000
    )
      throw new Error('Page rendering exceeds the pixel budget.');
    canvas.width = Math.ceil(viewport.width * dpr);
    canvas.height = Math.ceil(viewport.height * dpr);
    const context = canvas.getContext('2d', { alpha: false });
    if (!context) throw new Error('Page rendering is unavailable.');
    this.renderTask = page.render({
      canvasContext: context,
      canvas,
      viewport,
      transform: [dpr, 0, 0, dpr, 0, 0],
      annotationMode: AnnotationMode.ENABLE,
    });
    await this.renderTask.promise;
    const text = await page.getTextContent({ disableNormalization: true });
    if (generation !== this.generation || this.closed)
      throw new Error('Page selection changed.');
    if (text.items.length > 20000)
      throw new Error('Page text exceeds the inspection budget.');
    const items = text.items.filter((item): item is TextItem => 'str' in item);
    const textBoxes: PdfPageResult['textBoxes'] = [];
    for (const item of items) {
      const t = item.transform as number[];
      const style = text.styles[item.fontName];
      if (
        !style ||
        item.width <= 0 ||
        item.height <= 0 ||
        t.length !== 6 ||
        t[1] !== 0 ||
        t[2] !== 0 ||
        !t[0] ||
        t[0] < 0 ||
        t[3]! <= 0 ||
        !Number.isFinite(style.ascent) ||
        !Number.isFinite(style.descent)
      )
        continue;
      const box: Box = [
        t[4]!,
        t[5]! + item.height * style.descent!,
        t[4]! + item.width,
        t[5]! + item.height * style.ascent!,
      ];
      textBoxes.push({
        text: item.str,
        box: projectBox(viewport.transform, box),
      });
    }
    if (items.reduce((sum, item) => sum + item.str.length, 0) > 200000)
      throw new Error('Page text exceeds the inspection budget.');
    const content = items.map((i) => i.str + (i.hasEOL ? '\n' : ' ')).join('');
    if (content.length > 200000)
      throw new Error('Page text exceeds the inspection budget.');
    return {
      width: viewport.width,
      height: viewport.height,
      rotation: viewport.rotation,
      view: [...page.view],
      userUnit: page.userUnit,
      transform: [...viewport.transform],
      text: content,
      textBoxes,
    };
  }
  cancelRender(): void {
    this.generation++;
    this.renderTask?.cancel();
  }
  disposalFailed = false;
  private closing: Promise<void> | null = null;
  close(): Promise<void> {
    this.closing ??= this.dispose();
    return this.closing;
  }
  private async dispose(): Promise<void> {
    if (this.closed) return;
    this.closed = true;
    if (this.canvas) {
      this.canvas.width = 0;
      this.canvas.height = 0;
    }
    this.canvas = null;
    this.generation++;
    this.renderTask?.cancel();
    this.renderTask = null;
    this.page?.cleanup();
    this.page = null;
    const task = this.task;
    this.doc = null;
    this.task = null;
    this.pages = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      await Promise.race([
        task?.destroy(),
        new Promise<never>((_, reject) => {
          timer = setTimeout(
            () => reject(new Error('Disposal deadline')),
            1000,
          );
        }),
      ]);
    } catch {
      this.disposalFailed = true;
    } finally {
      clearTimeout(timer);
      this.worker.terminate();
      this.pdfWorker.destroy();
    }
  }
}
