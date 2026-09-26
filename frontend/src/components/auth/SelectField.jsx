import React from 'react';
import { ChevronDown } from 'lucide-react';

// Labeled dropdown, same visual language as FormField/PasswordField. Used
// today for the registration form's Position field.
export default function SelectField({
  id,
  label,
  value,
  onChange,
  error,
  options,
  required = false,
  placeholder = 'Select...'
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-semibold text-gray-300 mb-1.5">
        {label}
        {required && <span className="text-[#C1443B] ml-0.5" aria-hidden="true">*</span>}
      </label>
      <div className="relative">
        <select
          id={id}
          value={value}
          onChange={onChange}
          required={required}
          aria-required={required}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
          className={`w-full appearance-none bg-[#26221D] border rounded-lg pl-3.5 pr-9 py-2.5 text-sm outline-none transition-colors focus:border-[#C6602E] focus-visible:ring-2 focus-visible:ring-[#C6602E]/40 ${
            value ? 'text-gray-100' : 'text-gray-500'
          } ${error ? 'border-[#C1443B]' : 'border-[#3A342E]'}`}
        >
          <option value="" disabled>{placeholder}</option>
          {options.map(opt => (
            <option key={opt} value={opt} className="bg-[#26221D] text-gray-100">
              {opt}
            </option>
          ))}
        </select>
        <ChevronDown className="w-4 h-4 text-gray-500 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
      </div>
      {error && (
        <p id={`${id}-error`} role="alert" className="mt-1.5 text-xs text-[#E8918A]">
          {error}
        </p>
      )}
    </div>
  );
}
