export const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export function apiFetch(path, options = {}) {
  const { timeoutMs = 60000, ...fetchOptions } = options;
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

