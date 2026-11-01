/** Memory-only host bridge; server authorization remains authoritative. */
export interface SessionHost {
  getBearer(): Promise<string>;
  clear?(): void;
}
export class SessionEnded extends Error {
  constructor() {
    super('Session ended. Connect again to continue.');
  }
}
export class SessionController {
  private host: SessionHost | null = null;
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
    this.host = host;
    this.snapshot = { epoch: this.snapshot.epoch, connected: true };
    this.emit();
  }
  clear() {
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
  }
  async bearer(epoch: number) {
    this.assert(epoch);
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
