'use client';

import React, { useCallback, useEffect, useState } from 'react';
import FeatureGate from '@/components/ui/FeatureGate';
import { isRuntimeFeatureEnabled } from '@/lib/features/runtimeFlags';
import { useTwin } from '@/lib/context/TwinContext';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';

type AccessLog = {
  id?: string;
  created_at?: string;
  action?: string;
  event_type?: string;
  metadata?: Record<string, any>;
};

export default function PrivacyPage() {
  const enabled = isRuntimeFeatureEnabled('privacyControls');
  const { activeTwin, refreshTwins } = useTwin();
  const { get, patch } = useAuthFetch();

  const twinId = activeTwin?.id;
  const [retention, setRetention] = useState('90_days');
  const [memoryRetention, setMemoryRetention] = useState('forever');
  const [saving, setSaving] = useState(false);
  const [logs, setLogs] = useState<AccessLog[]>([]);
  const [logsState, setLogsState] = useState<'idle' | 'loading' | 'ready' | 'unavailable'>('idle');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const settings = (activeTwin?.settings || {}) as Record<string, any>;
    const privacy = (settings?.privacy || {}) as Record<string, any>;
    setRetention(String(privacy.conversation_retention || '90_days'));
    setMemoryRetention(String(privacy.memory_retention || 'forever'));
  }, [activeTwin?.settings]);

  const fetchLogs = useCallback(async () => {
    if (!twinId) return;
    setLogsState('loading');
    try {
      const res = await get(`/twins/${twinId}/logs?limit=50`);
      if (res.status === 404 || res.status === 501) {
        setLogs([]);
        setLogsState('unavailable');
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to load logs (${res.status})`);
      }
      const data = await res.json();
      setLogs(Array.isArray(data?.logs) ? data.logs : []);
      setLogsState('ready');
    } catch (err: any) {
      setLogs([]);
      setLogsState('unavailable');
      setError(err?.message || 'Unable to load logs.');
    }
  }, [get, twinId]);

  useEffect(() => {
    if (twinId) {
      void fetchLogs();
    }
  }, [twinId, fetchLogs]);

  const savePrivacySettings = async () => {
    if (!twinId) return;
    setSaving(true);
    setError(null);
    try {
      const currentSettings = (activeTwin?.settings || {}) as Record<string, any>;
      const nextSettings = {
        ...currentSettings,
        privacy: {
          ...(currentSettings.privacy || {}),
          conversation_retention: retention,
          memory_retention: memoryRetention,
        },
      };
      const res = await patch(`/twins/${twinId}`, { settings: nextSettings });
      if (!res.ok) {
        throw new Error(`Failed to save settings (${res.status})`);
      }
      await refreshTwins();
    } catch (err: any) {
      setError(err?.message || 'Failed to save privacy settings.');
    } finally {
      setSaving(false);
    }
  };

  const requestExport = async () => {
    if (!twinId) return;
    setError(null);
    try {
      const res = await get(`/twins/${twinId}/export`);
      if (!res.ok) {
        throw new Error(`Export request failed (${res.status})`);
      }
      const contentDisposition = res.headers.get('content-disposition') || '';
      const fileNameMatch = contentDisposition.match(/filename=\"?([^\";]+)\"?/i);
      const fileName = fileNameMatch?.[1] || `twin_${twinId}_export.json`;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = fileName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err?.message || 'Failed to request export.');
    }
  };

  return (
    <FeatureGate
      enabled={enabled}
      title="Privacy & Data"
      description="Enable NEXT_PUBLIC_FF_PRIVACY_CONTROLS to access privacy controls."
    >
      <div className="space-y-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-slate-900">Privacy & Data</h1>
          <p className="mt-1 text-sm text-slate-600">
            Private by default. You control retention, exports, and deletion for this twin.
          </p>
        </div>

        {error ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
        ) : null}

        <div className="grid gap-4 lg:grid-cols-2">
          <section className="rounded-2xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">Retention</h2>
            <div className="mt-4 grid gap-3">
              <label className="text-sm text-slate-700">
                Conversation Retention
                <select
                  value={retention}
                  onChange={(e) => setRetention(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                >
                  <option value="30_days">30 days</option>
                  <option value="90_days">90 days</option>
                  <option value="1_year">1 year</option>
                  <option value="forever">Forever</option>
                </select>
              </label>
              <label className="text-sm text-slate-700">
                Memory Retention
                <select
                  value={memoryRetention}
                  onChange={(e) => setMemoryRetention(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                >
                  <option value="forever">Forever</option>
                  <option value="1_year">Auto-delete after 1 year</option>
                </select>
              </label>
              <button
                onClick={savePrivacySettings}
                disabled={saving || !twinId}
                className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save Privacy Settings'}
              </button>
            </div>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">Export & Delete</h2>
            <div className="mt-4 space-y-3">
              <button
                onClick={requestExport}
                disabled={!twinId}
                className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2 text-left text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                Export Twin Data
              </button>
              <a
                href="/dashboard/settings"
                className="block w-full rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-left text-sm font-semibold text-rose-700 hover:bg-rose-100"
              >
                Go to Delete Twin (Danger Zone)
              </a>
            </div>
          </section>
        </div>

        <section className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">Access Logs</h2>
            <button
              onClick={fetchLogs}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              Refresh
            </button>
          </div>
          {logsState === 'loading' && <div className="mt-3 text-sm text-slate-500">Loading logs...</div>}
          {logsState === 'unavailable' && (
            <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              Access logs endpoint is unavailable in this deployment. This control is intentionally read-only.
            </div>
          )}
          {logsState === 'ready' && logs.length === 0 && (
            <div className="mt-3 text-sm text-slate-500">No logs found for this twin.</div>
          )}
          {logsState === 'ready' && logs.length > 0 && (
            <div className="mt-3 space-y-2">
              {logs.map((log, idx) => (
                <div key={log.id || idx} className="rounded-xl border border-slate-200 p-3 text-sm">
                  <div className="font-semibold text-slate-800">{log.action || log.event_type || 'event'}</div>
                  <div className="text-xs text-slate-500">{log.created_at || 'unknown time'}</div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </FeatureGate>
  );
}
