import React, { useState, useEffect, useCallback } from 'react';
import LandingPage from './pages/LandingPage';
import Dashboard from './pages/Dashboard';

const DASHBOARD_HASH = '#/app';

function resolveView() {
  return window.location.hash === DASHBOARD_HASH ? 'dashboard' : 'landing';
}

// Minimal hash-based view switch - no routing library, since the app only
// ever has these two views. Landing is the entry point; "Get Started" /
// "Explore Platform" navigate into the dashboard today, and will instead
// point at an auth route once that flow exists (see LandingPage's
// onEnterApp hook).
export default function App() {
  const [view, setView] = useState(resolveView);

  useEffect(() => {
    const onHashChange = () => setView(resolveView());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const enterApp = useCallback(() => {
    window.location.hash = DASHBOARD_HASH;
    setView('dashboard');
  }, []);

  const exitToLanding = useCallback(() => {
    window.location.hash = '';
    setView('landing');
  }, []);

  if (view === 'dashboard') {
    return <Dashboard onExitToLanding={exitToLanding} />;
  }
  return <LandingPage onEnterApp={enterApp} />;
}
