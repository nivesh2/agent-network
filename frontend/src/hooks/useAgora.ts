import { useSSE } from "./useSSE";

export function useAgora() {
  const {
    session,
    feed,
    activity,
    connectionStatus,
    sortMode,
    setSortMode,
    activeSessionId,
    setActiveSessionId,
  } = useSSE();

  return {
    session,
    feed,
    activity,
    connectionStatus,
    sortMode,
    setSortMode,
    activeSessionId,
    setActiveSessionId,
  };
}
