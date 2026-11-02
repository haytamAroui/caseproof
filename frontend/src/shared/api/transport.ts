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
    private send: typeof fetch = (...args) => fetch(...args),
  ) {}
  async get(path: string, signal?: AbortSignal): Promise<unknown> {
    return this.read(path, signal);
  }
  async pdf(
    path: string,
    binding: { sha256: string; snapshot: string; length: number },
    signal: AbortSignal,
  ): Promise<Uint8Array> {
    if (
      !/^[0-9a-f]{64}$/.test(binding.sha256) ||
      !/^[0-9a-f]{64}$/.test(binding.snapshot) ||
      !Number.isInteger(binding.length) ||
      binding.length < 1 ||
      binding.length > 20_000_000
    )
      throw new ApiError(502);
    return (await this.read(path, signal, binding)) as Uint8Array;
  }
  private async read(
    path: string,
    signal?: AbortSignal,
    binding?: { sha256: string; snapshot: string; length: number },
  ): Promise<unknown> {
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
        if (
          response.status === 401 ||
          response.status === 403 ||
          response.status === 404
        )
          this.session.clear();
        throw new ApiError(response.status);
      }
      if (
        !response.headers
          .get('content-type')
          ?.includes(binding ? 'application/pdf' : 'application/json')
      )
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
          if (size > (binding?.length ?? 2_000_000)) throw new ApiError(502);
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
      if (binding) {
        if (
          size !== binding.length ||
          response.headers.get('X-CaseProof-Snapshot') !== binding.snapshot ||
          response.headers.get('X-CaseProof-Original-SHA256') !== binding.sha256
        )
          throw new ApiError(502);
        const digest = new Uint8Array(
          await crypto.subtle.digest('SHA-256', bytes),
        );
        this.session.assert(epoch);
        if (
          combined.aborted ||
          Array.from(digest, (b) => b.toString(16).padStart(2, '0')).join(
            '',
          ) !== binding.sha256
        )
          throw new ApiError(502);
        return bytes;
      }
      return JSON.parse(
        new TextDecoder('utf-8', { fatal: true }).decode(bytes),
      ) as unknown;
    } finally {
      release();
    }
  }
}

/** Exact same-origin auth endpoints; no credentials or session material persisted. */
export class AuthTransport {
  constructor(private send: typeof fetch = (...args) => fetch(...args)) {}
  async login(
    email: string,
    password: string,
    signal: AbortSignal,
  ): Promise<unknown> {
    const response = await this.send('/v2/workspace/session', {
      method: 'POST',
      credentials: 'omit',
      redirect: 'error',
      cache: 'no-store',
      referrerPolicy: 'no-referrer',
      signal: AbortSignal.any([signal, AbortSignal.timeout(30000)]),
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!response.ok)
      throw new Error(
        response.status === 401
          ? 'Sign-in was rejected. Check your email and password.'
          : response.status === 429
            ? 'Too many sign-in attempts. Wait a minute and try again.'
            : 'Sign-in is unavailable. Try again.',
      );
    if (
      !response.headers.get('content-type')?.includes('application/json') ||
      !response.body
    )
      throw new Error('Invalid sign-in response.');
    const reader = response.body.getReader();
    const parts: Uint8Array[] = [];
    let size = 0;
    try {
      while (true) {
        const part = await reader.read();
        if (part.done) break;
        size += part.value.length;
        if (size > 16384) throw new Error('Invalid sign-in response.');
        parts.push(part.value);
      }
    } catch (error) {
      await reader.cancel();
      throw error;
    } finally {
      reader.releaseLock();
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const part of parts) {
      bytes.set(part, offset);
      offset += part.length;
    }
    if (signal.aborted) throw new SessionEnded();
    try {
      return JSON.parse(
        new TextDecoder('utf-8', { fatal: true }).decode(bytes),
      ) as unknown;
    } catch {
      throw new Error('Invalid sign-in response.');
    }
  }
  async logout(token: string): Promise<void> {
    const response = await this.send('/v2/workspace/session/end', {
      method: 'POST',
      credentials: 'omit',
      redirect: 'error',
      cache: 'no-store',
      referrerPolicy: 'no-referrer',
      signal: AbortSignal.timeout(15000),
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok)
      throw new Error(
        'Workspace cleared. Provider sign-out could not be confirmed.',
      );
  }
}
