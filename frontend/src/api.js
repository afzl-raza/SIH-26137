// Base URL for the backend API. Empty string keeps requests relative
// (handled by the Vite dev proxy locally). Set VITE_API_BASE_URL when the
// frontend and backend are deployed to different hosts (e.g. Vercel + Render).
export const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export function apiFetch(path, options) {
  return fetch(`${API_BASE}${path}`, options);
}
