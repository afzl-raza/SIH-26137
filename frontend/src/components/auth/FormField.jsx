import React from 'react';

// Labeled text input with an inline error message, styled to match the
// dashboard's existing form controls (ControlPanel.jsx uses the same
// bg/border/focus tokens on its inputs and selects).
export default function FormField({
  id,
  label,
  type = 'text',
  value,
  onChange,
  error,
  placeholder,
  required = false,
  autoComplete
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-semibold text-gray-300 mb-1.5">
        {label}
        {required && <span className="text-[#C1443B] ml-0.5" aria-hidden="true">*</span>}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required={required}
        aria-required={required}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        className={`w-full bg-[#26221D] border rounded-lg px-3.5 py-2.5 text-sm text-gray-100 placeholder-gray-500 outline-none transition-colors focus:border-[#C6602E] focus-visible:ring-2 focus-visible:ring-[#C6602E]/40 ${
          error ? 'border-[#C1443B]' : 'border-[#3A342E]'
        }`}
      />
      {error && (
        <p id={`${id}-error`} role="alert" className="mt-1.5 text-xs text-[#E8918A]">
          {error}
        </p>
      )}
    </div>
  );
}
