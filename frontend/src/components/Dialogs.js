import React, { useState, useEffect, useCallback, useRef } from 'react';

/* ==========================================================================
   D10 — In-App Feedback System (replaces alert()/confirm())
   
   Exports:
   - `<ToastHost />`: renders a stack of toast notifications (info/success/error/warning)
   - `<ConfirmDialog />`: modal confirmation dialog (cancel/confirm buttons)
   - `useToast()`: hook to dispatch toasts from any component
   - `useConfirm()`: hook to show a confirm dialog and get a Promise<boolean>
   ========================================================================== */

// --- Toast types ---
const TOAST_TYPES = { INFO: 'info', SUCCESS: 'success', ERROR: 'error', WARNING: 'warning' };
const TOAST_COLORS = {
  info: '#38bdf8',
  success: '#10b981',
  error: '#ef4444',
  warning: '#f59e0b',
};

// --- Toast Host Component ---
export function ToastHost() {
  const [toasts, setToasts] = useState([]);
  const timers = useRef({});

  const addToast = useCallback((message, type = TOAST_TYPES.INFO, duration = 3000) => {
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev.slice(-4), { id, message, type }]);
    
    // Auto-dismiss after duration
    timers.current[id] = setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
      delete timers.current[id];
    }, duration);
    
    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
    if (timers.current[id]) {
      clearTimeout(timers.current[id]);
      delete timers.current[id];
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      Object.values(timers.current).forEach(clearTimeout);
    };
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 16,
      right: 16,
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
      maxWidth: 320,
      pointerEvents: 'none',
    }}>
      {toasts.map(toast => (
        <div key={toast.id} style={{
          background: 'rgba(30, 41, 59, 0.95)',
          borderLeft: `4px solid ${TOAST_COLORS[toast.type]}`,
          color: '#f1f5f9',
          padding: '12px 16px',
          borderRadius: 8,
          boxShadow: '0 4px 15px rgba(0,0,0,0.3)',
          fontSize: 14,
          fontWeight: 500,
          pointerEvents: 'auto',
          cursor: 'pointer',
          animation: 'slideIn 0.3s ease-out',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }} onClick={() => removeToast(toast.id)}>
          <span>{toast.message}</span>
          <span style={{ opacity: 0.6, fontSize: 18 }}>&times;</span>
        </div>
      ))}
    </div>
  );
}

