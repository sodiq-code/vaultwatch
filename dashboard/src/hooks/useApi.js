import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Generic async hook for data fetching with loading/error states.
 * Wraps any async function and provides reactive state management.
 *
 * @param {Function} asyncFn - The async function to call
 * @param {Array} deps - Dependencies that trigger refetch when changed
 * @param {Object} opts - Options: { immediate: true, fallbackData: null }
 * @returns {{ data, loading, error, refetch }}
 */
export function useApi(asyncFn, deps = [], opts = {}) {
  const { immediate = true, fallbackData = null } = opts;
  const [data, setData] = useState(fallbackData);
  const [loading, setLoading] = useState(immediate);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  const execute = useCallback(async (...args) => {
    setLoading(true);
    setError(null);
    try {
      const result = await asyncFn(...args);
      if (mountedRef.current) {
        setData(result);
        setLoading(false);
      }
      return result;
    } catch (err) {
      if (mountedRef.current) {
        setError(err.message || 'An error occurred');
        setLoading(false);
        if (fallbackData) setData(fallbackData);
      }
      throw err;
    }
  }, deps);

  useEffect(() => {
    mountedRef.current = true;
    if (immediate) execute();
    return () => { mountedRef.current = false; };
  }, [execute, immediate]);

  return { data, loading, error, refetch: execute, setData };
}

/**
 * Hook for managing a single async action (e.g., form submissions).
 * Does NOT auto-execute — call trigger() manually.
 *
 * @param {Function} asyncFn - The async function to call
 * @returns {{ data, loading, error, trigger }}
 */
export function useAsyncAction(asyncFn) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const trigger = useCallback(async (...args) => {
    setLoading(true);
    setError(null);
    try {
      const result = await asyncFn(...args);
      setData(result);
      setLoading(false);
      return result;
    } catch (err) {
      setError(err.message || 'An error occurred');
      setLoading(false);
      throw err;
    }
  }, [asyncFn]);

  return { data, loading, error, trigger };
}
