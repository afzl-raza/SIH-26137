import React, { useState } from 'react';
import { Loader2 } from 'lucide-react';
import FormField from './FormField';
import { validateEmail } from '../../lib/authValidation';
import { forgotPassword } from '../../lib/authService';

// The backend always returns the same neutral message regardless of
// whether the email has an account (see main.py's /api/auth/forgot-password)
// - this form never learns, and never displays, whether a given email is
// registered.
//
// `dev_reset_token` on the response only exists when the backend is running
// outside production (no email-delivery infrastructure exists in this
// repository - see auth/store.py's PasswordResetStore docstring), so the
// "continue to reset" shortcut below is naturally absent in production
// without any UI branching here.
export default function ForgotPasswordForm({ onBackToLogin, onContinueToReset }) {
  const [email, setEmail] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState(null);
  const [devResetToken, setDevResetToken] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    const emailError = validateEmail(email);
    if (emailError) {
      setError(emailError);
      return;
    }

    setSubmitting(true);
    try {
      const data = await forgotPassword({ email: email.trim() });
      setMessage(data.message);
      setDevResetToken(data.dev_reset_token || null);
    } catch (err) {
      setError(err.message || "We couldn't process that request. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <FormField
          id="forgot-email"
          label="Email"
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          error={error}
          placeholder="you@company.com"
          autoComplete="email"
          required
        />

        <button
          type="submit"
          disabled={submitting}
          className="w-full py-2.5 bg-[#C6602E] hover:bg-[#B0552A] text-white rounded-lg text-sm font-bold flex items-center justify-center gap-2 transition-colors disabled:opacity-60 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-[#C6602E] focus-visible:ring-offset-2 focus-visible:ring-offset-[#1E1B18]"
        >
          {submitting && <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />}
          {submitting ? 'Sending instructions...' : 'Send reset instructions'}
        </button>
      </form>

      {message && (
        <p role="status" className="text-xs text-[#9FC589] bg-[#22301B]/60 border border-[#3A4A2E] rounded-lg px-3 py-2">
          {message}
        </p>
      )}

      {devResetToken && (
        <div className="rounded-lg border border-[#5A4A22] bg-[#3A2E14]/60 px-3 py-2.5">
          <p className="text-[10px] font-mono font-semibold uppercase tracking-wide text-[#E8C588]">
            Development environment only
          </p>
          <p className="mt-1 text-xs text-gray-300">
            No email service is configured in this environment, so continue directly below instead.
          </p>
          <button
            type="button"
            onClick={() => onContinueToReset?.(devResetToken)}
            className="mt-2 text-xs font-semibold text-[#E8A93A] hover:text-[#F0C271] transition-colors focus-visible:ring-2 focus-visible:ring-[#C6602E] rounded"
          >
            Continue to reset password &rarr;
          </button>
        </div>
      )}

      <p className="text-center text-sm text-gray-400">
        <button
          type="button"
          onClick={onBackToLogin}
          className="text-[#E8A93A] hover:text-[#F0C271] font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-[#C6602E] rounded"
        >
          Back to login
        </button>
      </p>
    </div>
  );
}
