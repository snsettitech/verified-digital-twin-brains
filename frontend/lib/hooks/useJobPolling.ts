'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// Polling intervals based on job status (ms)
const POLL_INTERVALS: Record<string, number> = {
  queued: 5000,           // Check every 5s
  processing: 3000,       // Check every 3s (more frequent when active)
  needs_attention: 10000, // Check every 10s
  complete: 0,            // Stop polling
  failed: 0,              // Stop polling
};

// Max polling interval during error backoff
const MAX_ERROR_INTERVAL = 30000; // 30 seconds

export interface Job {
  id: string;
  twin_id?: string;
  source_id?: string;
  status: 'queued' | 'processing' | 'needs_attention' | 'complete' | 'failed';
  job_type: string;
  priority: number;
  error_message?: string;
  metadata: {
    progress?: number;
    steps?: { name: string; status: string }[];
    estimated_completion?: string;
    [key: string]: any;
  };
  created_at: string;
  updated_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface JobLog {
  id: string;
  job_id: string;
  log_level: 'info' | 'warning' | 'error';
  message: string;
  metadata: any;
  created_at: string;
}

interface UseJobPollingOptions {
  twinId?: string;
  jobId?: string;
  autoStart?: boolean;
}

interface UseJobPollingReturn {
  jobs: Job[];
  activeJob: Job | null;
  logs: JobLog[];
  loading: boolean;
  error: string | null;
  isPolling: boolean;
  refetch: () => Promise<void>;
  fetchLogs: (jobId: string) => Promise<void>;
  retryJob: (jobId: string) => Promise<boolean>;
  cancelPolling: () => void;
}

export function useJobPolling({
  twinId,
  jobId,
  autoStart = true,
}: UseJobPollingOptions): UseJobPollingReturn {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const [logs, setLogs] = useState<JobLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  
  const supabase = getSupabaseClient();
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const errorCountRef = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef(true);

  // Get auth token
  const getAuthToken = useCallback(async (): Promise<string | null> => {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token || null;
  }, [supabase]);

  // Cancel any pending requests and timeouts
  const cancelPolling = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsPolling(false);
  }, []);

  // Fetch jobs
  const fetchJobs = useCallback(async (): Promise<Job[]> => {
    if (!twinId) return [];
    
    const token = await getAuthToken();
    if (!token) {
      throw new Error('Not authenticated');
    }

    // Cancel previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    const url = jobId 
      ? `${API_BASE_URL}/jobs/${jobId}`
      : `${API_BASE_URL}/jobs?twin_id=${twinId}&limit=10`;

    const response = await fetch(url, {
      headers: { 'Authorization': `Bearer ${token}` },
      signal: abortControllerRef.current.signal,
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch jobs: ${response.status}`);
    }

    const data = await response.json();
    return Array.isArray(data) ? data : [data];
  }, [twinId, jobId, getAuthToken]);

  // Main polling function
  const poll = useCallback(async () => {
    if (!isMountedRef.current) return;
    
    setLoading(true);
    setError(null);

    try {
      const fetchedJobs = await fetchJobs();
      
      if (!isMountedRef.current) return;

      // Reset error count on success
      errorCountRef.current = 0;
      
      setJobs(fetchedJobs);
      
      // Find active job (most recent non-complete/failed)
      const active = fetchedJobs.find(j => 
        j.status === 'processing' || j.status === 'queued' || j.status === 'needs_attention'
      );
      setActiveJob(active || null);

      // Determine next poll interval
      let nextInterval: number;
      
      if (active) {
        // Use status-based interval
        nextInterval = POLL_INTERVALS[active.status] || 5000;
      } else if (fetchedJobs.some(j => j.status === 'complete' || j.status === 'failed')) {
        // Recent completion, check once more then stop
        nextInterval = 5000;
      } else {
        // No active jobs, stop polling
        setIsPolling(false);
        return;
      }

      // Schedule next poll
      if (isMountedRef.current) {
        timeoutRef.current = setTimeout(poll, nextInterval);
        setIsPolling(true);
      }
    } catch (err) {
      if (!isMountedRef.current) return;
      
      // Don't show error for aborts (component unmounting)
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }

      errorCountRef.current++;
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch jobs';
      setError(errorMessage);

      // Exponential backoff on errors
      const backoffInterval = Math.min(
        5000 * Math.pow(2, errorCountRef.current - 1),
        MAX_ERROR_INTERVAL
      );

      if (isMountedRef.current) {
        timeoutRef.current = setTimeout(poll, backoffInterval);
        setIsPolling(true);
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [fetchJobs]);

  // Manual refetch
  const refetch = useCallback(async () => {
    cancelPolling();
    errorCountRef.current = 0;
    await poll();
  }, [cancelPolling, poll]);

  // Fetch logs for a specific job
  const fetchLogs = useCallback(async (targetJobId: string) => {
    const token = await getAuthToken();
    if (!token) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/jobs/${targetJobId}/logs?limit=50`,
        { headers: { 'Authorization': `Bearer ${token}` } }
      );

      if (response.ok) {
        const data = await response.json();
        setLogs(data);
      }
    } catch (err) {
      console.error('Failed to fetch logs:', err);
    }
  }, [getAuthToken]);

  // Retry a failed job
  const retryJob = useCallback(async (targetJobId: string): Promise<boolean> => {
    const token = await getAuthToken();
    if (!token) return false;

    try {
      const response = await fetch(
        `${API_BASE_URL}/jobs/${targetJobId}/retry`,
        {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );

      if (response.ok) {
        // Trigger immediate refetch
        refetch();
        return true;
      }
      return false;
    } catch (err) {
      console.error('Failed to retry job:', err);
      return false;
    }
  }, [getAuthToken, refetch]);

  // Start/stop polling
  useEffect(() => {
    isMountedRef.current = true;

    if (autoStart && twinId) {
      poll();
    }

    return () => {
      isMountedRef.current = false;
      cancelPolling();
    };
  }, [autoStart, twinId, poll, cancelPolling]);

  // Fetch logs when active job changes
  useEffect(() => {
    if (activeJob?.id && (activeJob.status === 'processing' || activeJob.status === 'failed')) {
      fetchLogs(activeJob.id);
    }
  }, [activeJob?.id, activeJob?.status, fetchLogs]);

  return {
    jobs,
    activeJob,
    logs,
    loading,
    error,
    isPolling,
    refetch,
    fetchLogs,
    retryJob,
    cancelPolling,
  };
}
