'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { API_BASE_URL } from '@/lib/constants';

interface VersionInfo {
  git_sha: string;
  build_time: string;
  environment: string;
  service: string;
  version: string;
}

interface HealthInfo {
  service?: string;
  version?: string;
}

interface CorsTestResult {
  origin: string;
  is_allowed: boolean;
  matched_pattern: string | null;
  allowed_origins: string[];
  timestamp: number;
}

type ConnectionStatus = 'checking' | 'online' | 'offline' | 'cors-error';

export function ApiStatus() {
  const [status, setStatus] = useState<ConnectionStatus>('checking');
  const [version, setVersion] = useState<VersionInfo | null>(null);
  const [corsTest, setCorsTest] = useState<CorsTestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastCheck, setLastCheck] = useState<Date>(new Date());
  const [expanded, setExpanded] = useState(false);
  const versionLoadedRef = useRef(false);
  const corsLoadedRef = useRef(false);

  const checkConnection = useCallback(async (refreshMetadata = false) => {
    setStatus('checking');
    setError(null);
    
    try {
      // Use /health as source of truth for API availability.
      const healthRes = await fetch(`${API_BASE_URL}/health`, {
        signal: AbortSignal.timeout(5000)
      });

      if (!healthRes.ok) {
        setStatus('offline');
        setError(`HTTP ${healthRes.status}: ${healthRes.statusText}`);
        setLastCheck(new Date());
        return;
      }

      const healthData: HealthInfo = await healthRes.json();
      setStatus('online');

      // /version is optional. Fetch once by default, and on explicit refresh.
      if (refreshMetadata || !versionLoadedRef.current) {
        let resolvedVersion: VersionInfo = {
          git_sha: 'unknown',
          build_time: 'unknown',
          environment: process.env.NODE_ENV || 'unknown',
          service: healthData.service || 'unknown',
          version: healthData.version || 'unknown',
        };

        try {
          const versionRes = await fetch(`${API_BASE_URL}/version`, {
            signal: AbortSignal.timeout(3000)
          });

          if (versionRes.ok) {
            resolvedVersion = await versionRes.json();
          }
        } catch {
          // Ignore optional /version failures.
        }
        versionLoadedRef.current = true;
        setVersion(resolvedVersion);
      }

      // /cors-test is optional. Fetch once by default, and on explicit refresh.
      if (refreshMetadata || !corsLoadedRef.current) {
        try {
          const corsRes = await fetch(`${API_BASE_URL}/cors-test`, {
            signal: AbortSignal.timeout(3000)
          });

          if (corsRes.ok) {
            const corsData = await corsRes.json();
            setCorsTest(corsData);
            corsLoadedRef.current = true;

            if (!corsData.is_allowed) {
              setStatus('cors-error');
              setError(`Origin not in CORS allowlist: ${corsData.origin}`);
            }
          } else {
            setCorsTest(null);
          }
        } catch {
          setCorsTest(null);
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError' || err.name === 'TimeoutError') {
        setStatus('offline');
        setError('Connection timeout');
      } else if (err.message?.includes('Failed to fetch')) {
        setStatus('offline');
        setError('Cannot reach backend');
      } else {
        setStatus('offline');
        setError(err.message || 'Unknown error');
      }
    }
    
    setLastCheck(new Date());
  }, []);

  useEffect(() => {
    checkConnection(true);
    const interval = setInterval(() => checkConnection(false), 60000);
    return () => clearInterval(interval);
  }, [checkConnection]);

  // In production, only show when there's an issue or when expanded
  if (process.env.NODE_ENV === 'production' && status === 'online' && !expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="fixed bottom-4 right-4 w-8 h-8 bg-green-500 rounded-full shadow-lg z-50 flex items-center justify-center hover:scale-110 transition-transform"
        title="API Connected - Click for details"
      >
        <span className="w-2 h-2 bg-white rounded-full animate-pulse" />
      </button>
    );
  }

  const getStatusColor = () => {
    switch (status) {
      case 'online': return 'bg-green-100 text-green-800 border-green-200';
      case 'checking': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'cors-error': return 'bg-orange-100 text-orange-800 border-orange-200';
      default: return 'bg-red-100 text-red-800 border-red-200';
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'online': return '🟢';
      case 'checking': return '🟡';
      case 'cors-error': return '🟠';
      default: return '🔴';
    }
  };

  return (
    <div 
      className={`fixed bottom-4 right-4 rounded-lg shadow-lg z-50 transition-all border ${getStatusColor()} ${
        expanded ? 'w-80 p-4' : 'px-4 py-2'
      }`}
    >
      {/* Header - Always visible */}
      <div 
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <span>{getStatusIcon()}</span>
          <span className="text-sm font-medium">
            API: {status === 'checking' ? '...' : status}
          </span>
          {version && !expanded && (
            <span className="text-xs opacity-75">
              ({version.git_sha?.slice(0, 7) || 'unknown'})
            </span>
          )}
        </div>
        <button className="text-xs opacity-50 hover:opacity-100">
          {expanded ? '▼' : '▲'}
        </button>
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div className="mt-3 space-y-3 text-xs border-t border-current pt-3">
          {/* Connection Details */}
          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="opacity-75">Backend URL:</span>
              <span className="font-mono truncate max-w-[150px]">{API_BASE_URL}</span>
            </div>
            {version && (
              <>
                <div className="flex justify-between">
                  <span className="opacity-75">Git SHA:</span>
                  <span className="font-mono">{version.git_sha}</span>
                </div>
                <div className="flex justify-between">
                  <span className="opacity-75">Environment:</span>
                  <span>{version.environment}</span>
                </div>
                <div className="flex justify-between">
                  <span className="opacity-75">Build Time:</span>
                  <span>{version.build_time !== 'unknown' ? new Date(version.build_time).toLocaleString() : 'unknown'}</span>
                </div>
              </>
            )}
            <div className="flex justify-between">
              <span className="opacity-75">Last Check:</span>
              <span>{lastCheck.toLocaleTimeString()}</span>
            </div>
          </div>

          {/* CORS Status */}
          {corsTest && (
            <div className="space-y-1 border-t border-current/20 pt-2">
              <div className="font-medium">CORS Configuration</div>
              <div className="flex justify-between">
                <span className="opacity-75">Your Origin:</span>
                <span className="font-mono truncate max-w-[150px]">{corsTest.origin}</span>
              </div>
              <div className="flex justify-between">
                <span className="opacity-75">CORS Allowed:</span>
                <span className={corsTest.is_allowed ? 'text-green-600' : 'text-red-600'}>
                  {corsTest.is_allowed ? '✓ Yes' : '✗ No'}
                </span>
              </div>
              {corsTest.matched_pattern && (
                <div className="flex justify-between">
                  <span className="opacity-75">Matched Pattern:</span>
                  <span className="font-mono">{corsTest.matched_pattern}</span>
                </div>
              )}
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded p-2 text-red-700">
              <div className="font-medium">Error:</div>
              <div className="font-mono break-words">{error}</div>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-2">
            <button
              onClick={(e) => {
                e.stopPropagation();
                checkConnection(true);
              }}
              className="flex-1 bg-white/50 hover:bg-white/80 rounded px-3 py-1.5 text-xs font-medium transition-colors"
            >
              Refresh
            </button>
            <a
              href="/admin"
              onClick={(e) => e.stopPropagation()}
              className="flex-1 bg-white/50 hover:bg-white/80 rounded px-3 py-1.5 text-xs font-medium transition-colors text-center"
            >
              Admin
            </a>
            {process.env.NODE_ENV === 'development' && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  window.open(`${API_BASE_URL}/docs`, '_blank');
                }}
                className="flex-1 bg-white/50 hover:bg-white/80 rounded px-3 py-1.5 text-xs font-medium transition-colors"
              >
                API Docs
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
