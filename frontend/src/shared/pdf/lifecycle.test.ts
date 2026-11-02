import { describe, expect, it, vi } from 'vitest';
import { boundedInspection, InspectionTimeout } from './lifecycle';
describe('bounded source inspection', () => {
  it('never publishes a renderer result after its deadline', async () => {
    vi.useFakeTimers();
    try {
      let complete!: (value: string) => void;
      const operation = new Promise<string>((resolve) => {
        complete = resolve;
      });
      const closed = vi.fn(),
        publish = vi.fn();
      const pending = boundedInspection(
        operation,
        new AbortController().signal,
        closed,
      ).then(publish);
      const rejected =
        expect(pending).rejects.toBeInstanceOf(InspectionTimeout);
      await vi.advanceTimersByTimeAsync(15001);
      await rejected;
      complete('late private text');
      await Promise.resolve();
      expect(publish).not.toHaveBeenCalled();
      expect(closed).toHaveBeenCalledOnce();
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });
  it('fences a selection change even if the engine ignores cancellation', async () => {
    const controller = new AbortController();
    let complete!: (value: string) => void;
    const operation = new Promise<string>((resolve) => {
      complete = resolve;
    });
    const publish = vi.fn(),
      timeout = vi.fn();
    const pending = boundedInspection(
      operation,
      controller.signal,
      timeout,
    ).then(publish);
    const rejected = expect(pending).rejects.toThrow();
    controller.abort();
    await rejected;
    complete('old source');
    await Promise.resolve();
    expect(publish).not.toHaveBeenCalled();
    expect(timeout).not.toHaveBeenCalled();
  });
  it('cleans up the deadline after a successful render', async () => {
    vi.useFakeTimers();
    try {
      const close = vi.fn();
      expect(
        await boundedInspection(
          Promise.resolve('pixels'),
          new AbortController().signal,
          close,
        ),
      ).toBe('pixels');
      await vi.advanceTimersByTimeAsync(15001);
      expect(close).not.toHaveBeenCalled();
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });
});
