import React, { useEffect, useRef, useState } from 'react';
import { Search, HelpCircle, Bell, LogOut, ChevronDown } from 'lucide-react';

// Search/help/notifications are static decoration this round - approved:
// this prototype has one operator and no real notification stream, so these
// are visual chrome, not a functioning search or inbox.

function initialsFor(name, email) {
  const source = (name || '').trim();
  if (source) {
    const parts = source.split(/\s+/).filter(Boolean);
    const letters = parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : parts[0].slice(0, 2);
    return letters.toUpperCase();
  }
  const localPart = (email || '').split('@')[0];
  return localPart ? localPart.slice(0, 2).toUpperCase() : '?';
}

export default function OverviewTopBar({ user, onLogout }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);
  const buttonRef = useRef(null);

  const displayName = user?.name?.trim() || user?.email || 'Fleet operator';
  const displayPosition = user?.position || 'Fleet operator';
  const initials = initialsFor(user?.name, user?.email);

  useEffect(() => {
    if (!menuOpen) return;

    function handlePointerDown(e) {
      if (menuRef.current?.contains(e.target) || buttonRef.current?.contains(e.target)) return;
      setMenuOpen(false);
    }
    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        setMenuOpen(false);
        buttonRef.current?.focus();
      }
    }
    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [menuOpen]);

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

      <div className="relative pl-3 border-l border-[#3B342A]">
        <button
          ref={buttonRef}
          type="button"
          onClick={() => setMenuOpen(v => !v)}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          aria-label={`Account menu for ${displayName}`}
          className="flex items-center gap-2 rounded-lg py-1 pl-1 pr-2 hover:bg-[#211E1A] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#FF7A1A] focus-visible:outline-offset-2"
        >
          <div className="w-8 h-8 rounded-full bg-[#2E2742] flex items-center justify-center text-[11px] font-bold text-[#A98AFF] flex-shrink-0">
            {initials}
          </div>
          <div className="leading-tight hidden sm:block text-left">
            <div className="text-[12px] text-[#FFF9F1] font-semibold truncate max-w-[140px]">{displayName}</div>
            <div className="text-[10px] text-[#817970] truncate max-w-[140px]">{displayPosition}</div>
          </div>
          <ChevronDown size={14} className="text-[#817970] hidden sm:block flex-shrink-0" />
        </button>

        {menuOpen && (
          <div
            ref={menuRef}
            role="menu"
            aria-label="Account"
            className="absolute right-0 top-full mt-2 w-64 bg-[#211E1A] border border-[#3B342A] rounded-xl shadow-2xl py-2 z-50"
          >
            <div className="px-3.5 pb-2 mb-1 border-b border-[#3B342A]">
              <div className="text-[10px] font-bold uppercase tracking-wider text-[#817970] mb-1.5">
                Account
              </div>
              <div className="text-[13px] text-[#FFF9F1] font-semibold truncate">{displayName}</div>
              {user?.email && (
                <div className="text-[11px] text-[#B9B0A5] truncate mt-0.5">{user.email}</div>
              )}
              <div className="text-[11px] text-[#817970] truncate mt-0.5">{displayPosition}</div>
            </div>
            <button
              type="button"
              role="menuitem"
              onClick={() => { setMenuOpen(false); onLogout?.(); }}
              className="w-full flex items-center gap-2 px-3.5 py-2 text-[13px] text-[#E8918A] hover:bg-[#3A1C18]/60 transition-colors text-left"
            >
              <LogOut size={14} />
              Sign out
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
