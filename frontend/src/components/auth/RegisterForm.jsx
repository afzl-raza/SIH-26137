import React, { useState } from 'react';
import { Loader2 } from 'lucide-react';
import FormField from './FormField';
import PasswordField from './PasswordField';
import SelectField from './SelectField';
import {
  validateEmail,
  validatePassword,
  validateRequired,
  validateConfirmPassword,
  PASSWORD_MIN_LENGTH
} from '../../lib/authValidation';
import { POSITION_OPTIONS } from '../../lib/positions';
import { register } from '../../lib/authService';

const EMPTY_FORM = { name: '', position: '', company: '', email: '', password: '', confirmPassword: '' };

export default function RegisterForm({ onSuccess, onSwitchToLogin }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  const update = (field) => (e) => setForm(f => ({ ...f, [field]: e.target.value }));

  const validate = () => {
    const next = {
      name: validateRequired(form.name, 'Name'),
      position: validateRequired(form.position, 'Position'),
      company: validateRequired(form.company, 'Company name'),
      email: validateEmail(form.email),
      password: validatePassword(form.password),
      confirmPassword: validateConfirmPassword(form.password, form.confirmPassword)
    };
    setErrors(next);
    return Object.values(next).every(v => !v);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError(null);
    if (!validate()) return;

    setSubmitting(true);
    try {
      const user = await register({
        name: form.name.trim(),
        position: form.position,
        company: form.company.trim(),
        email: form.email.trim(),
        password: form.password
      });
      onSuccess?.(user);
    } catch (err) {
      setFormError(err.message || 'Account creation failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <FormField
        id="register-name"
        label="Name"
        value={form.name}
        onChange={update('name')}
        error={errors.name}
        placeholder="Jane Doe"
        autoComplete="name"
        required
      />
      <SelectField
        id="register-position"
        label="Position"
        value={form.position}
        onChange={update('position')}
        error={errors.position}
        options={POSITION_OPTIONS}
        required
      />
      <FormField
        id="register-company"
        label="Company Name"
        value={form.company}
        onChange={update('company')}
        error={errors.company}
        placeholder="Acme Logistics"
        autoComplete="organization"
        required
      />
      <FormField
        id="register-email"
        label="Email"
        type="email"
        value={form.email}
        onChange={update('email')}
        error={errors.email}
        placeholder="you@company.com"
        autoComplete="email"
        required
      />
      <PasswordField
        id="register-password"
        label="Password"
        value={form.password}
        onChange={update('password')}
        error={errors.password}
        placeholder="Create a password"
        autoComplete="new-password"
        hint={`Password must be at least ${PASSWORD_MIN_LENGTH} characters.`}
        required
      />
      <PasswordField
        id="register-confirm-password"
        label="Confirm Password"
        value={form.confirmPassword}
        onChange={update('confirmPassword')}
        error={errors.confirmPassword}
        placeholder="Re-enter your password"
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
        {submitting ? 'Creating account...' : 'Create Account'}
      </button>

      <p className="text-center text-sm text-gray-400">
        Already have an account?{' '}
        <button
          type="button"
          onClick={onSwitchToLogin}
          className="text-[#E8A93A] hover:text-[#F0C271] font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-[#C6602E] rounded"
        >
          Login
        </button>
      </p>
    </form>
  );
}
