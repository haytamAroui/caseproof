/** Deadline and cancellation fence: late renderer completion is never publishable. */
export class InspectionTimeout extends Error {
  constructor() {
    super('Source inspection exceeded its time budget.');
  }
}
export async function boundedInspection<T>(
  operation: Promise<T>,
  signal: AbortSignal,
  onTimeout: () => void,
): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let abort: () => void = () => undefined;
  const fence = new Promise<never>((_, reject) => {
    abort = () => reject(signal.reason);
    signal.addEventListener('abort', abort, { once: true });
    timer = setTimeout(() => {
      reject(new InspectionTimeout());
      onTimeout();
    }, 15000);
    if (signal.aborted) abort();
  });
  try {
    return await Promise.race([operation, fence]);
  } finally {
    clearTimeout(timer);
    signal.removeEventListener('abort', abort);
  }
}
