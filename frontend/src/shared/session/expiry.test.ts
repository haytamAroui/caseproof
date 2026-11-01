import { describe, it, expect, vi } from 'vitest';
import { SessionController } from './controller';
describe('expiring signed host', () => {
  it('clears active memory and aborts requests at expiry without a new read', () => {
    vi.useFakeTimers();
    try {
      const session = new SessionController();
      const cleared = vi.fn();
      session.connect({
        getBearer: async () => 'signed-fixture',
        expiresAt: Date.now() + 1000,
        clear: cleared,
      });
      const pending = session.requestController();
      vi.advanceTimersByTime(1001);
      expect(session.getSnapshot().connected).toBe(false);
      expect(pending.controller.signal.aborted).toBe(true);
      expect(cleared).toHaveBeenCalledOnce();
    } finally {
      vi.useRealTimers();
    }
  });
  it('rejects an expired host before connecting', () => {
    expect(() =>
      new SessionController().connect({
        getBearer: async () => 'old',
        expiresAt: Date.now() - 1,
      }),
    ).toThrow('Session ended');
  });
});
