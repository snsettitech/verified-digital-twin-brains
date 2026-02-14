'use client';

import { useCallback, useEffect, useState } from 'react';
import { API_BASE_URL } from '@/lib/constants';

export function ApiConnectivityBanner() {
  const [isVisible, setIsVisible] = useState(false);
  const [status, setStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [retryCount, setRetryCount] = useState(0);

  const checkConnection = useCallback(async () => {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 7000);

      const res = await fetch(`${API_BASE_URL}/health`, {
        signal: controller.signal,
      });

      clearTimeout(timeout);

      if (res.ok) {
        setStatus('online');
        setIsVisible(false);
      } else {
        setStatus('offline');
        setIsVisible(true);
      }
    } catch {
      setStatus('offline');
      setIsVisible(true);
    }
  }, []);

  useEffect(() => {
    checkConnection();
  }, [checkConnection]);

  // Poll only while offline to avoid constant background pressure on /health.
  useEffect(() => {
    if (status !== 'offline') return;
    const interval = setInterval(checkConnection, 20000);
    return () => clearInterval(interval);
  }, [status, checkConnection]);

  const handleRetry = async () => {
    setRetryCount(c => c + 1);
    setStatus('checking');
    
    try {
      const res = await fetch(`${API_BASE_URL}/health`, {
        signal: AbortSignal.timeout(7000),
      });
      
      if (res.ok) {
        setStatus('online');
        setIsVisible(false);
        window.location.reload();
      } else {
        setStatus('offline');
      }
    } catch {
      setStatus('offline');
    }
  };

  if (!isVisible) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-[100] bg-red-600 text-white px-4 py-3 shadow-lg">
      <div className="max-w-6xl mx-auto flex items-center justify-between">
        <div className="flex items-center gap-3">
          <svg className="w-5 h-5 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span className="font-medium">
            Cannot connect to backend API
          </span>
          <span className="text-red-200 text-sm hidden sm:inline">
            (Attempt {retryCount + 1})
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-red-200 text-sm hidden md:inline">
            {API_BASE_URL}
          </span>
          <button
            onClick={handleRetry}
            disabled={status === 'checking'}
            className="px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            {status === 'checking' ? 'Retrying...' : 'Retry Connection'}
          </button>
        </div>
      </div>
    </div>
  );
}
