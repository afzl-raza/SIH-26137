import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import { CheckCircle2, AlertCircle, X, ArrowDown } from 'lucide-react';
import { cx } from '../../lib/cx';

const ToastContext = createContext(null);
let idCounter = 0;

// Minimal context-based toast stack - no library dependency. Replaces
// nothing (the app previously had no transient success feedback at all,
// only a persistent error banner in App.jsx), so this is pure addition.
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef({});

  const dismiss = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
    clearTimeout(timers.current[id]);
    delete timers.current[id];
  }, []);

  const toast = useCallback((message, opts = {}) => {
    const id = ++idCounter;
    const { tone = 'success', duration = 4200, detail, action } = opts;
    setToasts(prev => [...prev, { id, message, detail, tone, action }]);
    timers.current[id] = setTimeout(() => dismiss(id), duration);
    return id;
  }, [dismiss]);

  return (
    <ToastContext.Provider value={toast}>
      {children}
      {/* Bottom-centre on phones, below the sticky header on desktop - never
          on top of the nav. */}
      <div className="fixed bottom-4 left-1/2 -translate-x-1/2 sm:translate-x-0 sm:left-auto sm:bottom-auto sm:top-20 sm:right-4 z-[2000] flex flex-col-reverse sm:flex-col gap-2 w-[calc(100%-2rem)] sm:w-[320px] pointer-events-none">
        {toasts.map(t => (
          <div
            key={t.id}
            className={cx(
              'toast-item pointer-events-auto clean-panel border rounded-lg shadow-2xl px-3 py-2.5 flex items-start gap-2 text-xs',
              t.tone === 'error' ? 'border-[#5A2C26]' : 'border-[#332E29]'
            )}
          >
            {t.tone === 'error'
              ? <AlertCircle size={14} className="text-[#E8918A] flex-shrink-0 mt-0.5" />
              : <CheckCircle2 size={14} className="text-[#6B9A57] flex-shrink-0 mt-0.5" />}
            <div className="flex-1 min-w-0">
              <p className="text-gray-200 font-semibold leading-snug">{t.message}</p>
              {t.detail && <p className="text-gray-500 text-[10px] mt-0.5 leading-snug">{t.detail}</p>}
              {t.action && (
                <button
                  onClick={() => { t.action.onClick(); dismiss(t.id); }}
                  className="mt-1.5 flex items-center gap-1 text-[10px] font-semibold text-[#E8A578] hover:text-[#C6602E] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C6602E] rounded"
                >
                  {t.action.label}
                  <ArrowDown size={11} className="animate-bounce" />
                </button>
              )}
            </div>
            <button
              onClick={() => dismiss(t.id)}
              className="text-gray-600 hover:text-gray-300 flex-shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C6602E] rounded"
              aria-label="Dismiss notification"
            >
              <X size={12} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within a ToastProvider');
  return ctx;
}
