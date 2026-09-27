// Guest access: a frontend-only "explore without an account" mode. This is
// deliberately NOT part of authService.js/authValidation.js - it never
// calls a backend endpoint, never creates a user, and never touches the
// real session token in localStorage (see authService.js's
// TOKEN_STORAGE_KEY). App.jsx keeps guest mode as its own sessionState
// value ('guest', distinct from 'authenticated') so the rest of the app can
// never mistake a guest for a real signed-in user.
//
// The flag lives in sessionStorage, not localStorage: it's a same-tab,
// non-sensitive "was exploring as a guest" marker (never a credential or
// token), and clearing automatically when the tab/browser closes is the
// right default for a mode nothing account-like backs.
const GUEST_MODE_KEY = 'qdfro_guest_mode';

export function enterGuestMode() {
  try {
    sessionStorage.setItem(GUEST_MODE_KEY, 'true');
  } catch {
    // Storage can be unavailable (private browsing, disabled site data) -
    // guest mode still works for the rest of this page load via React
    // state, it just won't survive a refresh.
  }
}

export function exitGuestMode() {
  try {
    sessionStorage.removeItem(GUEST_MODE_KEY);
  } catch {
    // Nothing to clean up if storage was never reachable.
  }
}

export function isGuestModeActive() {
  try {
    return sessionStorage.getItem(GUEST_MODE_KEY) === 'true';
  } catch {
    return false;
  }
}
