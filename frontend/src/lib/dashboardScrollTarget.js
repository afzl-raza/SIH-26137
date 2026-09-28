// A one-shot cross-view signal: Overview's sidebar (a different top-level
// view than Dashboard - see App.jsx's hash-based switch) sets a real DOM
// element id here right before navigating to Dashboard, and Dashboard reads
// and clears it on mount to scroll straight to that section. sessionStorage
// (not a shared React context) because the two views are fully separate
// component trees mounted/unmounted by App.jsx, not siblings.
const KEY = 'qdfro_dashboard_scroll_target';

export function setPendingScrollTarget(sectionId) {
  try {
    sessionStorage.setItem(KEY, sectionId);
  } catch {
    // Storage can throw in a locked-down/private-browsing context - losing
    // the scroll target is harmless (Dashboard just opens at the top).
  }
}

export function consumePendingScrollTarget() {
  try {
    const value = sessionStorage.getItem(KEY);
    if (value) sessionStorage.removeItem(KEY);
    return value;
  } catch {
    return null;
  }
}
