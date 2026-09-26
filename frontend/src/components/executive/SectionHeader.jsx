import React from 'react';

export default function SectionHeader({ icon: Icon, title }) {
  return (
    <div className="flex items-center gap-2 text-gray-300 font-semibold uppercase tracking-wider text-xs">
      {Icon && <Icon size={14} className="text-[#C6602E] flex-shrink-0" />}
      <span>{title}</span>
    </div>
  );
}
