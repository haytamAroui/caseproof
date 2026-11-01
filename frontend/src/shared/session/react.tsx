import { createContext, useContext, useSyncExternalStore } from 'react';
import type { SessionController } from './controller';
export const SessionContext = createContext<SessionController | null>(null);
export function useSessionController() {
  const value = useContext(SessionContext);
  if (!value) throw Error('Missing session composition');
  return value;
}
export function useSession() {
  const c = useSessionController();
  return useSyncExternalStore(c.subscribe, c.getSnapshot);
}
