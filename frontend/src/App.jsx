import React, { useState, useEffect, useCallback, useMemo } from 'react';
import LandingPage from './pages/LandingPage';
import AuthPage from './pages/AuthPage';
import Overview from './pages/Overview';
import Dashboard from './pages/Dashboard';
import Logo from './components/Logo';
import { getCurrentUser } from './lib/authService';

const AUTH_HASH = '#/auth';
const OVERVIEW_HASH = '#/overview';
const DASHBOARD_HASH = '#/app';

function resolveRequestedView() {
  if (window.location.hash === DASHBOARD_HASH) return 'dashboard';
  if (window.location.hash === OVERVIEW_HASH) return 'overview';
  if (window.location.hash === AUTH_HASH) return 'auth';
  return 'landing';
}

// Reconciles what the URL asked for with what the session actually allows.
// Overview and Dashboard are never granted on hash alone: either one with
// no verified session resolves to 'auth' instead, and a signed-in user
// hitting #/auth is sent on to Overview rather than shown a login form for
// an account they're already in.
function resolveEffectiveView(requestedView, isAuthenticated) {
  if ((requestedView === 'dashboard' || requestedView === 'overview') && !isAuthenticated) return 'auth';
  if (requestedView === 'auth' && isAuthenticated) return 'overview';
  return requestedView;
}

const HASH_FOR_VIEW = { landing: '', auth: AUTH_HASH, overview: OVERVIEW_HASH, dashboard: DASHBOARD_HASH };

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

// Root view switch - no routing library, since the app only ever has four
// views: Landing -> Auth -> Overview (home/gate, mostly decorative except
// its real generate+optimize demo) -> Dashboard (the real map/optimize/
// benchmark workflow). This is the one place session state (from
// lib/authService.js, backed by the real /api/auth/* endpoints) meets
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
  // above (unauthenticated -> auth, or authenticated-hitting-auth ->
  // overview), the hash is corrected to match what's actually being shown
  // rather than lying about it after the fact.
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

  const goToOverview = useCallback(() => {
    window.location.hash = OVERVIEW_HASH;
    setRequestedView('overview');
  }, []);

  const goToDashboard = useCallback(() => {
    window.location.hash = DASHBOARD_HASH;
    setRequestedView('dashboard');
  }, []);

  // A successful login/register lands the operator on Overview (the home
  // screen), not straight into Dashboard's deeper workflow.
  const handleAuthSuccess = useCallback((authenticatedUser) => {
    setUser(authenticatedUser);
    setSessionState('authenticated');
    window.location.hash = OVERVIEW_HASH;
    setRequestedView('overview');
  }, []);

  if (sessionState === 'checking') {
    return <AuthSplash />;
  }
  if (effectiveView === 'dashboard') {
    return <Dashboard onExitToOverview={goToOverview} />;
  }
  if (effectiveView === 'overview') {
    return <Overview onEnterDashboard={goToDashboard} onExitToLanding={goToLanding} />;
  }
  if (effectiveView === 'auth') {
    return <AuthPage onAuthSuccess={handleAuthSuccess} onBackToLanding={goToLanding} />;
  }
  return <LandingPage onEnterApp={goToAuth} />;
}
