import React from 'react';
import { cx } from '../../lib/cx';

// One button component for every action in the app instead of each call
// site hand-rolling its own Tailwind string. Variants map to the same
// colors the app already used per action type (see tailwind.config.js /
// existing call sites) - this consolidates them, it doesn't invent new ones.
const VARIANTS = {
  primary: {
    base: 'bg-[#C6602E] hover:bg-[#B0552A] text-white border border-transparent',
    ring: 'focus-visible:ring-[#C6602E]'
  },
  secondary: {
    base: 'bg-[#1E2A33]/60 hover:bg-[#1E2A33] border border-[#2E4A56] text-[#8FBAC9]',
    ring: 'focus-visible:ring-[#5D7A9E]'
  },
  tertiary: {
    base: 'bg-transparent hover:bg-[#26221D]/60 border border-transparent text-gray-400 hover:text-gray-200',
    ring: 'focus-visible:ring-[#C6602E]'
  },
  destructive: {
    base: 'bg-[#3A1C18]/80 hover:bg-[#3A1C18] border border-[#5A2C26] text-[#E8918A]',
    ring: 'focus-visible:ring-[#C1443B]'
  },
  warning: {
    base: 'bg-[#3A2E14]/80 hover:bg-[#3A2E14] border border-[#5A4A22] text-[#E8C578]',
    ring: 'focus-visible:ring-[#E8A93A]'
  },
  success: {
    base: 'bg-[#22301B]/80 hover:bg-[#22301B] border border-[#3A4A2E] text-[#9FC589]',
    ring: 'focus-visible:ring-[#6B9A57]'
  }
};

const SIZES = {
  sm: 'text-[10px] py-1 px-2 gap-1 rounded',
  md: 'text-[11px] py-1.5 px-3 gap-1.5 rounded-md',
  lg: 'text-sm py-2.5 px-4 gap-2 rounded-md font-bold'
};

export default function Button({
  variant = 'tertiary',
  size = 'md',
  icon: Icon,
  loading = false,
  loadingText,
  disabledHint,
  fullWidth = true,
  className = '',
  children,
  disabled,
  type = 'button',
  ...rest
}) {
  const v = VARIANTS[variant] || VARIANTS.tertiary;
  const isDisabled = Boolean(disabled) || loading;

  return (
    <div className={fullWidth ? 'w-full' : 'inline-block'}>
      <button
        type={type}
        disabled={isDisabled}
        className={cx(
          'flex items-center justify-center transition-colors duration-150 select-none',
          'disabled:opacity-40 disabled:cursor-not-allowed',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[#171513]',
          fullWidth ? 'w-full' : '',
          v.base,
          v.ring,
          SIZES[size],
          className
        )}
        {...rest}
      >
        {loading ? (
          <>
            <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin flex-shrink-0" />
            <span>{loadingText || children}</span>
          </>
        ) : (
          <>
            {Icon && <Icon size={size === 'lg' ? 16 : 12} className="flex-shrink-0" />}
            <span>{children}</span>
          </>
        )}
      </button>
      {/* Visible disabled reason instead of relying on a hover-only `title`
          attribute, which touch/keyboard users never see (Part 9/22). */}
      {isDisabled && !loading && disabledHint && (
        <p className="text-[9px] text-gray-600 mt-1 leading-snug">{disabledHint}</p>
      )}
    </div>
  );
}
