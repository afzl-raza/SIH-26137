import React from 'react';
import { cx } from '../../lib/cx';

// Generic N-option toggle group. Replaces the hand-duplicated toggle-pair
// markup that previously existed separately for: network source,
// GIS/Graph view, vehicle filter, prototype/deployment, and the header's
// Executive/Engineering nav.
export default function SegmentedControl({
  options,
  value,
  onChange,
  disabled = false,
  className = '',
  itemClassName = ''
}) {
  return (
    <div
      className={cx('grid gap-1', className)}
      style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
      role="group"
    >
      {options.map(opt => {
        const isActive = value === opt.id;
        return (
          <button
            key={opt.id}
            type="button"
            onClick={() => onChange(opt.id)}
            disabled={disabled || opt.disabled}
            aria-pressed={isActive}
            title={opt.title}
            className={cx(
              'px-2 py-1 rounded border text-[10px] font-semibold transition-colors flex items-center justify-center gap-1 whitespace-nowrap',
              'disabled:opacity-40 disabled:cursor-not-allowed',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C6602E]',
              isActive
                ? (opt.activeClassName || 'bg-[#C6602E] border-[#C6602E] text-white')
                : 'bg-[#26221D] border-[#3A342E] text-gray-400 hover:text-gray-200',
              itemClassName
            )}
            style={isActive && opt.activeColor ? { backgroundColor: opt.activeColor, borderColor: opt.activeColor, color: '#fff' } : undefined}
          >
            {opt.icon && <opt.icon size={11} className="flex-shrink-0" />}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
