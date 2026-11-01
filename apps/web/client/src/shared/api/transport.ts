import { SessionController, SessionEnded } from '../session';
export class ApiError extends Error {
  constructor(public readonly status: number) {
    super(
      status === 401 || status === 403 || status === 404
        ? 'This report is unavailable for the current session.'
        : status === 409
          ? 'The snapshot changed. Reopen the current report.'
          : 'The service could not return this report. Try again.',
    );
  }
}
export class ApiClient {
  constructor(
    private session: SessionController,
    private send: typeof fetch = fetch,
  ) {}
  async get(path: string, signal?: AbortSignal): Promise<unknown> {
    if (
      !path.startsWith('/v2/') ||
      path.includes('://') ||
      /[\\\r\n]/.test(path) ||
      !new URL(path, 'https://caseproof.invalid').pathname.startsWith('/v2/')
    )
      throw Error('Only same-origin application API paths are allowed');
    const epoch = this.session.getSnapshot().epoch;
    const { controller, release } = this.session.requestController();
    const combined = AbortSignal.any([
      controller.signal,
      AbortSignal.timeout(30000),
      ...(signal ? [signal] : []),
    ]);
    try {
      const token = await this.session.bearer(epoch);
      if (combined.aborted) throw new SessionEnded();
      const response = await this.send(path, {
        headers: { Authorization: `Bearer ${token}` },
        signal: combined,
        credentials: 'omit',
        redirect: 'error',
        cache: 'no-store',
        referrerPolicy: 'no-referrer',
      });
      this.session.assert(epoch);
      if (!response.ok) {
        if (response.status === 401 || response.status === 403)
          this.session.clear();
        throw new ApiError(response.status);
      }
      if (!response.headers.get('content-type')?.includes('application/json'))
        throw new ApiError(502);
      if (!response.body) throw new ApiError(502);
      const reader = response.body.getReader();
      const chunks: Uint8Array[] = [];
      let size = 0;
      try {
        while (true) {
          const part = await reader.read();
          this.session.assert(epoch);
          if (part.done) break;
          size += part.value.byteLength;
          if (size > 2_000_000) throw new ApiError(502);
          chunks.push(part.value);
        }
      } catch (error) {
        await reader.cancel();
        throw error;
      } finally {
        reader.releaseLock();
      }
      this.session.assert(epoch);
      const bytes = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) {
        bytes.set(chunk, offset);
        offset += chunk.byteLength;
      }
      return JSON.parse(
        new TextDecoder('utf-8', { fatal: true }).decode(bytes),
      ) as unknown;
    } finally {
      release();
    }
  }
}
