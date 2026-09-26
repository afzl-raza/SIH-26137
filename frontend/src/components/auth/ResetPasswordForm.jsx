import React, { useState } from 'react';
import { Loader2 } from 'lucide-react';
import PasswordField from './PasswordField';
import { validatePassword, validateConfirmPassword, PASSWORD_MIN_LENGTH } from '../../lib/authValidation';
import { resetPassword } from '../../lib/authService';

export default function ResetPasswordForm({ token, onSuccess, onBackToLogin }) {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  const validate = () => {
    const next = {
      password: validatePassword(password),
      confirmPassword: validateConfirmPassword(password, confirmPassword)
    };
    setErrors(next);
    return !next.password && !next.confirmPassword;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError(null);
    if (!validate()) return;

    setSubmitting(true);
    try {
      const data = await resetPassword({ token, newPassword: password });
      onSuccess?.(data.message);
    } catch (err) {
      setFormError(err.message || "We couldn't reset your password. Please request a new reset link.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <PasswordField
        id="reset-password"
        label="New Password"
        value={password}
        onChange={e => setPassword(e.target.value)}
        error={errors.password}
        placeholder="Create a new password"
        autoComplete="new-password"
        hint={`Password must be at least ${PASSWORD_MIN_LENGTH} characters.`}
        required
      />
      <PasswordField
        id="reset-confirm-password"
        label="Confirm New Password"
        value={confirmPassword}
        onChange={e => setConfirmPassword(e.target.value)}
        error={errors.confirmPassword}
        placeholder="Re-enter your new password"
        autoComplete="new-password"
        required
      />

      {formError && (
        <p role="alert" className="text-xs text-[#E8918A] bg-[#3A1C18]/60 border border-[#5A2C26] rounded-lg px-3 py-2">
          {formError}
        </p>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="w-full py-2.5 bg-[#C6602E] hover:bg-[#B0552A] text-white rounded-lg text-sm font-bold flex items-center justify-center gap-2 transition-colors disabled:opacity-60 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-[#C6602E] focus-visible:ring-offset-2 focus-visible:ring-offset-[#1E1B18]"
      >
        {submitting && <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />}
        {submitting ? 'Updating password...' : 'Reset Password'}
      </button>

      <p className="text-center text-sm text-gray-400">
        <button
          type="button"
          onClick={onBackToLogin}
          className="text-[#E8A93A] hover:text-[#F0C271] font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-[#C6602E] rounded"
        >
          Back to login
        </button>
      </p>
    </form>
  );
}
