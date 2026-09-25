import React, { useState } from 'react';
import { Menu, X } from 'lucide-react';
import Logo from '../Logo';

const NAV_LINKS = [
  { href: '#technology', label: 'Technology' },
  { href: '#platform', label: 'Platform' }
];

export default function LandingNavbar({ onEnterApp }) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-[#332E29] bg-[#0D0C0B]/85 backdrop-blur-md">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="bg-[#1E1B18] border border-[#3A342E] p-1.5 rounded-lg">
            <Logo size={20} />
          </div>
          <div className="flex items-center gap-2">
            <span className="font-display font-bold text-sm sm:text-base tracking-wide text-gray-100">
              Q-DFRO
            </span>
            <span className="hidden sm:inline text-[10px] bg-[#3A2318] text-[#E8A93A] border border-[#5A3A22] px-1.5 py-0.5 rounded font-mono font-semibold">
              QPSO ENGINE
            </span>
          </div>
        </div>

        <nav className="hidden md:flex items-center gap-8" aria-label="Primary">
          {NAV_LINKS.map(link => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm text-gray-400 hover:text-gray-100 transition-colors"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden md:block">
          <button
            onClick={onEnterApp}
            className="bg-[#C6602E] hover:bg-[#B0552A] text-white text-sm font-semibold px-4 py-2 rounded-lg shadow-md shadow-[#C6602E]/20 transition-colors"
          >
            Get Started
          </button>
        </div>

        <button
          className="md:hidden text-gray-300 hover:text-white p-1.5"
          onClick={() => setMenuOpen(v => !v)}
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
        >
          {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {menuOpen && (
        <div className="md:hidden border-t border-[#332E29] bg-[#0D0C0B] px-4 pb-4 pt-2 space-y-3">
          {NAV_LINKS.map(link => (
            <a
              key={link.href}
              href={link.href}
              onClick={() => setMenuOpen(false)}
              className="block text-sm text-gray-300 hover:text-white py-1"
            >
              {link.label}
            </a>
          ))}
          <button
            onClick={() => { setMenuOpen(false); onEnterApp(); }}
            className="w-full bg-[#C6602E] hover:bg-[#B0552A] text-white text-sm font-semibold px-4 py-2.5 rounded-lg transition-colors"
          >
            Get Started
          </button>
        </div>
      )}
    </header>
  );
}
