'use client';

import { useEffect, useState } from 'react';

interface StepIngestionProgressProps {
  twinId: string | null;
  onComplete: () => void;
}

interface JobStatus {
  status: string;
  total_sources: number;
  processed_sources: number;
  extracted_claims: number;
  error_message?: string;
}

export function StepIngestionProgress({ twinId, onComplete }: StepIngestionProgressProps) {
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [pollInterval, setPollInterval] = useState<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!twinId) return;

    const fetchStatus = async () => {
      try {
        // Fetch the latest job for this twin
        const response = await fetch(`/api/twins/${twinId}/link-compile-job`);
        if (!response.ok) return;
        
        const data = await response.json();
        setJobStatus(data);

        // Check if complete
        if (data.status === 'completed' || data.status === 'claims_ready') {
          if (pollInterval) {
            clearInterval(pollInterval);
            setPollInterval(null);
          }
          onComplete();
        } else if (data.status === 'failed') {
          if (pollInterval) {
            clearInterval(pollInterval);
            setPollInterval(null);
          }
        }
      } catch (e) {
        console.error('Failed to fetch status:', e);
      }
    };

    // Poll every 3 seconds
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    setPollInterval(interval);

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [twinId, onComplete]);

  const getStatusMessage = () => {
    switch (jobStatus?.status) {
      case 'pending':
        return 'Waiting to start...';
      case 'processing':
        return 'Downloading and processing content...';
      case 'extracting_claims':
        return 'Extracting claims from your content...';
      case 'compiling_persona':
        return 'Building your persona...';
      case 'completed':
        return 'Processing complete!';
      case 'failed':
        return `Failed: ${jobStatus.error_message || 'Unknown error'}`;
      default:
        return 'Initializing...';
    }
  };

  const progress = jobStatus && jobStatus.total_sources > 0
    ? Math.round((jobStatus.processed_sources / jobStatus.total_sources) * 100)
    : 0;

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2">Processing Your Content</h2>
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

          {jobStatus && (
            <div className="grid grid-cols-3 gap-4 mt-6 text-sm">
              <div className="bg-slate-800 p-3 rounded-lg">
                <div className="text-2xl font-bold text-indigo-400">
                  {jobStatus.processed_sources}/{jobStatus.total_sources}
                </div>
                <div className="text-slate-400">Sources</div>
              </div>
              <div className="bg-slate-800 p-3 rounded-lg">
                <div className="text-2xl font-bold text-indigo-400">
                  {jobStatus.extracted_claims || 0}
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
      </div>
    </div>
  );
}
