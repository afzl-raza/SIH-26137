import React, { useState } from 'react';
import { Loader2 } from 'lucide-react';
import FormField from './FormField';
import PasswordField from './PasswordField';
import { validateEmail, validatePassword } from '../../lib/authValidation';
import { login } from '../../lib/authService';

export default function LoginForm({ onSuccess, onSwitchToRegister, onForgotPassword }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  const validate = () => {
    const next = {
      email: validateEmail(email),
      password: validatePassword(password)
    };
    setErrors(next);
    return !next.email && !next.password;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError(null);
    if (!validate()) return;

    setSubmitting(true);
    try {
      const user = await login({ email: email.trim(), password });
      onSuccess?.(user);
    } catch (err) {
      setFormError(err.message || 'Login failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <FormField
        id="login-email"
        label="Email"
        type="email"
        value={email}
        onChange={e => setEmail(e.target.value)}
        error={errors.email}
        placeholder="you@company.com"
        autoComplete="email"
        required
      />
      <div>
        <PasswordField
          id="login-password"
          label="Password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          error={errors.password}
          placeholder="Enter your password"
          autoComplete="current-password"
          required
        />
        <div className="mt-1.5 text-right">
          <button
            type="button"
            onClick={onForgotPassword}
            className="text-xs text-gray-400 hover:text-[#E8A93A] transition-colors focus-visible:ring-2 focus-visible:ring-[#C6602E] rounded"
          >
            Forgot password?
          </button>
        </div>
      </div>

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
        {submitting ? 'Signing in...' : 'Login'}
      </button>

      <p className="text-center text-sm text-gray-400">
        Don&rsquo;t have an account?{' '}
        <button
          type="button"
          onClick={onSwitchToRegister}
          className="text-[#E8A93A] hover:text-[#F0C271] font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-[#C6602E] rounded"
        >
          Create account
        </button>
      </p>
    </form>
  );
}
