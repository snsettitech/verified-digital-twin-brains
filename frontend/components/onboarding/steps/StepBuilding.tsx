'use client';

import { useEffect, useState } from 'react';

interface StepBuildingProps {
  twinId: string | null;
  onComplete: () => void;
}

interface BuildProgress {
  sourcesProgress: number;
  claimsProgress: number;
  totalSources: number;
  processedSources: number;
  extractedClaims: number;
  status: 'collecting' | 'extracting' | 'generating' | 'completed' | 'failed';
  errorMessage?: string;
}

export function StepBuilding({ twinId, onComplete }: StepBuildingProps) {
  const [progress, setProgress] = useState<BuildProgress>({
    sourcesProgress: 0,
    claimsProgress: 0,
    totalSources: 0,
    processedSources: 0,
    extractedClaims: 0,
    status: 'collecting',
  });

  useEffect(() => {
    if (!twinId) return;

    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`/api/persona/link-compile/twins/${twinId}/job`);
        if (!response.ok) return;
        
        const data = await response.json();
        
        // Map job status to progress
        const sourcesProgress = data.total_sources > 0 
          ? Math.round((data.processed_sources / data.total_sources) * 100)
          : 0;
        
        let claimsProgress = 0;
        let status: BuildProgress['status'] = 'collecting';
        
        switch (data.status) {
          case 'pending':
          case 'processing':
            status = 'collecting';
            claimsProgress = 0;
            break;
          case 'extracting_claims':
            status = 'extracting';
            claimsProgress = 30;
            break;
          case 'compiling_persona':
            status = 'generating';
            claimsProgress = 70;
            break;
          case 'completed':
          case 'claims_ready':
            status = 'completed';
            claimsProgress = 100;
            break;
          case 'failed':
            status = 'failed';
            break;
        }
        
        setProgress({
          sourcesProgress,
          claimsProgress,
          totalSources: data.total_sources,
          processedSources: data.processed_sources,
          extractedClaims: data.extracted_claims,
          status,
          errorMessage: data.error_message,
        });

        if (status === 'completed') {
          clearInterval(pollInterval);
          setTimeout(onComplete, 1000); // Brief delay to show 100%
        }
      } catch (e) {
        console.error('Failed to fetch progress:', e);
      }
    }, 2000);

    return () => clearInterval(pollInterval);
  }, [twinId, onComplete]);

  const getStatusMessage = () => {
    switch (progress.status) {
      case 'collecting':
        return 'Downloading and processing your sources...';
      case 'extracting':
        return 'Extracting claims and evidence...';
      case 'generating':
        return 'Building your persona and bio...';
      case 'completed':
        return 'Your Digital Twin is ready!';
      case 'failed':
        return `Failed: ${progress.errorMessage || 'Unknown error'}`;
      default:
        return 'Initializing...';
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="text-center">
        <h2 className="text-2xl font-bold text-white mb-2">Building Your Twin</h2>
        <p className="text-slate-400">
          This usually takes 1–2 minutes. You'll be able to preview before activating.
        </p>
      </div>

      {/* Two-Track Progress */}
      <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 space-y-6">
        {/* Track 1: Sources */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="text-lg">
                {progress.sourcesProgress === 100 ? '✅' : '📥'}
              </span>
              <span className="font-medium text-white">Collecting Sources</span>
            </div>
            <span className="text-sm text-slate-400">
              {progress.processedSources} / {progress.totalSources}
            </span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-3">
            <div 
              className="bg-blue-500 h-3 rounded-full transition-all duration-500"
              style={{ width: `${progress.sourcesProgress}%` }}
            />
          </div>
        </div>

        {/* Track 2: Claims/Bio */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="text-lg">
                {progress.claimsProgress === 100 ? '✅' : progress.claimsProgress > 0 ? '⚙️' : '⏳'}
              </span>
              <span className="font-medium text-white">Extracting Claims & Generating Bio</span>
            </div>
            <span className="text-sm text-slate-400">
              {progress.extractedClaims} claims found
            </span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-3">
            <div 
              className={`h-3 rounded-full transition-all duration-500 ${
                progress.status === 'collecting' ? 'bg-slate-600' : 'bg-indigo-500'
              }`}
              style={{ width: `${progress.claimsProgress}%` }}
            />
          </div>
        </div>

        {/* Status Message */}
        <div className="text-center pt-4 border-t border-slate-800">
          <div className="inline-flex items-center gap-3">
            {progress.status !== 'completed' && progress.status !== 'failed' && (
              <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            )}
            <span className="text-lg font-medium text-white">{getStatusMessage()}</span>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-slate-900 p-4 rounded-xl border border-slate-700 text-center">
          <div className="text-2xl font-bold text-blue-400">
            {progress.totalSources}
          </div>
          <div className="text-sm text-slate-400">Sources</div>
        </div>
        <div className="bg-slate-900 p-4 rounded-xl border border-slate-700 text-center">
          <div className="text-2xl font-bold text-indigo-400">
            {progress.extractedClaims}
          </div>
          <div className="text-sm text-slate-400">Claims Found</div>
        </div>
        <div className="bg-slate-900 p-4 rounded-xl border border-slate-700 text-center">
          <div className="text-2xl font-bold text-slate-400">
            {progress.status === 'completed' ? '✓' : '...'}
          </div>
          <div className="text-sm text-slate-400">Bio Status</div>
        </div>
      </div>

      {/* Error State */}
      {progress.status === 'failed' && (
        <div className="bg-red-500/10 border border-red-500/30 p-4 rounded-xl">
          <p className="text-red-400 text-center">
            Something went wrong. You can try again or add different sources.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 w-full py-3 bg-red-600 hover:bg-red-500 text-white rounded-xl font-medium transition-colors"
          >
            Try Again
          </button>
        </div>
      )}

      {/* Tips */}
      <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700">
        <p className="text-sm text-slate-400">
          <span className="text-amber-400">💡 Tip:</span> The more high-quality sources you provide, 
          the more accurate and citeable your Digital Twin will be.
        </p>
      </div>

      <p className="text-center text-sm text-slate-500">
        Don't close this window. You'll be redirected when ready.
      </p>
    </div>
  );
}
