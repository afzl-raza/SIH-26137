import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import { CheckCircle2, AlertCircle, X } from 'lucide-react';
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
    const { tone = 'success', duration = 4200, detail } = opts;
    setToasts(prev => [...prev, { id, message, detail, tone }]);
    timers.current[id] = setTimeout(() => dismiss(id), duration);
    return id;
  }, [dismiss]);

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="fixed top-4 right-4 z-[2000] flex flex-col gap-2 max-w-[320px] w-[calc(100%-2rem)] sm:w-[320px] pointer-events-none">
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
