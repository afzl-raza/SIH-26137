import React from 'react';
import { cx } from '../../lib/cx';

const VARIANTS = {
  tertiary: 'bg-transparent hover:bg-[#26221D]/60 text-gray-400 hover:text-gray-200',
  destructive: 'bg-transparent hover:bg-[#3A1C18]/60 text-[#E8918A] hover:text-white'
};

export default function IconButton({
  variant = 'tertiary',
  icon: Icon,
  iconSize = 14,
  children,
  className = '',
  ...rest
}) {
  return (
    <button
      type="button"
      className={cx(
        'inline-flex items-center justify-center rounded-md w-7 h-7 flex-shrink-0 transition-colors duration-150',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C6602E]',
        'disabled:opacity-40 disabled:cursor-not-allowed',
        VARIANTS[variant] || VARIANTS.tertiary,
        className
      )}
      {...rest}
    >
      {Icon ? <Icon size={iconSize} /> : children}
    </button>
  );
}
