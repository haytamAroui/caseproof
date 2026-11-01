/** Memory-only host bridge; server authorization remains authoritative. */
export interface SessionHost {
  getBearer(): Promise<string>;
  expiresAt?: number;
  clear?(): void;
}
export class SessionEnded extends Error {
  constructor() {
    super('Session ended. Connect again to continue.');
  }
}
export class SessionController {
  private host: SessionHost | null = null;
  private expiryTimer: ReturnType<typeof setTimeout> | undefined;
  private snapshot = { epoch: 0, connected: false };
  private listeners = new Set<() => void>();
  private aborters = new Set<AbortController>();
  private cleanups = new Set<() => void>();
  getSnapshot = () => this.snapshot;
  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => {
      this.listeners.delete(fn);
    };
  };
  onClear = (fn: () => void) => {
    this.cleanups.add(fn);
    return () => {
      this.cleanups.delete(fn);
    };
  };
  connect(host: SessionHost) {
    this.clear();
    if (
      host.expiresAt !== undefined &&
      (!Number.isFinite(host.expiresAt) || host.expiresAt <= Date.now())
    )
      throw new SessionEnded();
    this.host = host;
    if (host.expiresAt !== undefined)
      this.expiryTimer = setTimeout(
        () => this.clear(),
        Math.min(host.expiresAt! - Date.now(), 2147483647),
      );
    this.snapshot = { epoch: this.snapshot.epoch, connected: true };
    this.emit();
  }
  clear() {
    clearTimeout(this.expiryTimer);
    this.expiryTimer = undefined;
    const host = this.host;
    this.host = null;
    this.snapshot = { epoch: this.snapshot.epoch + 1, connected: false };
    for (const c of this.aborters) c.abort();
    this.aborters.clear();
    for (const fn of this.cleanups) fn();
    this.emit();
    host?.clear?.();
  }
  private emit() {
    for (const listener of this.listeners) listener();
  }
  assert(epoch: number) {
    if (!this.host || epoch !== this.snapshot.epoch) throw new SessionEnded();
    if (
      this.host.expiresAt !== undefined &&
      this.host.expiresAt <= Date.now()
    ) {
      this.clear();
      throw new SessionEnded();
    }
  }
  async bearer(epoch: number) {
    this.assert(epoch);
    if (
      this.host?.expiresAt !== undefined &&
      this.host.expiresAt <= Date.now()
    ) {
      this.clear();
      throw new SessionEnded();
    }
    let token: string;
    try {
      token = await this.host!.getBearer();
    } catch {
      if (epoch === this.snapshot.epoch) this.clear();
      throw new SessionEnded();
    }
    this.assert(epoch);
    if (!token || token.length > 8192 || /[\r\n]/.test(token)) {
      this.clear();
      throw new SessionEnded();
    }
    return token;
  }
  requestController() {
    const controller = new AbortController();
    this.aborters.add(controller);
    return {
      controller,
      release: () => {
        this.aborters.delete(controller);
      },
    };
  }
}
