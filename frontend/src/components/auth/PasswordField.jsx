import React, { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

// Password input, masked by default (never rendered as plain text unless
// the viewer explicitly toggles visibility) with an optional helper hint
// below it (e.g. the minimum-length rule) shown when there's no error.
export default function PasswordField({
  id,
  label,
  value,
  onChange,
  error,
  placeholder,
  required = false,
  autoComplete,
  hint
}) {
  const [visible, setVisible] = useState(false);

  return (
    <div>
      <label htmlFor={id} className="block text-xs font-semibold text-gray-300 mb-1.5">
        {label}
        {required && <span className="text-[#C1443B] ml-0.5" aria-hidden="true">*</span>}
      </label>
      <div className="relative">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          autoComplete={autoComplete}
          required={required}
          aria-required={required}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
          className={`w-full bg-[#26221D] border rounded-lg pl-3.5 pr-11 py-2.5 text-sm text-gray-100 placeholder-gray-500 outline-none transition-colors focus:border-[#C6602E] focus-visible:ring-2 focus-visible:ring-[#C6602E]/40 ${
            error ? 'border-[#C1443B]' : 'border-[#3A342E]'
          }`}
        />
        <button
          type="button"
          onClick={() => setVisible(v => !v)}
          className="absolute inset-y-0 right-0 flex items-center px-3 text-gray-500 hover:text-gray-300 transition-colors focus-visible:ring-2 focus-visible:ring-[#C6602E] rounded-r-lg"
          aria-label={visible ? 'Hide password' : 'Show password'}
        >
          {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>
      {error ? (
        <p id={`${id}-error`} role="alert" className="mt-1.5 text-xs text-[#E8918A]">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="mt-1.5 text-xs text-gray-500">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
