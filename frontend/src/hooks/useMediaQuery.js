import { useState, useEffect } from 'react';

/**
 * D2 — Responsive media query hook (SSR-safe, change-listener based).
 * Replaces all ad-hoc `window.innerWidth` checks.
 *
 * @param {string} query - Media query string (e.g., '(max-width: 767px)').
 * @returns {boolean} Whether the query matches.
 */
export function useMediaQuery(query) {
  const [matches, setMatches] = useState(() => {
    // SSR-safe: return false on server
    if (typeof window === 'undefined') return false;
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const mql = window.matchMedia(query);

    // Listener to update state on breakpoint changes
    const handleChange = (e) => setMatches(e.matches);

    mql.addEventListener('change', handleChange);
    // Initial sync (in case the listener doesn't fire immediately)
    setMatches(mql.matches);

    return () => {
      mql.removeEventListener('change', handleChange);
    };
  }, [query]);

  return matches;
}

// --- Predefined breakpoints for convenience ---

/** Returns true when viewport is ≥ 768px (tablet+). */
export function useIsMediumOrAbove() {
  return useMediaQuery('(min-width: 768px)');
}

/** Returns true when viewport is ≥ 1024px (desktop+). */
export function useIsLargeOrAbove() {
  return useMediaQuery('(min-width: 1024px)');
}

/** Returns true when viewport < 640px (mobile). */
export function useIsSmallScreen() {
  return useMediaQuery('(max-width: 639px)');
}

/** Returns true when viewport < 768px (mobile/tablet). */
export function useIsMobileOrTablet() {
  return useMediaQuery('(max-width: 767px)');
}