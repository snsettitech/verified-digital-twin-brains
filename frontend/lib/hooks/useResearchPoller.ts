/**
 * useResearchPoller - Research run status polling hook
 * 
 * Features:
 * - Polling with exponential backoff (2s -> 5s max)
 * - Page visibility awareness (pauses when tab hidden)
 * - Terminal state detection (stops polling on complete/failed)
 * - Idempotent action handling
 * - Cleanup on unmount
 */

'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { researchApi, ResearchRunStatusResponse, ResearchRunStatus, isTerminalStatus } from '@/lib/api/research';

export interface UseResearchPollerOptions {
  twinId: string | null;
  researchRunId: string | null;
  /** Initial polling interval in ms (default: 2000ms) */
  initialInterval?: number;
  /** Maximum polling interval in ms (default: 5000ms) */
  maxInterval?: number;
  /** Max time to poll in ms before giving up (default: 30 minutes) */
  timeout?: number;
  /** Enable debug logging */
  debug?: boolean;
}

export interface UseResearchPollerReturn {
  /** Current research run status */
  status: ResearchRunStatusResponse | null;
  /** Whether polling is active */
  isPolling: boolean;
  /** Error message if any */
  error: string | null;
  /** Whether the run reached a terminal state */
  isTerminal: boolean;
  /** Whether the run completed successfully */
  isCompleted: boolean;
  /** Whether the run failed */
  isFailed: boolean;
  /** Whether user action is required */
  requiresUserAction: boolean;
  /** Start polling for a research run */
  startPolling: (twinId: string, researchRunId: string) => void;
  /** Stop polling */
  stopPolling: () => void;
  /** Refresh status immediately */
  refresh: () => Promise<void>;
  /** Retry after error */
  retry: () => void;
}

// Default polling intervals
const DEFAULT_INITIAL_INTERVAL = 2000;   // 2 seconds
const DEFAULT_MAX_INTERVAL = 5000;       // 5 seconds
const DEFAULT_TIMEOUT = 30 * 60 * 1000;  // 30 minutes
const MAX_ERROR_BACKOFF = 30000;         // Max 30s between retries on error

