// Hook for persisting component state in browser localStorage.
// Unlike useTripConfigs (which stores configs on the server), this keeps
// UI preferences local to each browser.

import { useState, useEffect } from 'react';

export function useLocalStorage(key, defaultValue) {
  // Create a unique key for this app to avoid conflicts
  const storageKey = `skybreak.${key}`;

  // State to store our value
  const [storedValue, setStoredValue] = useState(() => {
    try {
      // Get from localStorage by key
      const item = window.localStorage.getItem(storageKey);
      // Parse stored json or return defaultValue
      return item ? JSON.parse(item) : defaultValue;
    } catch (error) {
      // If error also return defaultValue
      console.error(error);
      return defaultValue;
    }
  });

  // Return a wrapped version of useState's setter function that persists the new value to localStorage
  const setValue = (value) => {
    try {
      // Allow value to be a function so we have same API as useState
      const valueToStore = value instanceof Function ? value(storedValue) : value;
      // Save state
      setStoredValue(valueToStore);
      // Save to localStorage
      window.localStorage.setItem(storageKey, JSON.stringify(valueToStore));
    } catch (error) {
      console.error(error);
    }
  };

  return [storedValue, setValue];
}

export function useLocalStorageObject(key, defaultValue) {
  // Helper for objects - ensures we don't lose keys when partial updates happen
  const [value, setValue] = useLocalStorage(key, defaultValue);

  const setObjectValue = (updater) => {
    setValue(prev => {
      const newValue = typeof updater === 'function' ? updater(prev || {}) : updater;
      return { ...prev || {}, ...newValue };
    });
  };

  return [value, setObjectValue];
}