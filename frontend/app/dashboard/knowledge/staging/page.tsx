'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useTwin } from '@/lib/context/TwinContext';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';

interface Source {
  id: string;
  filename: string;
  file_size: number;
  status: string;
  staging_status: string;
  health_status: string;
  created_at: string;
  extracted_text_length?: number;
  chunk_count?: number;
}

export default function StagingPage() {
  const router = useRouter();
  const { activeTwin, isLoading: twinLoading } = useTwin();
  const { get, post } = useAuthFetch();
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [selectedSources, setSelectedSources] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [processingQueue, setProcessingQueue] = useState(false);
  const [queueStatus, setQueueStatus] = useState<{processed: number; failed: number; remaining: number} | null>(null);

  const twinId = activeTwin?.id;

  const fetchSources = useCallback(async () => {
    if (!twinId) return;
    try {
      const response = await get(`/sources/${twinId}`);
      if (response.ok) {
        const data = await response.json();
        const stagedSources = data.filter((s: Source) =>
          s.staging_status && ['staged', 'approved', 'rejected', 'training'].includes(s.staging_status)
        );
        setSources(stagedSources);
      }
    } catch (error) {
      console.error('Error fetching sources:', error);
    } finally {
      setLoading(false);
    }
  }, [twinId, get]);

  useEffect(() => {
    if (twinId) {
      fetchSources();
      const interval = setInterval(fetchSources, 5000);
      return () => clearInterval(interval);
    } else if (!twinLoading) {
      setLoading(false);
    }
  }, [twinId, twinLoading, fetchSources]);

  const filteredSources = sources.filter(s => {
    if (filter === 'all') return true;
    return s.staging_status === filter;
  });

  const handleApprove = async (sourceId: string) => {
    try {
      const response = await post(`/sources/${sourceId}/approve`);
      if (response.ok) {
        fetchSources();
      } else {
        const data = await response.json();
        setError(data.detail || 'Approval failed');
      }
    } catch (err) {
      setError('Connection error');
    }
  };

  const handleReject = async (sourceId: string) => {
    const reason = prompt('Rejection reason:');
    if (!reason) return;

    try {
      const response = await post(`/sources/${sourceId}/reject`, { reason });
      if (response.ok) {
        fetchSources();
      } else {
        const data = await response.json();
        setError(data.detail || 'Rejection failed');
      }
    } catch (err) {
      setError('Connection error');
    }
  };

  const handleBulkApprove = async () => {
    if (selectedSources.size === 0) return;

    try {
      const response = await post(`/sources/bulk-approve`, { source_ids: Array.from(selectedSources) });
      if (response.ok) {
        setSelectedSources(new Set());
        fetchSources();
      } else {
        const data = await response.json();
        setError(data.detail || 'Bulk approval failed');
      }
    } catch (err) {
      setError('Connection error');
    }
  };

  const handleProcessQueue = async () => {
    if (!twinId) return;
    setProcessingQueue(true);
    setError(null);
    setQueueStatus(null);
    
    try {
      const response = await post(`/training-jobs/process-queue?twin_id=${twinId}`);
      if (response.ok) {
        const result = await response.json();
        setQueueStatus({
          processed: result.processed || 0,
          failed: result.failed || 0,
          remaining: result.remaining || 0
        });
        // Refresh sources to see updated status
        setTimeout(() => {
          fetchSources();
        }, 1000);
      } else {
        const data = await response.json();
        setError(data.detail || 'Failed to process queue');
      }
    } catch (err) {
      setError('Connection error while processing queue');
    } finally {
      setProcessingQueue(false);
    }
  };

  const getHealthBadge = (status: string) => {
    const colors = {
      healthy: 'bg-green-100 text-green-700',
      needs_attention: 'bg-yellow-100 text-yellow-700',
      failed: 'bg-red-100 text-red-700'
    };
    return (
      <span className={`px-2 py-1 text-xs font-bold rounded ${colors[status as keyof typeof colors] || colors.healthy}`}>
        {status.toUpperCase().replace('_', ' ')}
      </span>
    );
  };

  const getStagingBadge = (status: string) => {
    const colors = {
      staged: 'bg-blue-100 text-blue-700',
      approved: 'bg-purple-100 text-purple-700',
      rejected: 'bg-red-100 text-red-700',
      training: 'bg-yellow-100 text-yellow-700',
      live: 'bg-green-100 text-green-700'
    };
    return (
      <span className={`px-2 py-1 text-xs font-bold rounded ${colors[status as keyof typeof colors] || colors.staged}`}>
        {status.toUpperCase()}
      </span>
    );
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
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-slate-900 mb-3">No Twin Found</h2>
          <p className="text-slate-500 mb-6">Create a digital twin first to access content staging.</p>
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
          <h1 className="text-4xl font-black tracking-tight text-slate-900">Content Staging</h1>
          <p className="text-slate-500 mt-2 font-medium">Review and approve content before it enters the brain.</p>
        </div>
        <div className="flex gap-3">
          {sources.filter(s => s.staging_status === 'approved').length > 0 && (
            <button
              onClick={handleProcessQueue}
              disabled={processingQueue}
              className="px-6 py-3 bg-green-600 text-white rounded-2xl text-sm font-black hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2"
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
                  Process Queue ({sources.filter(s => s.staging_status === 'approved').length} approved)
                </>
              )}
            </button>
          )}
          {selectedSources.size > 0 && (
            <button
              onClick={handleBulkApprove}
              className="px-6 py-3 bg-indigo-600 text-white rounded-2xl text-sm font-black hover:bg-indigo-700 transition-all"
            >
              Approve Selected ({selectedSources.size})
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        {['all', 'staged', 'approved', 'rejected', 'training'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-xl text-sm font-bold transition-all ${filter === f
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-100 text-red-600 p-6 rounded-2xl text-sm font-bold">
          {error}
        </div>
      )}

      {queueStatus && (
        <div className={`border p-6 rounded-2xl text-sm font-bold ${
          queueStatus.failed > 0 
            ? 'bg-yellow-50 border-yellow-200 text-yellow-800' 
            : 'bg-green-50 border-green-200 text-green-800'
        }`}>
          <div className="flex items-center gap-2 mb-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>Queue Processing Complete</span>
          </div>
          <div className="text-xs mt-2 space-y-1">
            <div>Processed: {queueStatus.processed} job(s)</div>
            {queueStatus.failed > 0 && <div>Failed: {queueStatus.failed} job(s)</div>}
            {queueStatus.remaining > 0 && <div>Remaining: {queueStatus.remaining} job(s)</div>}
          </div>
        </div>
      )}

      {/* Sources Table */}
      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
        <div className="p-8 border-b border-slate-100">
          <h3 className="text-lg font-black text-slate-800">Staged Sources</h3>
        </div>

        {loading ? (
          <div className="p-20 flex justify-center">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600"></div>
          </div>
        ) : filteredSources.length === 0 ? (
          <div className="p-32 text-center">
            <p className="text-slate-500">No sources in staging</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-50/50">
                  <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">
                    <input
                      type="checkbox"
                      checked={selectedSources.size === filteredSources.length && filteredSources.length > 0}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedSources(new Set(filteredSources.map(s => s.id)));
                        } else {
                          setSelectedSources(new Set());
                        }
                      }}
                      className="rounded"
                    />
                  </th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Filename</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Status</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Health</th>
                  <th className="px-8 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Created</th>
                  <th className="px-8 py-5 text-right"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {filteredSources.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-8 py-6">
                      <input
                        type="checkbox"
                        checked={selectedSources.has(s.id)}
                        onChange={(e) => {
                          const newSet = new Set(selectedSources);
                          if (e.target.checked) {
                            newSet.add(s.id);
                          } else {
                            newSet.delete(s.id);
                          }
                          setSelectedSources(newSet);
                        }}
                        className="rounded"
                      />
                    </td>
                    <td className="px-8 py-6">
                      <div className="font-bold text-slate-800 text-sm">{s.filename}</div>
                      {s.extracted_text_length && (
                        <div className="text-xs text-slate-500 mt-1">
                          {s.extracted_text_length.toLocaleString()} chars
                        </div>
                      )}
                    </td>
                    <td className="px-8 py-6">{getStagingBadge(s.staging_status || 'staged')}</td>
                    <td className="px-8 py-6">{getHealthBadge(s.health_status || 'healthy')}</td>
                    <td className="px-8 py-6 text-xs font-bold text-slate-400">
                      {new Date(s.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-8 py-6 text-right">
                      <div className="flex gap-2 justify-end">
                        <button
                          onClick={() => router.push(`/dashboard/knowledge/${s.id}`)}
                          className="px-3 py-1.5 bg-slate-100 text-slate-700 rounded-lg text-xs font-bold hover:bg-slate-200 transition-all"
                        >
                          View
                        </button>
                        {s.staging_status === 'staged' && (
                          <>
                            <button
                              onClick={() => handleApprove(s.id)}
                              className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-xs font-bold hover:bg-green-700 transition-all"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => handleReject(s.id)}
                              className="px-3 py-1.5 bg-red-600 text-white rounded-lg text-xs font-bold hover:bg-red-700 transition-all"
                            >
                              Reject
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
