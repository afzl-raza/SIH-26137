// Real authentication API client - talks to the /api/auth/* endpoints added
// to backend/main.py (backed by backend/auth/store.py: PBKDF2-hashed
// passwords, an opaque bearer session token, one-time password-reset
// tokens). No credentials are checked or accepted client-side; every
// decision (does this email exist, does this password match, is this
// session/reset token valid) is made by the backend.
//
// The session token is the one thing kept client-side, in localStorage, so
// a page refresh doesn't lose the session (see getCurrentUser()). It is an
// opaque, revocable, expiring token - never the password itself, and never
// logged.
import { apiFetch } from '../api';

const TOKEN_STORAGE_KEY = 'qdfro_auth_token';

export class AuthError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'AuthError';
    this.status = status;
  }
}

function readToken() {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_STORAGE_KEY, token);
    else localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // Storage can be unavailable (private browsing, disabled site data) -
    // the session just won't survive a refresh in that case.
  }
}

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

const UNREACHABLE_MESSAGE = 'Unable to connect to the authentication server. Please make sure the backend is running.';

// Status codes whose message is always this fixed, generic text regardless
// of what the backend's `detail` said - a 5xx must never surface an
// internal exception's own message to the user (that's the backend's
// implementation detail, not something for them to act on).
const FIXED_STATUS_MESSAGES = {
  403: "You don't have permission to do that.",
  404: 'We could not find what you were looking for.',
  422: 'Please check the highlighted fields.',
  500: "We couldn't complete your request right now. Please try again.",
  502: "We couldn't complete your request right now. Please try again.",
  503: "We couldn't complete your request right now. Please try again."
};

// Safe to log: status/content-type/parse-error/detail text only - never the
// request body, so a password typed into a form can never reach here.
function logAuthFailure(endpoint, kind, details) {
  console.error('Authentication request failed', { endpoint, kind, ...details });
}

// Turns a network failure or a backend error response into one clear,
// user-facing message, while logging enough safe detail (status, content
// type, the backend's own detail text) to the console for local debugging.
// Never surfaces a stack trace, raw JSON, SQL, or an internal exception name.
//
// The key distinction this makes: a real response from THIS backend - a
// success or a deliberate error - is always JSON (every endpoint in
// main.py's auth/* returns JSON, and FastAPI's own default handler for an
// unhandled exception does too). A non-JSON error body reaching here was
// never produced by the backend at all - in local dev this is almost always
// Vite's dev-server proxy (vite.config.js) returning its own bare 5xx
// because nothing is listening on the backend port it forwards /api to, not
// an application-level failure. That case previously fell into a generic
// "Something went wrong" message identical to a real backend error, which
// is the bug this fixes: the two are now told apart and reported
// differently.
async function request(path, options = {}) {
  let res;
  try {
    res = await apiFetch(path, options);
  } catch (err) {
    logAuthFailure(path, 'network', { message: err?.message });
    throw new AuthError(UNREACHABLE_MESSAGE);
  }

  const contentType = res.headers.get('content-type') || '';
  let body = null;
  if (contentType.includes('application/json')) {
    try {
      body = await res.json();
    } catch (err) {
      logAuthFailure(path, 'malformed-json', { status: res.status, message: err?.message });
    }
  }

  if (res.ok) {
    return body;
  }

  if (body === null) {
    // Not JSON at all - nothing our own backend would ever send.
    logAuthFailure(path, 'non-json-error-response', { status: res.status, contentType });
    throw new AuthError(UNREACHABLE_MESSAGE, res.status);
  }

  if (res.status >= 500) {
    logAuthFailure(path, 'backend-error', { status: res.status, detail: body?.detail });
    throw new AuthError(FIXED_STATUS_MESSAGES[500], res.status);
  }

  if (typeof body.detail === 'string') {
    // Our own HTTPException(detail=...) messages (main.py) are already
    // written to be shown to the user as-is.
    throw new AuthError(body.detail, res.status);
  }

  // FastAPI's automatic request-validation errors shape `detail` as a list
  // of {loc, msg, type} objects, not a string - not meant for end users
  // verbatim, so every other unrecognized shape falls back to a status-based
  // message instead of dumping that structure into the UI.
  logAuthFailure(path, 'unrecognized-detail-shape', { status: res.status, detail: body.detail });
  throw new AuthError(
    FIXED_STATUS_MESSAGES[res.status] || 'Please check the information you entered and try again.',
    res.status
  );
}

export async function register({ name, position, company, email, password }) {
  const data = await request('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, position, company, email, password })
  });
  writeToken(data.token);
  return data.user;
}

export async function login({ email, password }) {
  const data = await request('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  writeToken(data.token);
  return data.user;
}

export async function logout() {
  const token = readToken();
  writeToken(null);
  if (!token) return;
  try {
    await apiFetch('/api/auth/logout', {
      method: 'POST',
      headers: authHeaders(token)
    });
  } catch {
    // Session is already cleared client-side; if the revoke call itself
    // failed, the token simply expires on its own TTL server-side instead.
  }
}

// Restores a session after a page refresh/reload. Returns the current user
// if the stored token is still valid, or null (and clears the stale token)
// otherwise - never throws, since "no session" is an expected outcome here,
// not an error.
export async function getCurrentUser() {
  const token = readToken();
  if (!token) return null;
  try {
    const data = await request('/api/auth/me', { headers: authHeaders(token) });
    return data.user;
  } catch {
    writeToken(null);
    return null;
  }
}

export async function forgotPassword({ email }) {
  return request('/api/auth/forgot-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email })
  });
}

export async function resetPassword({ token, newPassword }) {
  return request('/api/auth/reset-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, new_password: newPassword })
  });
}
