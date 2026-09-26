import React, { useState, useEffect, useCallback, useMemo } from 'react';
import LandingPage from './pages/LandingPage';
import AuthPage from './pages/AuthPage';
import Dashboard from './pages/Dashboard';
import Logo from './components/Logo';
import { getCurrentUser } from './lib/authService';

const AUTH_HASH = '#/auth';
const DASHBOARD_HASH = '#/app';

function resolveRequestedView() {
  if (window.location.hash === DASHBOARD_HASH) return 'dashboard';
  if (window.location.hash === AUTH_HASH) return 'auth';
  return 'landing';
}

// Reconciles what the URL asked for with what the session actually allows.
// The dashboard is never granted on hash alone: a direct #/app with no
// verified session resolves to 'auth' instead, and a signed-in user hitting
// #/auth is sent straight on to the dashboard rather than shown a login
// form for an account they're already in.
function resolveEffectiveView(requestedView, isAuthenticated) {
  if (requestedView === 'dashboard') return isAuthenticated ? 'dashboard' : 'auth';
  if (requestedView === 'auth' && isAuthenticated) return 'dashboard';
  return requestedView;
}

const HASH_FOR_VIEW = { landing: '', auth: AUTH_HASH, dashboard: DASHBOARD_HASH };

function AuthSplash() {
  return (
    <div className="min-h-screen bg-[#0D0C0B] flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="bg-[#1E1B18] border border-[#3A342E] p-2 rounded-lg animate-pulse">
          <Logo size={24} />
        </div>
        <span className="text-xs font-mono text-gray-500">Checking your session...</span>
      </div>
    </div>
  );
}

// Root view switch - no routing library, since the app only ever has three
// views: Landing -> Auth -> Dashboard. This is the one place session state
// (from lib/authService.js, backed by the real /api/auth/* endpoints) meets
// navigation; the forms themselves, in components/auth/, never see routing
// concerns.
export default function App() {
  const [requestedView, setRequestedView] = useState(resolveRequestedView);
  // 'checking' while the stored session token (if any) is verified against
  // the backend on load; then either a user object or null.
  const [sessionState, setSessionState] = useState('checking');
  const [user, setUser] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getCurrentUser().then((current) => {
      if (cancelled) return;
      setUser(current);
      setSessionState(current ? 'authenticated' : 'anonymous');
    });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const onHashChange = () => setRequestedView(resolveRequestedView());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const isAuthenticated = sessionState === 'authenticated';
  const effectiveView = useMemo(
    () => resolveEffectiveView(requestedView, isAuthenticated),
    [requestedView, isAuthenticated]
  );

  // Keeps the address bar honest: if the requested view got overridden
  // above (unauthenticated -> #/app, or authenticated -> #/auth), the hash
  // is corrected to match what's actually being shown rather than lying
  // about it after the fact.
  useEffect(() => {
    if (sessionState === 'checking') return;
    const targetHash = HASH_FOR_VIEW[effectiveView];
    if (window.location.hash !== targetHash) {
      window.location.hash = targetHash;
    }
  }, [effectiveView, sessionState]);

  const goToAuth = useCallback(() => {
    window.location.hash = AUTH_HASH;
    setRequestedView('auth');
  }, []);

  const goToLanding = useCallback(() => {
    window.location.hash = '';
    setRequestedView('landing');
  }, []);

  const handleAuthSuccess = useCallback((authenticatedUser) => {
    setUser(authenticatedUser);
    setSessionState('authenticated');
    window.location.hash = DASHBOARD_HASH;
    setRequestedView('dashboard');
  }, []);

  if (sessionState === 'checking') {
    return <AuthSplash />;
  }
  if (effectiveView === 'dashboard') {
    return <Dashboard onExitToLanding={goToLanding} />;
  }
  if (effectiveView === 'auth') {
    return <AuthPage onAuthSuccess={handleAuthSuccess} onBackToLanding={goToLanding} />;
  }
  return <LandingPage onEnterApp={goToAuth} />;
}
