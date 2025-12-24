'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

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

const twinId = "eeeed554-9180-4229-a9af-0f8dd2c69e9b"; // Fixed for dev

export default function StagingPage() {
  const router = useRouter();
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [selectedSources, setSelectedSources] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const fetchSources = async () => {
    try {
      const response = await fetch(`http://localhost:8000/sources/${twinId}`, {
        headers: { 'Authorization': 'Bearer development_token' }
      });
      if (response.ok) {
        const data = await response.json();
        // Filter to show only staged sources
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
  };

  useEffect(() => {
    fetchSources();
    // Poll for updates every 5 seconds
    const interval = setInterval(fetchSources, 5000);
    return () => clearInterval(interval);
  }, []);

  const filteredSources = sources.filter(s => {
    if (filter === 'all') return true;
    return s.staging_status === filter;
  });

  const handleApprove = async (sourceId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/sources/${sourceId}/approve`, {
        method: 'POST',
        headers: { 
          'Authorization': 'Bearer development_token',
          'Content-Type': 'application/json'
        }
      });
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
      const response = await fetch(`http://localhost:8000/sources/${sourceId}/reject`, {
        method: 'POST',
        headers: { 
          'Authorization': 'Bearer development_token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ reason })
      });
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
      const response = await fetch(`http://localhost:8000/sources/bulk-approve`, {
        method: 'POST',
        headers: { 
          'Authorization': 'Bearer development_token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ source_ids: Array.from(selectedSources) })
      });
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

  return (
    <div className="max-w-6xl mx-auto space-y-10 pb-20">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-black tracking-tight text-slate-900">Content Staging</h1>
          <p className="text-slate-500 mt-2 font-medium">Review and approve content before it enters the brain.</p>
        </div>
        {selectedSources.size > 0 && (
          <button
            onClick={handleBulkApprove}
            className="px-6 py-3 bg-indigo-600 text-white rounded-2xl text-sm font-black hover:bg-indigo-700 transition-all"
          >
            Approve Selected ({selectedSources.size})
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        {['all', 'staged', 'approved', 'rejected', 'training'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-xl text-sm font-bold transition-all ${
              filter === f
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

