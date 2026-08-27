const GRAPH_SYNC_EVENT = 'job-hunt:graph-sync';
const GRAPH_SYNC_STORAGE_KEY = 'job-hunt.graph-sync.v1';

export const notifyGraphDataChanged = (payload = {}) => {
  if (typeof window === 'undefined') return;
  const message = { ...payload, changedAt: Date.now() };
  window.dispatchEvent(new CustomEvent(GRAPH_SYNC_EVENT, { detail: message }));
  try {
    window.localStorage.setItem(GRAPH_SYNC_STORAGE_KEY, JSON.stringify(message));
  } catch {
    // Storage can be unavailable in privacy-restricted browser contexts.
  }
};

export const subscribeGraphDataChanged = (handler) => {
  if (typeof window === 'undefined') return () => {};
  const onCustomEvent = (event) => handler(event.detail || {});
  const onStorageEvent = (event) => {
    if (event.key !== GRAPH_SYNC_STORAGE_KEY || !event.newValue) return;
    try { handler(JSON.parse(event.newValue)); } catch { /* ignore malformed stale event */ }
  };
  window.addEventListener(GRAPH_SYNC_EVENT, onCustomEvent);
  window.addEventListener('storage', onStorageEvent);
  return () => {
    window.removeEventListener(GRAPH_SYNC_EVENT, onCustomEvent);
    window.removeEventListener('storage', onStorageEvent);
  };
};
