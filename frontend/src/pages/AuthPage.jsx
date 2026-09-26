import React, { useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import Logo from '../components/Logo';
import LoginForm from '../components/auth/LoginForm';
import RegisterForm from '../components/auth/RegisterForm';
import ForgotPasswordForm from '../components/auth/ForgotPasswordForm';
import ResetPasswordForm from '../components/auth/ResetPasswordForm';

const HIGHLIGHTS = [
  'Quantum-inspired route optimization',
  'Live traffic-aware re-planning',
  'Benchmarked against classical algorithms'
];

const COPY = {
  login: {
    title: 'Welcome back',
    subtitle: 'Log in to access the fleet operations console.'
  },
  register: {
    title: 'Create your account',
    subtitle: 'Set up access to the fleet operations console.'
  },
  forgot: {
    title: 'Reset your password',
    subtitle: "Enter your account email and we'll send reset instructions."
  },
  reset: {
    title: 'Choose a new password',
    subtitle: 'Your new password must be at least 8 characters.'
  }
};

// A reset link (emailed to the user in a real deployment) opens the auth
// page with ?reset_token=... in the URL - detected once, up front, so a
// direct link lands straight on the reset form.
function initialResetToken() {
  try {
    return new URLSearchParams(window.location.search).get('reset_token');
  } catch {
    return null;
  }
}

// onAuthSuccess is a plain navigation hook - App.jsx owns what "successful
// authentication" means for the rest of the app (it stores the returned
// user and moves into the dashboard). This component only orchestrates
// which auth form is showing.
export default function AuthPage({ onAuthSuccess, onBackToLanding }) {
  const [resetToken] = useState(initialResetToken);
  const [mode, setMode] = useState(resetToken ? 'reset' : 'login');
  const [continuedResetToken, setContinuedResetToken] = useState(resetToken);
  const [notice, setNotice] = useState(null);

  const goToLogin = (message) => {
    setNotice(message || null);
    setMode('login');
  };

  const { title, subtitle } = COPY[mode];

  return (
    <div className="min-h-screen bg-[#0D0C0B] text-gray-100 font-sans selection:bg-[#C6602E] selection:text-white flex flex-col">
      <header className="px-4 sm:px-6 py-5">
        <button
          onClick={onBackToLanding}
          className="inline-flex items-center gap-2.5 group focus-visible:ring-2 focus-visible:ring-[#C6602E] rounded-lg"
          aria-label="Back to landing page"
        >
          <div className="bg-[#1E1B18] border border-[#3A342E] p-1.5 rounded-lg group-hover:border-[#5A3A22] transition-colors">
            <Logo size={20} />
          </div>
          <span className="font-display font-bold text-sm sm:text-base tracking-wide text-gray-100">
            Q-DFRO
          </span>
        </button>
      </header>

      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 pb-16 grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16 items-center">
        {/* Branding panel - hidden on small screens so the form stays the focus */}
        <div className="hidden lg:block landing-fade-up">
          <span className="inline-flex items-center gap-1.5 text-[11px] font-mono font-semibold bg-[#3A2318] text-[#E8A93A] border border-[#5A3A22] px-2.5 py-1 rounded-full">
            QUANTUM-INSPIRED OPTIMIZATION
          </span>
          <h1 className="mt-5 font-display font-bold text-3xl xl:text-4xl leading-tight text-gray-50">
            Operate your fleet with intelligent routing
          </h1>
          <p className="mt-4 text-gray-400 text-sm leading-relaxed max-w-md">
            Sign in to load live network conditions, run the QPSO optimizer, and
            react to disruptions in real time &mdash; or create an account to get
            started.
          </p>
          <ul className="mt-7 space-y-3">
            {HIGHLIGHTS.map(item => (
              <li key={item} className="flex items-center gap-2.5 text-sm text-gray-300">
                <CheckCircle2 className="w-4 h-4 text-[#6B9A57] flex-shrink-0" aria-hidden="true" />
                {item}
              </li>
            ))}
          </ul>
        </div>

        {/* Auth card */}
        <div className="w-full max-w-md mx-auto landing-fade-up">
          <div className="clean-card rounded-2xl shadow-2xl p-6 sm:p-8">
            <div className="mb-6">
              <h2 className="font-display font-bold text-xl sm:text-2xl text-gray-50">
                {title}
              </h2>
              <p className="mt-1.5 text-sm text-gray-400">
                {subtitle}
              </p>
            </div>

            {notice && mode === 'login' && (
              <p role="status" className="mb-4 text-xs text-[#9FC589] bg-[#22301B]/60 border border-[#3A4A2E] rounded-lg px-3 py-2">
                {notice}
              </p>
            )}

            {mode === 'login' && (
              <LoginForm
                onSuccess={onAuthSuccess}
                onSwitchToRegister={() => { setNotice(null); setMode('register'); }}
                onForgotPassword={() => { setNotice(null); setMode('forgot'); }}
              />
            )}
            {mode === 'register' && (
              <RegisterForm
                onSuccess={onAuthSuccess}
                onSwitchToLogin={() => goToLogin()}
              />
            )}
            {mode === 'forgot' && (
              <ForgotPasswordForm
                onBackToLogin={() => goToLogin()}
                onContinueToReset={(token) => {
                  setContinuedResetToken(token);
                  setMode('reset');
                }}
              />
            )}
            {mode === 'reset' && (
              <ResetPasswordForm
                token={continuedResetToken}
                onSuccess={(message) => goToLogin(message)}
                onBackToLogin={() => goToLogin()}
              />
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
