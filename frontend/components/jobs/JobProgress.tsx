'use client';

import React, { useState } from 'react';
import { Job, JobLog, useJobPolling } from '@/lib/hooks/useJobPolling';

interface JobProgressProps {
  twinId: string;
  jobId?: string;
  compact?: boolean;
}

// Status configuration
const STATUS_CONFIG: Record<string, {
  label: string;
  color: string;
  bgColor: string;
  icon: React.ReactNode;
}> = {
  queued: {
    label: 'Queued',
    color: 'text-slate-600',
    bgColor: 'bg-slate-100',
    icon: (
      <svg className="w-4 h-4 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  processing: {
    label: 'Processing',
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    icon: (
      <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
      </svg>
    ),
  },
  needs_attention: {
    label: 'Needs Attention',
    color: 'text-amber-600',
    bgColor: 'bg-amber-50',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    ),
  },
  complete: {
    label: 'Complete',
    color: 'text-green-600',
    bgColor: 'bg-green-50',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
      </svg>
    ),
  },
  failed: {
    label: 'Failed',
    color: 'text-red-600',
    bgColor: 'bg-red-50',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
      </svg>
    ),
  },
};

// Format duration from ISO dates
function formatDuration(start?: string, end?: string): string {
  if (!start) return '';
  const startDate = new Date(start);
  const endDate = end ? new Date(end) : new Date();
  const diff = endDate.getTime() - startDate.getTime();
  
  const minutes = Math.floor(diff / 60000);
  const seconds = Math.floor((diff % 60000) / 1000);
  
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
}

// Format estimated time
function formatEstimatedTime(estimated?: string): string {
  if (!estimated) return '';
  const estimatedDate = new Date(estimated);
  const now = new Date();
  const diff = estimatedDate.getTime() - now.getTime();
  
  if (diff <= 0) return 'Any moment now';
  
  const minutes = Math.ceil(diff / 60000);
  if (minutes < 1) return '< 1 min';
  if (minutes === 1) return '1 min';
  if (minutes < 60) return `${minutes} mins`;
  
  const hours = Math.floor(minutes / 60);
  if (hours === 1) return '1 hour';
  return `${hours} hours`;
}

// Job type labels
const JOB_TYPE_LABELS: Record<string, string> = {
  ingestion: 'Source Ingestion',
  reindex: 'Vector Reindexing',
  graph_extraction: 'Graph Building',
  content_extraction: 'Content Extraction',
  feedback_learning: 'Model Training',
  health_check: 'Health Check',
  other: 'Background Job',
};

