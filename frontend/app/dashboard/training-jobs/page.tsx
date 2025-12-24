'use client';

import React, { useState, useEffect } from 'react';

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

const twinId = "eeeed554-9180-4229-a9af-0f8dd2c69e9b"; // Fixed for dev

export default function TrainingJobsPage() {
  const [jobs, setJobs] = useState<TrainingJob[]>([]);
  const [sources, setSources] = useState<Record<string, Source>>({});
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedJob, setSelectedJob] = useState<TrainingJob | null>(null);
  const [processingQueue, setProcessingQueue] = useState(false);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const [jobsRes, sourcesRes] = await Promise.all([
        fetch(`http://localhost:8000/training-jobs?twin_id=${twinId}`, {
          headers: { 'Authorization': 'Bearer development_token' }
        }),
        fetch(`http://localhost:8000/sources/${twinId}`, {
          headers: { 'Authorization': 'Bearer development_token' }
        })
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
  };

  const handleRetry = async (jobId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/training-jobs/${jobId}/retry`, {
        method: 'POST',
        headers: { 
          'Authorization': 'Bearer development_token',
          'Content-Type': 'application/json'
        }
      });
      if (response.ok) {
        fetchData();
      }
    } catch (error) {
      console.error('Error retrying job:', error);
    }
  };

  const handleProcessQueue = async () => {
    setProcessingQueue(true);
    try {
      const response = await fetch(`http://localhost:8000/training-jobs/process-queue?twin_id=${twinId}`, {
        method: 'POST',
        headers: { 
          'Authorization': 'Bearer development_token',
          'Content-Type': 'application/json'
        }
      });
      if (response.ok) {
        const result = await response.json();
        alert(result.message || `Processed ${result.processed} job(s)`);
        fetchData();
      } else {
        const data = await response.json();
        alert(data.detail || 'Failed to process queue');
      }
    } catch (error) {
      console.error('Error processing queue:', error);
      alert('Connection error');
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
          className="px-6 py-3 bg-indigo-600 text-white rounded-2xl text-sm font-black hover:bg-indigo-700 disabled:opacity-50 transition-all"
        >
          {processingQueue ? 'Processing...' : 'Process Queue'}
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        {['all', 'queued', 'processing', 'complete', 'failed', 'needs_attention'].map((status) => (
          <button
            key={status}
            onClick={() => setStatusFilter(status)}
            className={`px-4 py-2 rounded-xl text-sm font-bold transition-all ${
              statusFilter === status
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

