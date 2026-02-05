'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useTwin } from '@/lib/context/TwinContext';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';

interface Source {
  id: string;
  filename: string;
  file_size: number;
  status: string;
  health_status: string;
  created_at: string;
  extracted_text_length?: number;
  chunk_count?: number;
  content_text?: string;
  author?: string;
  citation_url?: string;
  publish_date?: string;
}

interface HealthCheck {
  id: string;
  check_type: string;
  status: string;
  message: string;
  metadata: any;
  created_at: string;
}

interface IngestionLog {
  id: string;
  log_level: string;
  message: string;
  metadata: any;
  created_at: string;
}

interface TrainingJob {
  id: string;
  source_id?: string;
  status: string;
  job_type: string;
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export default function SourceDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const { activeTwin, isLoading: twinLoading } = useTwin();
  const { get } = useAuthFetch();

  const sourceId = params.source_id as string;
  const twinId = activeTwin?.id;

  const [source, setSource] = useState<Source | null>(null);
  const [healthChecks, setHealthChecks] = useState<HealthCheck[]>([]);
  const [logs, setLogs] = useState<IngestionLog[]>([]);
  const [trainingJob, setTrainingJob] = useState<TrainingJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'health' | 'logs'>('overview');

  const fetchData = useCallback(async () => {
    if (!twinId) return;

    try {
      const [sourceRes, healthRes, logsRes] = await Promise.all([
        get(`/sources/${twinId}`),
        get(`/sources/${sourceId}/health`),
        get(`/sources/${sourceId}/logs`)
      ]);

      if (sourceRes.ok) {
        const sources = await sourceRes.json();
        const found = sources.find((s: Source) => s.id === sourceId);
        setSource(found || null);
      }

      if (healthRes.ok) {
        const health = await healthRes.json();
        setHealthChecks(health.checks || []);
      }

      if (logsRes.ok) {
        const logsData = await logsRes.json();
        setLogs(logsData);
      }

      // Fetch training job if exists
      const jobsRes = await get(`/training-jobs?twin_id=${twinId}`);
      if (jobsRes.ok) {
        const jobs = await jobsRes.json();
        const job = jobs.find((j: TrainingJob) => j.source_id === sourceId);
        setTrainingJob(job || null);
      }
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  }, [twinId, sourceId, get]);

  useEffect(() => {
    if (twinId) {
      fetchData();
      const interval = setInterval(fetchData, 5000);
      return () => clearInterval(interval);
    } else if (!twinLoading) {
      setLoading(false);
    }
  }, [twinId, twinLoading, fetchData]);


  if (twinLoading || loading) {
    return (
      <div className="max-w-6xl mx-auto p-20 flex justify-center">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (!twinId) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center max-w-md p-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-3">No Twin Found</h2>
          <p className="text-slate-500 mb-6">Create a digital twin first to view knowledge sources.</p>
          <a href="/dashboard/right-brain" className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition-colors">
            Create Your Twin
          </a>
        </div>
      </div>
    );
  }

  if (!source) {
    return (
      <div className="max-w-6xl mx-auto p-20 text-center">
        <p className="text-slate-500">Source not found</p>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-10 pb-20">
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => router.back()}
            className="text-slate-500 hover:text-slate-700 mb-4 text-sm font-bold"
          >
            ← Back
          </button>
          <h1 className="text-4xl font-black tracking-tight text-slate-900">{source.filename}</h1>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-3 border-b border-slate-200">
        {['overview', 'health', 'logs'].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab as any)}
            className={`px-6 py-3 text-sm font-bold transition-all border-b-2 ${activeTab === tab
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-8 space-y-6">
          <div className="grid grid-cols-2 gap-6">
            <div>
              <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Status</h3>
              <p className="text-lg font-black text-slate-800">{source.status}</p>
            </div>
            <div>
              <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Health</h3>
              <p className="text-lg font-black text-slate-800">{source.health_status || 'healthy'}</p>
            </div>
            <div>
              <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-2">File Size</h3>
              <p className="text-lg font-black text-slate-800">{(source.file_size / 1024).toFixed(2)} KB</p>
            </div>
            <div>
              <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Text Length</h3>
              <p className="text-lg font-black text-slate-800">
                {source.extracted_text_length?.toLocaleString() || 'N/A'} chars
              </p>
            </div>
            {source.chunk_count && (
              <div>
                <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Chunks</h3>
                <p className="text-lg font-black text-slate-800">{source.chunk_count}</p>
              </div>
            )}
            {source.author && (
              <div>
                <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Author</h3>
                <p className="text-lg font-black text-slate-800">{source.author}</p>
              </div>
            )}
          </div>

          {trainingJob && (
            <div className="border-t border-slate-200 pt-6">
              <h3 className="text-sm font-black text-slate-800 mb-4">Training Job</h3>
              <div className="bg-slate-50 p-4 rounded-xl">
                <p className="text-sm text-slate-600">
                  Status: <span className="font-bold">{trainingJob.status}</span>
                </p>
                {trainingJob.error_message && (
                  <p className="text-sm text-red-600 mt-2">{trainingJob.error_message}</p>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Health Checks Tab */}
      {activeTab === 'health' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-8">
          <h3 className="text-lg font-black text-slate-800 mb-6">Health Check Results</h3>
          {healthChecks.length === 0 ? (
            <p className="text-slate-500">No health checks performed</p>
          ) : (
            <div className="space-y-4">
              {healthChecks.map((check) => (
                <div key={check.id} className="border border-slate-200 rounded-xl p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-slate-800">{check.check_type}</span>
                    <span className={`px-2 py-1 text-xs font-bold rounded ${check.status === 'pass' ? 'bg-green-100 text-green-700' :
                      check.status === 'fail' ? 'bg-red-100 text-red-700' :
                        'bg-yellow-100 text-yellow-700'
                      }`}>
                      {check.status.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-sm text-slate-600">{check.message}</p>
                  <p className="text-xs text-slate-400 mt-2">
                    {new Date(check.created_at).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Logs Tab */}
      {activeTab === 'logs' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-8">
          <h3 className="text-lg font-black text-slate-800 mb-6">Ingestion Logs</h3>
          {logs.length === 0 ? (
            <p className="text-slate-500">No logs available</p>
          ) : (
            <div className="space-y-3">
              {logs.map((log) => (
                <div key={log.id} className="flex items-start gap-4 p-4 bg-slate-50 rounded-xl">
                  <span className={`px-2 py-1 text-xs font-bold rounded ${log.log_level === 'error' ? 'bg-red-100 text-red-700' :
                    log.log_level === 'warning' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-blue-100 text-blue-700'
                    }`}>
                    {log.log_level.toUpperCase()}
                  </span>
                  <div className="flex-1">
                    <p className="text-sm text-slate-800">{log.message}</p>
                    <p className="text-xs text-slate-400 mt-1">
                      {new Date(log.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
