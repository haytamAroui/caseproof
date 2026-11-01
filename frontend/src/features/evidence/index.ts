/** Viewer boundary only; selection follows hard-fixture acceptance. */
export interface PageImage {
  readonly originalSha256: string;
  readonly representationSha256: string;
  readonly page: number;
  readonly width: number;
  readonly height: number;
  readonly image: Blob;
}
export interface PageImageReader {
  readPage(
    input: {
      caseId: string;
      versionId: string;
      page: number;
      snapshot: string;
    },
    signal: AbortSignal,
  ): Promise<PageImage>;
}
