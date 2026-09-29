export const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export function apiFetch(path, options = {}) {
  // Real-data loading (Nominatim + Overpass) can legitimately take several
  // minutes on a cold request. Keep the default generous enough that the app
  // does not time out before the backend has finished its own backoff/retry.
  const { timeoutMs = 180000, ...fetchOptions } = options;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    controller.abort(
      new DOMException(`Request to ${path} timed out after ${Math.round(timeoutMs / 1000)}s`, 'TimeoutError')
    );
  }, timeoutMs);

  if (fetchOptions.signal) {
    if (fetchOptions.signal.aborted) {
      controller.abort(fetchOptions.signal.reason);
    } else {
      fetchOptions.signal.addEventListener('abort', () => {
        controller.abort(fetchOptions.signal.reason);
      }, { once: true });
    }
  }

  return fetch(`${API_BASE}${path}`, {
    ...fetchOptions,
    signal: controller.signal
  }).finally(() => clearTimeout(timeoutId));
}

