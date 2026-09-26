import React from 'react';
import { Search, HelpCircle, Bell } from 'lucide-react';

// Search/help/notifications are static decoration this round - approved:
// this prototype has one operator and no real notification stream, so these
// are visual chrome, not a functioning search or inbox.
export default function OverviewTopBar() {
  return (
    <div className="h-16 flex-shrink-0 border-b border-[#3B342A] bg-[#171512] flex items-center gap-4 px-6 font-sans">
      <div
        title="Search is not wired up in this prototype"
        className="flex-1 max-w-md flex items-center gap-2 bg-[#211E1A] border border-[#3B342A] rounded-lg px-3 py-2 text-[#817970] cursor-default"
      >
        <Search size={15} />
        <span className="text-[13px] flex-1">Search vehicles, routes, or destinations…</span>
        <kbd className="text-[10px] bg-[#312B24] border border-[#3B342A] rounded px-1.5 py-0.5">⌘K</kbd>
      </div>

      <div className="flex-1" />

      <button type="button" title="Not wired up in this prototype" className="flex items-center gap-1.5 text-[13px] text-[#B9B0A5] cursor-default">
        <HelpCircle size={16} />
        Help
      </button>
      <button type="button" title="Not wired up in this prototype" className="text-[#B9B0A5] cursor-default p-1.5">
        <Bell size={16} />
      </button>
      <div className="flex items-center gap-2 pl-3 border-l border-[#3B342A]">
        <div className="w-8 h-8 rounded-full bg-[#2E2742] flex items-center justify-center text-[11px] font-bold text-[#A98AFF]">
          AM
        </div>
        <div className="leading-tight hidden sm:block">
          <div className="text-[12px] text-[#FFF9F1] font-semibold">Alex Morgan</div>
          <div className="text-[10px] text-[#817970]">Route operator</div>
        </div>
      </div>
    </div>
  );
}
