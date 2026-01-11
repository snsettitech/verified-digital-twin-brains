'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useTwin } from '@/lib/context/TwinContext';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';

interface TrainingJob {
  id: string;
  source_id: string;
  twin_id: string;
  status: string;
  job_type: string;
  priority: number;
  error_message?: string;
  metadata: any;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

interface Source {
  id: string;
  filename: string;
}

export default function TrainingJobsPage() {
  const { activeTwin, isLoading: twinLoading } = useTwin();
  const { get, post } = useAuthFetch();
  const [jobs, setJobs] = useState<TrainingJob[]>([]);
  const [sources, setSources] = useState<Record<string, Source>>({});
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedJob, setSelectedJob] = useState<TrainingJob | null>(null);
  const [processingQueue, setProcessingQueue] = useState(false);

  const twinId = activeTwin?.id;

  const fetchData = useCallback(async () => {
    if (!twinId) return;
    try {
      const [jobsRes, sourcesRes] = await Promise.all([
        get(`/training-jobs?twin_id=${twinId}`),
        get(`/sources/${twinId}`)
      ]);

      if (jobsRes.ok) {
        const jobsData = await jobsRes.json();
        setJobs(jobsData);
      }

      if (sourcesRes.ok) {
        const sourcesData = await sourcesRes.json();
        const sourcesMap: Record<string, Source> = {};
        sourcesData.forEach((s: Source) => {
          sourcesMap[s.id] = s;
        });
        setSources(sourcesMap);
      }
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  }, [twinId, get]);

  useEffect(() => {
    if (twinId) {
      fetchData();
      const interval = setInterval(fetchData, 5000);
      return () => clearInterval(interval);
    } else if (!twinLoading) {
      setLoading(false);
    }
  }, [twinId, twinLoading, fetchData]);

  const handleRetry = async (jobId: string) => {
    try {
      const response = await post(`/training-jobs/${jobId}/retry`);
      if (response.ok) {
        fetchData();
      }
    } catch (error) {
      console.error('Error retrying job:', error);
    }
  };

  const [queueStatus, setQueueStatus] = useState<{processed: number; failed: number; remaining: number; message?: string} | null>(null);

  const handleProcessQueue = async () => {
    if (!twinId) return;
    setProcessingQueue(true);
    setQueueStatus(null);
    try {
      const response = await post(`/training-jobs/process-queue?twin_id=${twinId}`);
      if (response.ok) {
        const result = await response.json();
        setQueueStatus({
          processed: result.processed || 0,
          failed: result.failed || 0,
          remaining: result.remaining || 0,
          message: result.message
        });
        // Refresh data after a short delay to see updated job statuses
        setTimeout(() => {
          fetchData();
        }, 1000);
      } else {
        const data = await response.json();
        setQueueStatus({
          processed: 0,
          failed: 0,
          remaining: 0,
          message: data.detail || 'Failed to process queue'
        });
      }
    } catch (error) {
      console.error('Error processing queue:', error);
      setQueueStatus({
        processed: 0,
        failed: 0,
        remaining: 0,
        message: 'Connection error while processing queue'
      });
    } finally {
      setProcessingQueue(false);
    }
  };

  const filteredJobs = jobs.filter(j => {
    if (statusFilter === 'all') return true;
    return j.status === statusFilter;
  });

  const getStatusBadge = (status: string) => {
    const colors = {
      queued: 'bg-blue-100 text-blue-700',
      processing: 'bg-yellow-100 text-yellow-700',
      complete: 'bg-green-100 text-green-700',
      failed: 'bg-red-100 text-red-700',
      needs_attention: 'bg-orange-100 text-orange-700'
    };
    return (
      <span className={`px-2 py-1 text-xs font-bold rounded ${colors[status as keyof typeof colors] || colors.queued}`}>
        {status.toUpperCase().replace('_', ' ')}
      </span>
    );
  };

  const getDuration = (job: TrainingJob) => {
    if (!job.started_at) return 'N/A';
    const end = job.completed_at || new Date().toISOString();
    const start = new Date(job.started_at);
    const endDate = new Date(end);
    const diff = Math.floor((endDate.getTime() - start.getTime()) / 1000);
    if (diff < 60) return `${diff}s`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m`;
    return `${Math.floor(diff / 3600)}h`;
  };

  if (twinLoading) {
    return (
      <div className="flex justify-center p-20">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (!twinId) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center max-w-md p-8">
          <div className="w-16 h-16 bg-indigo-100 rounded-2xl flex items-center justify-center mx-auto mb-6">
            <svg className="w-8 h-8 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-slate-900 mb-3">No Twin Found</h2>
          <p className="text-slate-500 mb-6">Create a digital twin first to manage training jobs.</p>
          <a href="/dashboard/right-brain" className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition-colors">
            Create Your Twin
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-10 pb-20">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-black tracking-tight text-slate-900">Training Jobs</h1>
          <p className="text-slate-500 mt-2 font-medium">Monitor and manage content training jobs.</p>
        </div>
        <button
          onClick={handleProcessQueue}
          disabled={processingQueue}
          className="px-6 py-3 bg-indigo-600 text-white rounded-2xl text-sm font-black hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2"
        >
          {processingQueue ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              Processing...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Process Queue
            </>
          )}
        </button>
      </div>

      {/* Queue Status */}
      {queueStatus && (
        <div className={`border p-6 rounded-2xl text-sm font-bold ${
          queueStatus.failed > 0 
            ? 'bg-yellow-50 border-yellow-200 text-yellow-800' 
            : queueStatus.processed > 0
            ? 'bg-green-50 border-green-200 text-green-800'
            : 'bg-slate-50 border-slate-200 text-slate-800'
        }`}>
          <div className="flex items-center gap-2 mb-2">
            {queueStatus.failed > 0 ? (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            )}
            <span>{queueStatus.message || 'Queue Processing Complete'}</span>
          </div>
          <div className="text-xs mt-2 space-y-1">
            <div>Processed: {queueStatus.processed} job(s)</div>
            {queueStatus.failed > 0 && <div>Failed: {queueStatus.failed} job(s)</div>}
            {queueStatus.remaining > 0 && <div>Remaining: {queueStatus.remaining} job(s)</div>}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3">
        {['all', 'queued', 'processing', 'complete', 'failed', 'needs_attention'].map((status) => (
          <button
            key={status}
            onClick={() => setStatusFilter(status)}
            className={`px-4 py-2 rounded-xl text-sm font-bold transition-all ${statusFilter === status
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
          >
            {status.charAt(0).toUpperCase() + status.slice(1).replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* Jobs Table */}
      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
        <div className="p-8 border-b border-slate-100">
          <h3 className="text-lg font-black text-slate-800">Training Jobs</h3>
        </div>

        {loading ? (
          <div className="p-20 flex justify-center">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600"></div>
          </div>
        ) : filteredJobs.length === 0 ? (
          <div className="p-32 text-center">
            <p className="text-slate-500">No training jobs found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-50/50">
                  <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Job ID</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Source</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Type</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Status</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Created</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Duration</th>
                  <th className="px-8 py-5 text-right"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {filteredJobs.map((job) => (
                  <tr
                    key={job.id}
                    className="hover:bg-slate-50/50 transition-colors cursor-pointer"
                    onClick={() => setSelectedJob(job)}
                  >
                    <td className="px-8 py-6">
                      <div className="font-mono text-xs text-slate-600">{job.id.substring(0, 8)}...</div>
                    </td>
                    <td className="px-8 py-6">
                      <div className="font-bold text-slate-800 text-sm">
                        {sources[job.source_id]?.filename || job.source_id.substring(0, 8)}
                      </div>
                    </td>
                    <td className="px-8 py-6">
                      <span className="px-2 py-1 bg-slate-100 text-slate-700 text-xs font-bold rounded">
                        {job.job_type.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-8 py-6">{getStatusBadge(job.status)}</td>
                    <td className="px-8 py-6 text-xs font-bold text-slate-400">
                      {new Date(job.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-8 py-6 text-xs font-bold text-slate-400">
                      {getDuration(job)}
                    </td>
                    <td className="px-8 py-6 text-right">
                      {job.status === 'failed' && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRetry(job.id);
                          }}
                          className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-bold hover:bg-indigo-700 transition-all"
                        >
                          Retry
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Job Details Modal */}
      {selectedJob && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setSelectedJob(null)}>
          <div className="bg-white rounded-2xl p-8 max-w-2xl w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-black text-slate-900">Job Details</h2>
              <button
                onClick={() => setSelectedJob(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Job ID</h3>
                <p className="font-mono text-sm text-slate-800">{selectedJob.id}</p>
              </div>
              <div>
                <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Status</h3>
                <p className="text-sm text-slate-800">{getStatusBadge(selectedJob.status)}</p>
              </div>
              <div>
                <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Source</h3>
                <p className="text-sm text-slate-800">
                  {sources[selectedJob.source_id]?.filename || selectedJob.source_id}
                </p>
              </div>
              {selectedJob.error_message && (
                <div>
                  <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Error</h3>
                  <p className="text-sm text-red-600 bg-red-50 p-3 rounded-xl">{selectedJob.error_message}</p>
                </div>
              )}
              {selectedJob.metadata && Object.keys(selectedJob.metadata).length > 0 && (
                <div>
                  <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Metadata</h3>
                  <pre className="text-xs text-slate-600 bg-slate-50 p-3 rounded-xl overflow-auto">
                    {JSON.stringify(selectedJob.metadata, null, 2)}
                  </pre>
                </div>
              )}
            </div>
            {selectedJob.status === 'failed' && (
              <div className="mt-6">
                <button
                  onClick={() => {
                    handleRetry(selectedJob.id);
                    setSelectedJob(null);
                  }}
                  className="w-full px-6 py-3 bg-indigo-600 text-white rounded-xl text-sm font-black hover:bg-indigo-700 transition-all"
                >
                  Retry Job
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
