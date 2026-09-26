import React from 'react';
import { cx } from '../../lib/cx';

const TONES = {
  neutral: 'bg-[#26221D] text-gray-300 border-[#3A342E]',
  accent: 'bg-[#3A2318] text-[#E8A578] border-[#5A3A22]',
  amber: 'bg-[#3A2E14] text-[#E8C578] border-[#5A4A22]',
  green: 'bg-[#22301B] text-[#9FC589] border-[#3A4A2E]',
  red: 'bg-[#3A1C18] text-[#E8918A] border-[#5A2C26]'
};

export default function Badge({ tone = 'neutral', pulse = false, dotColor, children, className = '', ...rest }) {
  return (
    <span
      className={cx(
        'px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide inline-flex items-center gap-1.5 border font-mono',
        TONES[tone] || TONES.neutral,
        pulse ? 'animate-pulse' : '',
        className
      )}
      {...rest}
    >
      {dotColor && <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: dotColor }} />}
      {children}
    </span>
  );
}