// --- Confirm Dialog Component ---
export function ConfirmDialog({ isOpen, title, message, onConfirm, onCancel }) {
  const cancelRef = useRef(null);

  useEffect(() => {
    if (isOpen && cancelRef.current) {
      cancelRef.current.focus();
    }
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handleEscape = (e) => {
      if (e.key === 'Escape') onCancel?.();
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 10000,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'rgba(0, 0, 0, 0.6)',
      backdropFilter: 'blur(4px)',
    }}>
      <div style={{
        background: '#1e293b',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: 16,
        padding: 24,
        maxWidth: 400,
        width: '90%',
        boxShadow: '0 20px 60px rgba(0, 0, 0, 0.5)',
      }}>
        <h3 style={{ margin: '0 0 12px 0', fontSize: 18, fontWeight: 700, color: '#f8fafc' }}>
          {title}
        </h3>
        <p style={{ margin: '0 0 20px 0', fontSize: 14, color: '#cbd5e1', lineHeight: 1.5 }}>
          {message}
        </p>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
          <button ref={cancelRef} onClick={onCancel} style={{
            padding: '10px 20px',
            borderRadius: 10,
            border: '1px solid rgba(255, 255, 255, 0.15)',
            background: 'transparent',
            color: '#cbd5e1',
            fontWeight: 600,
            fontSize: 14,
            cursor: 'pointer',
          }}>
            Cancel
          </button>
          <button onClick={onConfirm} style={{
            padding: '10px 20px',
            borderRadius: 10,
            border: 'none',
            background: '#ef4444',
            color: '#fff',
            fontWeight: 700,
            fontSize: 14,
            cursor: 'pointer',
          }}>
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}

// --- useToast Hook ---
/**
 * Returns { toasts, info, success, error, warning, clearAll }.
 * Use in any component to display toast notifications.
 */
export function useToast() {
  const dispatchRef = useRef(null);

  const toast = useCallback((type, message, duration) => {
    if (dispatchRef.current) {
      dispatchRef.current(type, message, duration);
    }
  }, []);

  const registerDispatch = useCallback((fn) => {
    dispatchRef.current = fn;
  }, []);

  return {
    toast,
    info: (msg, dur) => toast(TOAST_TYPES.INFO, msg, dur),
    success: (msg, dur) => toast(TOAST_TYPES.SUCCESS, msg, dur),
    error: (msg, dur) => toast(TOAST_TYPES.ERROR, msg, dur),
    warning: (msg, dur) => toast(TOAST_TYPES.WARNING, msg, dur),
    registerDispatch,
  };
}

// --- useConfirm Hook ---
/**
 * Returns { showConfirm, confirmed }.
 * Use to replace window.confirm() with an in-app dialog.
 * 
 * Example:
 *   const { showConfirm } = useConfirm();
 *   const ok = await showConfirm('Delete all?', 'This cannot be undone.');
 *   if (ok) { /* proceed *\/ }
 */
export function useConfirm() {
  const [state, setState] = useState({ isOpen: false, title: '', message: '', resolve: null });

  const showConfirm = useCallback((title, message) => {
    return new Promise(resolve => {
      setState({ isOpen: true, title, message, resolve });
    });
  }, []);

  const handleConfirm = useCallback(() => {
    setState(prev => ({ ...prev, isOpen: false }));
    state.resolve?.(true);
  }, [state.resolve]);

  const handleCancel = useCallback(() => {
    setState(prev => ({ ...prev, isOpen: false }));
    state.resolve?.(false);
  }, [state.resolve]);

  return {
    ConfirmDialog: () => (
      <ConfirmDialog
        isOpen={state.isOpen}
        title={state.title || 'Confirm Action'}
        message={state.message}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    ),
    showConfirm,
  };
}

// --- Export ToastProvider for App-level integration ---
export function ToastProvider({ children }) {
  const { toast, registerDispatch } = useToast();
  const [toasts, setToasts] = useState([]);
  const timers = useRef({});

  useEffect(() => {
    registerDispatch((type, message, duration) => {
      const id = Date.now() + Math.random();
      setToasts(prev => [...prev.slice(-4), { id, message, type }]);
      timers.current[id] = setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
        delete timers.current[id];
      }, duration || 3000);
    });
  }, [registerDispatch]);

  // Listen for global showToast CustomEvents (App.js, AirportsTab, SettingsTab dispatch these)
  useEffect(() => {
    const handler = (e) => {
      const { message, type } = e.detail || {};
      if (!message) return;
      const id = Date.now() + Math.random();
      setToasts(prev => [...prev.slice(-4), { id, message, type: type || 'info' }]);
      timers.current[id] = setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
        delete timers.current[id];
      }, 3000);
    };
    window.addEventListener('showToast', handler);
    return () => window.removeEventListener('showToast', handler);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
    if (timers.current[id]) {
      clearTimeout(timers.current[id]);
      delete timers.current[id];
    }
  }, []);

  return (
    <>
      {children}
      <div style={{
        position: 'fixed',
        top: 16,
        right: 16,
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        maxWidth: 320,
        pointerEvents: 'none',
      }}>
        {toasts.map(t => (
          <div key={t.id} style={{
            background: 'rgba(30, 41, 59, 0.95)',
            borderLeft: `4px solid ${TOAST_COLORS[t.type]}`,
            color: '#f1f5f9',
            padding: '12px 16px',
            borderRadius: 8,
            boxShadow: '0 4px 15px rgba(0,0,0,0.3)',
            fontSize: 14,
            fontWeight: 500,
            pointerEvents: 'auto',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }} onClick={() => removeToast(t.id)}>
            <span>{t.message}</span>
            <span style={{ opacity: 0.6, fontSize: 18 }}>&times;</span>
          </div>
        ))}
      </div>
    </>
  );
}