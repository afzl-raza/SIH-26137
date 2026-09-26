import React, { useState, useEffect, useCallback } from 'react';
import LandingPage from './pages/LandingPage';
import Overview from './pages/Overview';
import Dashboard from './pages/Dashboard';

const OVERVIEW_HASH = '#/overview';
const DASHBOARD_HASH = '#/app';

function resolveView() {
  if (window.location.hash === DASHBOARD_HASH) return 'dashboard';
  if (window.location.hash === OVERVIEW_HASH) return 'overview';
  return 'landing';
}

// Minimal hash-based view switch - no routing library, since the app only
// ever has these three views. Landing (marketing) -> Overview (home/gate,
// mostly decorative) -> Dashboard (the real map/optimize/benchmark
// workflow). "Get Started" on Landing goes to Overview, not straight to
// Dashboard, now that Overview exists as the landing spot for a logged-in
// operator.
export default function App() {
  const [view, setView] = useState(resolveView);

  useEffect(() => {
    const onHashChange = () => setView(resolveView());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const enterOverview = useCallback(() => {
    window.location.hash = OVERVIEW_HASH;
    setView('overview');
  }, []);

  const enterDashboard = useCallback(() => {
    window.location.hash = DASHBOARD_HASH;
    setView('dashboard');
  }, []);

  const exitToLanding = useCallback(() => {
    window.location.hash = '';
    setView('landing');
  }, []);

  const exitToOverview = useCallback(() => {
    window.location.hash = OVERVIEW_HASH;
    setView('overview');
  }, []);

  if (view === 'dashboard') {
    return <Dashboard onExitToOverview={exitToOverview} />;
  }
  if (view === 'overview') {
    return <Overview onEnterDashboard={enterDashboard} onExitToLanding={exitToLanding} />;
  }
  return <LandingPage onEnterApp={enterOverview} />;
}
