'use client';

import { useEffect, useState, useCallback } from 'react';
import { validateLinkCompileJob, type LinkCompileJob } from '@/lib/types/api.contract';

interface IngestionProgressProps {
  twinId: string | null;
  onComplete: () => void;
}

export function IngestionProgress({ twinId, onComplete }: IngestionProgressProps) {
  const [job, setJob] = useState<LinkCompileJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pollCount, setPollCount] = useState(0);

  const pollJobStatus = useCallback(async () => {
    if (!twinId) return;

    try {
      const response = await fetch(`/api/persona/link-compile/twins/${twinId}/job`);
      if (!response.ok) {
        if (response.status === 404) {
          // Job not found yet, keep polling
          return;
        }
        throw new Error('Failed to fetch job status');
      }

      const data = await response.json();
      const validatedJob = validateLinkCompileJob(data);
      
      if (validatedJob) {
        setJob(validatedJob);
        
        // Check completion
        if (validatedJob.status === 'completed' || validatedJob.status === 'claims_ready') {
          onComplete();
        } else if (validatedJob.status === 'failed') {
          setError(validatedJob.error_message || 'Processing failed');
        }
      }
    } catch (e) {
      console.error('Poll error:', e);
    }
    
    setPollCount(c => c + 1);
  }, [twinId, onComplete]);

  useEffect(() => {
    // Initial poll
    pollJobStatus();
    
    // Set up polling interval (every 3 seconds)
    const interval = setInterval(pollJobStatus, 3000);
    
    return () => clearInterval(interval);
  }, [pollJobStatus]);

  const getStatusMessage = () => {
    switch (job?.status) {
      case 'pending':
        return 'Waiting to start...';
      case 'processing':
        return 'Downloading and processing content...';
      case 'extracting_claims':
        return 'Extracting claims from your content...';
      case 'compiling_persona':
        return 'Building your persona...';
      case 'completed':
      case 'claims_ready':
        return 'Processing complete!';
      case 'failed':
        return `Failed: ${job.error_message || 'Unknown error'}`;
      default:
        return pollCount === 0 ? 'Initializing...' : 'Processing...';
    }
  };

  const progress = job && job.total_sources > 0
    ? Math.round((job.processed_sources / job.total_sources) * 100)
    : 0;

  if (error) {
    return (
      <div className="space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold mb-2 text-white">Processing Failed</h2>
          <p className="text-red-400">{error}</p>
        </div>
        <button
          onClick={() => window.location.reload()}
          className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-semibold"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2 text-white">Processing Your Content</h2>
        <p className="text-slate-400">
          We're extracting claims and building your persona. This may take a few minutes.
        </p>
      </div>

      <div className="bg-slate-900 border border-slate-700 rounded-xl p-6">
        {/* Progress Bar */}
        <div className="w-full bg-slate-800 rounded-full h-4 mb-6">
          <div 
            className="bg-indigo-600 h-4 rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Status */}
        <div className="text-center">
          <div className="inline-flex items-center gap-3 mb-4">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-lg font-medium text-white">{getStatusMessage()}</span>
          </div>

          {job && (
            <div className="grid grid-cols-3 gap-4 mt-6 text-sm">
              <div className="bg-slate-800 p-3 rounded-lg">
                <div className="text-2xl font-bold text-indigo-400">
                  {job.processed_sources}/{job.total_sources}
                </div>
                <div className="text-slate-400">Sources</div>
              </div>
              <div className="bg-slate-800 p-3 rounded-lg">
                <div className="text-2xl font-bold text-indigo-400">
                  {job.extracted_claims}
                </div>
                <div className="text-slate-400">Claims Found</div>
              </div>
              <div className="bg-slate-800 p-3 rounded-lg">
                <div className="text-2xl font-bold text-indigo-400">
                  {progress}%
                </div>
                <div className="text-slate-400">Complete</div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="text-center text-sm text-slate-500">
        <p>Don't close this window. You'll be redirected when processing is complete.</p>
        {pollCount > 0 && <p className="mt-1">Poll count: {pollCount}</p>}
      </div>
    </div>
  );
}
