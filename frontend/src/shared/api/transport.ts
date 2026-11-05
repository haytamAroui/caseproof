import { SessionController, SessionEnded } from '../session';
type BinaryBinding = {
  sha256: string;
  snapshot: string;
  length: number;
  media?:
    | 'application/json'
    | 'application/octet-stream'
    | 'text/markdown'
    | 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
  export?: true;
  editorCandidate?: true;
  originalSha256?: string;
};
export class ApiError extends Error {
  constructor(public readonly status: number) {
    super(
      status === 401 || status === 403 || status === 404
        ? 'This report is unavailable for the current session.'
        : status === 409
          ? 'The snapshot changed. Reopen the current report.'
          : status === 412
            ? 'Snapshot stale. Reopen the current report.'
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
  async post(
    path: string,
    body: unknown,
    signal?: AbortSignal,
    mutation?: { snapshot: string; idempotencyKey?: string },
  ): Promise<unknown> {
    return this.read(path, signal, undefined, body, mutation);
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
  async preservedOriginal(
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
    return (await this.read(path, signal, {
      ...binding,
      media: 'application/octet-stream',
    })) as Uint8Array;
  }
  async artifact(
    path: string,
    binding: BinaryBinding,
    signal: AbortSignal,
  ): Promise<Uint8Array> {
    if (
      binding.export !== true ||
      !binding.media ||
      !/^[0-9a-f]{64}$/.test(binding.sha256) ||
      !/^[0-9a-f]{64}$/.test(binding.snapshot) ||
      !Number.isInteger(binding.length) ||
      binding.length < 1 ||
      binding.length >
        (binding.media.includes('wordprocessingml') ? 5_242_880 : 2_000_000) ||
      !/^\/v2\/matters\/[^/]+\/briefs\/[^/]+\/dossier\/releases\/[0-9a-f-]{36}\/artifacts\/(json|markdown|docx)$/.test(
        new URL(path, 'https://caseproof.invalid').pathname,
      )
    )
      throw new ApiError(502);
    return (await this.read(path, signal, binding)) as Uint8Array;
  }
  async editorCandidate(
    path: string,
    command: { snapshot_hash: string; original_sha256: string },
    receipt: { sha256: string; byte_length: number },
    signal: AbortSignal,
  ): Promise<Uint8Array> {
    if (
      !/^\/v2\/matters\/[^/]+\/briefs\/[^/]+\/dossier\/editor\/candidate$/.test(
        new URL(path, 'https://caseproof.invalid').pathname,
      ) ||
      !/^[0-9a-f]{64}$/.test(receipt.sha256) ||
      !/^[0-9a-f]{64}$/.test(command.original_sha256) ||
      !/^[0-9a-f]{64}$/.test(command.snapshot_hash) ||
      !Number.isInteger(receipt.byte_length) ||
      receipt.byte_length < 1 ||
      receipt.byte_length > 5_242_880
    )
      throw new ApiError(502);
    return (await this.read(
      path,
      signal,
      {
        sha256: receipt.sha256,
        snapshot: command.snapshot_hash,
        length: receipt.byte_length,
        media:
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        editorCandidate: true,
        originalSha256: command.original_sha256,
      },
      command,
      { snapshot: command.snapshot_hash },
    )) as Uint8Array;
  }
  async nativeWordUpload(
    path: string,
    binding: {
      snapshot_hash: string;
      original_sha256: string;
      candidate_sha256: string;
      byte_length: number;
    },
    bytes: Uint8Array,
    signal: AbortSignal,
    mutation?: { requestId: string; reviewId: string },
  ): Promise<unknown> {
    if (
      !/^\/v2\/matters\/[^/]+\/briefs\/[^/]+\/dossier\/editor\/native\/(preview|commit)$/.test(path) ||
      path.includes('://') ||
      /[\\\r\n?#]/.test(path) ||
      (mutation !== undefined && !path.endsWith('/commit')) ||
      (!mutation && !path.endsWith('/preview')) ||
      !/^[0-9a-f]{64}$/.test(binding.snapshot_hash) ||
      !/^[0-9a-f]{64}$/.test(binding.original_sha256) ||
      !/^[0-9a-f]{64}$/.test(binding.candidate_sha256) ||
      binding.candidate_sha256 === binding.original_sha256 ||
      !Number.isInteger(binding.byte_length) ||
      binding.byte_length !== bytes.byteLength ||
      bytes.byteLength < 1 ||
      bytes.byteLength > 5_242_880 ||
      (mutation !== undefined &&
        (!/^[0-9a-f-]{36}$/.test(mutation.requestId) ||
          !/^[0-9a-f-]{36}$/.test(mutation.reviewId)))
    )
      throw new ApiError(422);

    const ownDigest = Array.from(
      new Uint8Array(await crypto.subtle.digest('SHA-256', new Uint8Array(bytes))),
      (b) => b.toString(16).padStart(2, '0'),
    ).join('');
    if (ownDigest !== binding.candidate_sha256) throw new ApiError(422);

    const epoch = this.session.getSnapshot().epoch;
    const { controller, release } = this.session.requestController();
    const combined = AbortSignal.any([
      signal, controller.signal, AbortSignal.timeout(180000),
    ]);
    try {
      const token = await this.session.bearer(epoch);
      this.session.assert(epoch);
      combined.throwIfAborted();
      const response = await this.send(path, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'If-Match': `snapshot_id:${binding.snapshot_hash}`,
          'X-CaseProof-Snapshot-Hash': binding.snapshot_hash,
          'X-CaseProof-Original-SHA256': binding.original_sha256,
          'X-CaseProof-Candidate-SHA256': binding.candidate_sha256,
          'X-CaseProof-Byte-Length': String(binding.byte_length),
          ...(mutation
            ? {
                'Idempotency-Key': mutation.requestId,
                'X-CaseProof-Review-Request-ID': mutation.reviewId,
              }
            : {}),
        },
        body: new Uint8Array(bytes),
        signal: combined,
        cache: 'no-store',
        credentials: 'omit',
        redirect: 'error',
        referrerPolicy: 'no-referrer',
      });
      this.session.assert(epoch);
      combined.throwIfAborted();
      if (!response.ok) {
        if (response.status === 401) this.session.clear();
        throw new ApiError(response.status);
      }
      if (!response.headers.get('content-type')?.includes('application/json') ||
          !response.body) throw new ApiError(502);
      const reader = response.body.getReader();
      let size = 0;
      const chunks: Uint8Array[] = [];
      try {
        while (true) {
          const next = await reader.read();
          this.session.assert(epoch);
          combined.throwIfAborted();
          if (next.done) break;
          size += next.value.byteLength;
          if (size > 20000) throw new ApiError(502);
          chunks.push(next.value);
        }
      } catch (error) {
        await reader.cancel();
        throw error;
      } finally {
        reader.releaseLock();
      }
      const result = new Uint8Array(size);
      let cursor = 0;
      for (const chunk of chunks) { result.set(chunk, cursor); cursor += chunk.length; }
      this.session.assert(epoch);
      return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(result)) as unknown;
    } finally {
      release();
    }
  }
  private async read(
    path: string,
    signal?: AbortSignal,
    binding?: BinaryBinding,
    body?: unknown,
    mutation?: { snapshot: string; idempotencyKey?: string },
  ): Promise<unknown> {
    if (
      !path.startsWith('/v2/') ||
      path.includes('://') ||
      /[\\\r\n]/.test(path) ||
      !new URL(path, 'https://caseproof.invalid').pathname.startsWith('/v2/')
    )
      throw Error('Only same-origin application API paths are allowed');
    if (
      mutation &&
      (!/^[0-9a-f]{64}$/.test(mutation.snapshot) ||
        (mutation.idempotencyKey !== undefined &&
          !/^[0-9a-f-]{36}$/.test(mutation.idempotencyKey)))
    )
      throw Error('Invalid mutation correspondence');
    const epoch = this.session.getSnapshot().epoch;
    const { controller, release } = this.session.requestController();
    const combined = AbortSignal.any([
      controller.signal,
      AbortSignal.timeout(
        path.startsWith('/v2/workspace/intake/') ||
          path.includes('/dossier/releases') ||
          path.includes('/dossier/editor/') ||
          /\/dossier\/(confirmation|checks|recheck|corrections\/(preview|commit))$/.test(
            path,
          )
          ? 180000
          : 30000,
      ),
      ...(signal ? [signal] : []),
    ]);
    try {
      const token = await this.session.bearer(epoch);
      if (combined.aborted) throw new SessionEnded();
      const response = await this.send(path, {
        method: body === undefined ? 'GET' : 'POST',
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        headers: {
          Authorization: `Bearer ${token}`,
          ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
          ...(mutation
            ? { 'If-Match': `snapshot_id:${mutation.snapshot}` }
            : {}),
          ...(mutation?.idempotencyKey
            ? { 'Idempotency-Key': mutation.idempotencyKey }
            : {}),
        },
        signal: combined,
        credentials: 'omit',
        redirect: 'error',
        cache: 'no-store',
        referrerPolicy: 'no-referrer',
      });
      this.session.assert(epoch);
      combined.throwIfAborted();
      if (!response.ok) {
        // A correction-history reader may lack correction permissions while
        // remaining authorized for their current matter. That denial must not
        // destroy an otherwise valid reader session. Other resource denials
        // retain the existing revocation-clears-session safety behavior.
        const recoveryRead =
          body === undefined &&
          /^\/v2\/matters\/[^/]+\/briefs\/[^/]+\/dossier\/snapshots\/[0-9a-f]{64}\/references\/[^/]+\/correction-operations$/.test(
            new URL(path, 'https://caseproof.invalid').pathname,
          );
        // Lacking the separate export grant is not session revocation. Do not
        // sign out a valid report reader merely for asking about releases.
        const exportGrantBoundary = /\/dossier\/releases(?:\/|$)/.test(
          new URL(path, 'https://caseproof.invalid').pathname,
        );
        // Editing permissions do not imply the source-reading session is revoked.
        const editorBoundary = /\/dossier\/editor(?:\/|$)/.test(
          new URL(path, 'https://caseproof.invalid').pathname,
        );
        if (
          response.status === 401 ||
          ((response.status === 403 || response.status === 404) &&
            !recoveryRead &&
            !exportGrantBoundary &&
            !editorBoundary)
        )
          this.session.clear();
        throw new ApiError(response.status);
      }
      if (
        !response.headers
          .get('content-type')
          ?.includes(
            binding ? (binding.media ?? 'application/pdf') : 'application/json',
          )
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
          combined.throwIfAborted();
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
      combined.throwIfAborted();
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
          response.headers.get(
            binding.export
              ? 'X-CaseProof-Export-SHA256'
              : binding.editorCandidate
                ? 'X-CaseProof-Edit-Candidate-SHA256'
                : 'X-CaseProof-Original-SHA256',
          ) !== binding.sha256 ||
          (binding.export &&
            response.headers.get('X-CaseProof-Export-Size') !==
              String(binding.length)) ||
          (binding.editorCandidate &&
            response.headers.get('X-CaseProof-Original-SHA256') !==
              binding.originalSha256)
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
