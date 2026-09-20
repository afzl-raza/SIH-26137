export const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export function apiFetch(path, options = {}) {
  const { timeoutMs = 15000, ...fetchOptions } = options;
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);

  return fetch(`${API_BASE}${path}`, {
    ...fetchOptions,
    signal: fetchOptions.signal || controller.signal
  }).finally(() => clearTimeout(id));
}
