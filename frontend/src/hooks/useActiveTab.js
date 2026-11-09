import { useState, useEffect } from 'react';

const VALID_KEYS = new Set(['trips', 'favorites', 'airports', 'flights', 'settings']);

export function useActiveTab(navKeys) {
  const [tab, setTab] = useState('favorites');
  useEffect(() => {
    const handlePop = () => {
      const pathTab = window.location.pathname.replace(/^\//, '');
      if (VALID_KEYS.has(pathTab) || navKeys.find(n => n.key === pathTab)) setTab(pathTab);
    };
    window.addEventListener('popstate', handlePop);
    const initial = window.location.pathname.replace(/^\//, '');
    if (initial && navKeys.find(n => n.key === initial)) setTab(initial);
    return () => window.removeEventListener('popstate', handlePop);
  }, [navKeys]);
  return [tab, setTab];
}