export function useResearchPoller({
  twinId: initialTwinId,
  researchRunId: initialResearchRunId,
  initialInterval = DEFAULT_INITIAL_INTERVAL,
  maxInterval = DEFAULT_MAX_INTERVAL,
  timeout = DEFAULT_TIMEOUT,
  debug = false,
}: UseResearchPollerOptions): UseResearchPollerReturn {
  const [status, setStatus] = useState<ResearchRunStatusResponse | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const twinIdRef = useRef<string | null>(initialTwinId);
  const researchRunIdRef = useRef<string | null>(initialResearchRunId);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const pollRef = useRef<(() => Promise<void>) | null>(null);
  const errorCountRef = useRef(0);
  const startTimeRef = useRef<number>(0);
  const isVisibleRef = useRef(true);
  const currentIntervalRef = useRef(initialInterval);
  
  const log = useCallback((...args: unknown[]) => {
    if (debug) console.log('[useResearchPoller]', ...args);
  }, [debug]);

  // Track page visibility
  useEffect(() => {
    const handleVisibilityChange = () => {
      isVisibleRef.current = !document.hidden;
      log('Visibility changed:', isVisibleRef.current ? 'visible' : 'hidden');
    };
    
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [log]);

  // Cleanup function
  const cleanup = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsPolling(false);
    log('Cleanup complete');
  }, [log]);

  // Main polling function
  const poll = useCallback(async () => {
    const twinId = twinIdRef.current;
    const researchRunId = researchRunIdRef.current;
    
    if (!twinId || !researchRunId) {
      log('No twinId or researchRunId, stopping');
      cleanup();
      return;
    }

    // Don't poll if page is hidden
    if (!isVisibleRef.current) {
      log('Page hidden, scheduling next poll');
      timeoutRef.current = setTimeout(() => {
        void pollRef.current?.();
      }, 1000);
      return;
    }

    // Check timeout
    if (Date.now() - startTimeRef.current > timeout) {
      log('Polling timeout reached');
      setError('Research run timed out. Please check status manually.');
      cleanup();
      return;
    }

    // Cancel any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    try {
      log('Polling research run:', researchRunId);
      
      const data = await researchApi.getResearchRunStatus(twinId, researchRunId);
      
      log('Status:', data.status);
      
      setStatus(data);
      setError(null);
      errorCountRef.current = 0; // Reset error count on success
      
      // Check if terminal state - stop polling
      if (isTerminalStatus(data.status)) {
        log('Terminal state reached:', data.status);
        cleanup();
        return;
      }
      
      // Check if awaiting confirmation - keep polling but slower
      if (data.status === 'awaiting_confirmation') {
        log('Awaiting confirmation, slowing polling');
        currentIntervalRef.current = maxInterval;
      } else {
        // Gradually increase interval up to max
        currentIntervalRef.current = Math.min(
          currentIntervalRef.current + 500,
          maxInterval
        );
      }
      
      log('Scheduling next poll in', currentIntervalRef.current, 'ms');
      timeoutRef.current = setTimeout(() => {
        void pollRef.current?.();
      }, currentIntervalRef.current);
      
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        log('Request aborted');
        return;
      }

      errorCountRef.current++;
      const errorMsg = err instanceof Error ? err.message : 'Failed to fetch research status';
      log('Poll error:', errorMsg, '(count:', errorCountRef.current, ')');
      setError(errorMsg);

      // Exponential backoff on errors
      const backoffMs = Math.min(
        1000 * Math.pow(2, errorCountRef.current - 1),
        MAX_ERROR_BACKOFF
      );
      
      log('Retrying after error backoff:', backoffMs, 'ms');
      timeoutRef.current = setTimeout(() => {
        void pollRef.current?.();
      }, backoffMs);
    }
  }, [timeout, initialInterval, maxInterval, cleanup, log]);

  useEffect(() => {
    pollRef.current = poll;
  }, [poll]);

  // Start polling
  const startPolling = useCallback((newTwinId: string, newResearchRunId: string) => {
    log('Starting polling for research run:', newResearchRunId);
    twinIdRef.current = newTwinId;
    researchRunIdRef.current = newResearchRunId;
    startTimeRef.current = Date.now();
    errorCountRef.current = 0;
    currentIntervalRef.current = initialInterval;
    setError(null);
    setIsPolling(true);
    void pollRef.current?.();
  }, [poll, initialInterval, log]);

  // Stop polling
  const stopPolling = useCallback(() => {
    log('Stopping polling');
    cleanup();
  }, [cleanup, log]);

  // Refresh status immediately
  const refresh = useCallback(async () => {
    const twinId = twinIdRef.current;
    const researchRunId = researchRunIdRef.current;
    
    if (!twinId || !researchRunId) {
      throw new Error('No active research run to refresh');
    }

    log('Manual refresh');
    const data = await researchApi.getResearchRunStatus(twinId, researchRunId);
    setStatus(data);
    return;
  }, [log]);

  // Retry after error
  const retry = useCallback(() => {
    log('Retrying after error');
    errorCountRef.current = 0;
    setError(null);
    setIsPolling(true);
    void pollRef.current?.();
  }, [poll, log]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  // Start polling if initial IDs provided
  useEffect(() => {
    if (initialTwinId && initialResearchRunId && !researchRunIdRef.current) {
      startPolling(initialTwinId, initialResearchRunId);
    }
  }, [initialTwinId, initialResearchRunId, startPolling]);

  const isTerminal = status ? isTerminalStatus(status.status) : false;
  const isCompleted = status?.status === 'completed';
  const isFailed = status?.status === 'failed' || status?.status === 'timed_out';
  const requiresUserAction = status?.status === 'awaiting_confirmation' || false;

  return {
    status,
    isPolling,
    error,
    isTerminal,
    isCompleted,
    isFailed,
    requiresUserAction,
    startPolling,
    stopPolling,
    refresh,
    retry,
  };
}

export default useResearchPoller;