// Single job card component
function JobCard({
  job,
  logs,
  onRetry,
  expanded = false,
}: {
  job: Job;
  logs: JobLog[];
  onRetry: () => void;
  expanded?: boolean;
}) {
  const [showLogs, setShowLogs] = useState(expanded);
  const config = STATUS_CONFIG[job.status] || STATUS_CONFIG.queued;
  const progress = job.metadata?.progress || 0;
  const steps = job.metadata?.steps || [];
  const estimated = job.metadata?.estimated_completion;

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h4 className="font-semibold text-slate-900">
                {JOB_TYPE_LABELS[job.job_type] || job.job_type}
              </h4>
              <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.bgColor} ${config.color}`}>
                {config.icon}
                {config.label}
              </span>
            </div>
            <p className="text-sm text-slate-500 mt-1">
              Started {formatDuration(job.started_at)} ago
              {estimated && job.status === 'processing' && (
                <span className="text-blue-600"> • {formatEstimatedTime(estimated)} remaining</span>
              )}
            </p>
          </div>
          
          {/* Actions */}
          {job.status === 'failed' && (
            <button
              onClick={onRetry}
              className="px-3 py-1.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
            >
              Retry
            </button>
          )}
        </div>

        {/* Progress bar */}
        {(job.status === 'processing' || job.status === 'queued') && (
          <div className="mt-4">
            <div className="flex justify-between text-sm mb-1.5">
              <span className="text-slate-600">Progress</span>
              <span className="font-medium text-slate-900">{progress}%</span>
            </div>
            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-indigo-600 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Steps */}
        {steps.length > 0 && (
          <div className="mt-4 space-y-2">
            {steps.map((step, idx) => (
              <div key={idx} className="flex items-center gap-3">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center ${
                  step.status === 'completed' ? 'bg-green-100 text-green-600' :
                  step.status === 'running' ? 'bg-blue-100 text-blue-600' :
                  step.status === 'failed' ? 'bg-red-100 text-red-600' :
                  'bg-slate-100 text-slate-400'
                }`}>
                  {step.status === 'completed' ? (
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7" />
                    </svg>
                  ) : step.status === 'running' ? (
                    <div className="w-2 h-2 bg-current rounded-full animate-pulse" />
                  ) : (
                    <span className="text-xs">{idx + 1}</span>
                  )}
                </div>
                <span className={`text-sm ${
                  step.status === 'completed' ? 'text-slate-600 line-through' :
                  step.status === 'running' ? 'text-slate-900 font-medium' :
                  'text-slate-500'
                }`}>
                  {step.name}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Error message */}
        {job.error_message && (
          <div className="mt-4 p-3 bg-red-50 border border-red-100 rounded-xl">
            <p className="text-sm text-red-700">{job.error_message}</p>
          </div>
        )}
      </div>

      {/* Logs toggle */}
      {(logs.length > 0 || job.status === 'processing') && (
        <div className="border-t border-slate-100">
          <button
            onClick={() => setShowLogs(!showLogs)}
            className="w-full px-5 py-3 flex items-center justify-between text-sm text-slate-600 hover:bg-slate-50 transition-colors"
          >
            <span>View Logs ({logs.length})</span>
            <svg
              className={`w-4 h-4 transition-transform ${showLogs ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {/* Logs content */}
          {showLogs && (
            <div className="px-5 pb-4">
              <div className="bg-slate-900 rounded-xl p-4 max-h-64 overflow-y-auto font-mono text-xs">
                {logs.length === 0 ? (
                  <p className="text-slate-500">No logs yet...</p>
                ) : (
                  <div className="space-y-1">
                    {logs.map((log) => (
                      <div key={log.id} className="flex gap-3">
                        <span className="text-slate-500 shrink-0">
                          {new Date(log.created_at).toLocaleTimeString()}
                        </span>
                        <span className={`${
                          log.log_level === 'error' ? 'text-red-400' :
                          log.log_level === 'warning' ? 'text-amber-400' :
                          'text-slate-300'
                        }`}>
                          {log.message}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Main component
export default function JobProgress({ twinId, jobId, compact = false }: JobProgressProps) {
  const {
    jobs,
    activeJob,
    logs,
    loading,
    error,
    isPolling,
    refetch,
    retryJob,
  } = useJobPolling({ twinId, jobId });

  // Compact view for header/badge
  if (compact) {
    if (!activeJob) return null;
    
    const config = STATUS_CONFIG[activeJob.status];
    return (
      <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium ${config.bgColor} ${config.color}`}>
        {config.icon}
        <span>{config.label}</span>
        {activeJob.status === 'processing' && (
          <span className="text-xs opacity-75">{activeJob.metadata?.progress || 0}%</span>
        )}
      </div>
    );
  }

  // Full view
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-slate-900">Background Jobs</h3>
          <p className="text-sm text-slate-500">
            {isPolling ? 'Monitoring active jobs...' : 'No active jobs'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {loading && (
            <div className="w-5 h-5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          )}
          <button
            onClick={refetch}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
            title="Refresh"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-100 rounded-xl">
          <div className="flex items-center gap-2 text-red-700">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-sm">{error}</span>
          </div>
          <button
            onClick={refetch}
            className="mt-2 text-sm text-red-600 hover:text-red-700 font-medium"
          >
            Try again
          </button>
        </div>
      )}

      {/* Active job */}
      {activeJob && (
        <JobCard
          job={activeJob}
          logs={logs}
          onRetry={() => retryJob(activeJob.id)}
          expanded={true}
        />
      )}

      {/* Recent completed/failed jobs */}
      {jobs.filter(j => j.status === 'complete' || j.status === 'failed').length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-slate-500 uppercase tracking-wider">Recent</h4>
          {jobs
            .filter(j => j.status === 'complete' || j.status === 'failed')
            .slice(0, 3)
            .map(job => (
              <JobCard
                key={job.id}
                job={job}
                logs={[]}
                onRetry={() => retryJob(job.id)}
              />
            ))}
        </div>
      )}

      {/* Empty state */}
      {!activeJob && jobs.length === 0 && !loading && !error && (
        <div className="text-center py-12 bg-slate-50 rounded-2xl border border-slate-200 border-dashed">
          <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
          </div>
          <h4 className="font-medium text-slate-900">No active jobs</h4>
          <p className="text-sm text-slate-500 mt-1">Background jobs will appear here when running.</p>
        </div>
      )}
    </div>
  );
}

// Compact badge export
export function JobStatusBadge({ twinId }: { twinId: string }) {
  return <JobProgress twinId={twinId} compact />;
}
