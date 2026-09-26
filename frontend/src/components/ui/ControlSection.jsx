import React from 'react';
import { cx } from '../../lib/cx';

// Numbered section header used to group related controls in the
// Engineering Control Room (Part 3/20 of the design brief) - purely a
// presentational wrapper, no state of its own.
export default function ControlSection({ index, title, icon: Icon, children, className = '' }) {
  return (
    <section className={cx('space-y-2', className)}>
      <div className="flex items-center gap-1.5 text-gray-300 font-semibold uppercase tracking-wider text-[10px] border-b border-[#332E29]/60 pb-1.5">
        {index != null && <span className="text-[#C6602E] font-mono">{String(index).padStart(2, '0')}</span>}
        {Icon && <Icon size={12} className="text-gray-400 flex-shrink-0" />}
        <span>{title}</span>
      </div>
      <div className="space-y-2">{children}</div>
    </section>
  );
}
