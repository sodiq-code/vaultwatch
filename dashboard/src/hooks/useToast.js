import { useState, useCallback, useRef } from 'react';

let toastIdCounter = 0;

/**
 * Toast notification system hook.
 * Provides transient success/error/warning/info notifications.
 *
 * @returns {{ toasts, addToast, removeToast }}
 */
export function useToast() {
  const [toasts, setToasts] = useState([]);
  const timersRef = useRef({});

  const removeToast = useCallback((id) => {
    if (timersRef.current[id]) {
      clearTimeout(timersRef.current[id]);
      delete timersRef.current[id];
    }
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const addToast = useCallback(({ type = 'info', message, duration = 4000 }) => {
    const id = ++toastIdCounter;
    const toast = { id, type, message, createdAt: Date.now() };

    setToasts(prev => [...prev, toast]);

    if (duration > 0) {
      timersRef.current[id] = setTimeout(() => removeToast(id), duration);
    }

    return id;
  }, [removeToast]);

  return { toasts, addToast, removeToast };
}
