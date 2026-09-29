// Local Vite development proxies relative /api requests to FastAPI.  A hosted
// frontend has no such proxy, so an unset build variable must not send POSTs
// to Vercel's own /api route (which responds with 405 Method Not Allowed).
const DEFAULT_PRODUCTION_API = 'https://sih26137-backend.onrender.com';

export const API_BASE = import.meta.env.VITE_API_BASE_URL
  || (import.meta.env.PROD ? DEFAULT_PRODUCTION_API : '');

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

