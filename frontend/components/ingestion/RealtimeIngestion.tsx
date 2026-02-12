'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';
import { API_BASE_URL, API_ENDPOINTS } from '@/lib/constants';

type RealtimeEventType = 'transcript_partial' | 'transcript_final' | 'text' | 'marker';

interface RealtimeSession {
  id: string;
  twin_id: string;
  source_id?: string;
  status: 'active' | 'committed' | 'failed' | 'cancelled' | string;
  last_sequence_no?: number;
  appended_chars?: number;
  indexed_chars?: number;
  last_indexed_at?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at?: string;
  updated_at?: string;
}

interface RealtimeAppendResponse {
  status: string;
  append?: {
    status: string;
    session: RealtimeSession;
    event: Record<string, unknown>;
    should_index: boolean;
  };
  processing?: Record<string, unknown> | null;
  queued_job?: Record<string, unknown> | null;
  queue_error?: string | null;
}

interface RealtimeCommitResponse {
  status: string;
  session?: RealtimeSession;
  queued_job?: Record<string, unknown>;
  processing?: Record<string, unknown>;
  queue_error?: string;
  source_id?: string;
  job_id?: string;
}

interface RealtimeHealthResponse {
  status: 'healthy' | 'degraded' | string;
  schema_available?: boolean;
  error?: string | null;
}

interface RealtimeEventRow {
  id: string;
  session_id: string;
  sequence_no: number;
  event_type: RealtimeEventType | string;
  text_chunk: string;
  chars_count: number;
  created_at: string;
}

export default function RealtimeIngestion({
  twinId,
  onComplete,
}: {
  twinId: string;
  onComplete?: (result: { source_id: string; status: string }) => void;
}) {
  const supabase = getSupabaseClient();

  const [health, setHealth] = useState<RealtimeHealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  const [session, setSession] = useState<RealtimeSession | null>(null);
  const [events, setEvents] = useState<RealtimeEventRow[]>([]);

  const [title, setTitle] = useState('');
  const [eventType, setEventType] = useState<RealtimeEventType>('text');
  const [chunk, setChunk] = useState('');
  const [sequenceNo, setSequenceNo] = useState(1);
  const [processNow, setProcessNow] = useState(false);
  const [enqueueWhenReady, setEnqueueWhenReady] = useState(true);
  const [commitAsync, setCommitAsync] = useState(true);

  const [busy, setBusy] = useState(false);
  const [statusText, setStatusText] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const pollTimerRef = useRef<number | null>(null);

  const schemaAvailable = Boolean(health?.schema_available);

  const getAuthToken = useCallback(async (): Promise<string | null> => {
    const {
      data: { session: authSession },
    } = await supabase.auth.getSession();
    return authSession?.access_token || null;
  }, [supabase]);

  const headersForToken = useCallback((token: string) => {
    return {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    } as const;
  }, []);

  const sessionLagChars = useMemo(() => {
    if (!session) return null;
    const appended = Number(session.appended_chars || 0);
    const indexed = Number(session.indexed_chars || 0);
    return appended - indexed;
  }, [session]);

  const fetchHealth = useCallback(async () => {
    setHealthError(null);
    try {
      const token = await getAuthToken().catch(() => null);
      const res = await fetch(`${API_BASE_URL}${API_ENDPOINTS.INGEST_REALTIME_HEALTH}`, {
        method: 'GET',
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });

      // If realtime routes are not mounted (ENABLE_REALTIME_INGESTION=false), we expect 404.
      if (res.status === 404) {
        setHealth({
          status: 'disabled',
          schema_available: false,
          error: 'Realtime ingestion routes are disabled on this backend.',
        });
        return;
      }

      if (res.status === 401 || res.status === 403) {
        setHealthError('Not authenticated');
        setHealth(null);
        return;
      }

      const data = (await res.json()) as RealtimeHealthResponse;
      setHealth(data);
    } catch (e: any) {
      setHealthError(e?.message || 'Failed to check realtime ingestion health');
      setHealth(null);
    }
  }, [getAuthToken]);

  const fetchSession = useCallback(
    async (sessionId: string) => {
      const token = await getAuthToken();
      if (!token) throw new Error('Not authenticated');
      const res = await fetch(`${API_BASE_URL}${API_ENDPOINTS.INGEST_REALTIME_SESSION(sessionId)}`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail || `Failed to fetch session (${res.status})`);
      }
      const data = await res.json();
      setSession(data.session as RealtimeSession);
      return data.session as RealtimeSession;
    },
    [getAuthToken]
  );

  const fetchEvents = useCallback(
    async (sessionId: string) => {
      const token = await getAuthToken();
      if (!token) throw new Error('Not authenticated');
      const url = new URL(`${API_BASE_URL}${API_ENDPOINTS.INGEST_REALTIME_SESSION(sessionId)}/events`);
      // Prefer the canonical endpoint helper when available, but keep this robust to refactors.
      url.searchParams.set('after_sequence_no', '0');
      url.searchParams.set('limit', '200');

      const res = await fetch(url.toString(), {
        method: 'GET',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail || `Failed to fetch events (${res.status})`);
      }
      const data = await res.json();
      const rows = (data.events || []) as RealtimeEventRow[];
      setEvents(rows);
      return rows;
    },
    [getAuthToken]
  );

  const startSession = useCallback(async () => {
    setError(null);
    setStatusText('');
    setBusy(true);
    try {
      const token = await getAuthToken();
      if (!token) throw new Error('Not authenticated');

      const res = await fetch(`${API_BASE_URL}${API_ENDPOINTS.INGEST_REALTIME_START(twinId)}`, {
        method: 'POST',
        headers: headersForToken(token),
        body: JSON.stringify({
          source_type: 'realtime_stream',
          title: title.trim() || null,
          metadata: {
            ui: 'realtime_ingestion_v1',
          },
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail || `Failed to start session (${res.status})`);
      }
      const data = await res.json();
      const next = data.session as RealtimeSession;
      setSession(next);
      setEvents([]);
      setSequenceNo(1);
      setStatusText('Session started.');
    } catch (e: any) {
      setError(e?.message || 'Failed to start realtime session');
    } finally {
      setBusy(false);
    }
  }, [getAuthToken, headersForToken, title, twinId]);

  const appendChunk = useCallback(async () => {
    if (!session?.id) return;
    if (!chunk.trim()) return;
    setError(null);
    setStatusText('');
    setBusy(true);
    try {
      const token = await getAuthToken();
      if (!token) throw new Error('Not authenticated');

      const res = await fetch(`${API_BASE_URL}${API_ENDPOINTS.INGEST_REALTIME_APPEND(session.id)}`, {
        method: 'POST',
        headers: headersForToken(token),
        body: JSON.stringify({
          sequence_no: sequenceNo,
          text_chunk: chunk,
          event_type: eventType,
          metadata: {
            ui: 'realtime_ingestion_v1',
            client_ts: new Date().toISOString(),
          },
          process_now: Boolean(processNow),
          enqueue_when_ready: Boolean(enqueueWhenReady),
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail || `Failed to append chunk (${res.status})`);
      }
      const data = (await res.json()) as RealtimeAppendResponse;
      const nextSession = data?.append?.session;
      if (nextSession) setSession(nextSession);
      setSequenceNo((n) => n + 1);
      setChunk('');
      setStatusText(
        data?.queued_job
          ? 'Chunk appended (queued indexing).'
          : data?.processing
            ? 'Chunk appended (processed inline).'
            : 'Chunk appended.'
      );

      // Refresh visible event log opportunistically.
      await fetchEvents(session.id).catch(() => {});
    } catch (e: any) {
      setError(e?.message || 'Failed to append chunk');
    } finally {
      setBusy(false);
    }
  }, [
    chunk,
    enqueueWhenReady,
    eventType,
    fetchEvents,
    getAuthToken,
    headersForToken,
    processNow,
    sequenceNo,
    session?.id,
  ]);

  const commitSession = useCallback(async () => {
    if (!session?.id) return;
    setError(null);
    setStatusText('');
    setBusy(true);
    try {
      const token = await getAuthToken();
      if (!token) throw new Error('Not authenticated');

      const res = await fetch(`${API_BASE_URL}${API_ENDPOINTS.INGEST_REALTIME_COMMIT(session.id)}`, {
        method: 'POST',
        headers: headersForToken(token),
        body: JSON.stringify({
          process_async: Boolean(commitAsync),
          metadata: {
            ui: 'realtime_ingestion_v1',
            committed_from: 'frontend',
          },
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail || `Failed to commit session (${res.status})`);
      }
      const data = (await res.json()) as RealtimeCommitResponse;
      if (data.session) setSession(data.session);

      const sourceId =
        (data.session?.source_id as string | undefined) || (session.source_id as string | undefined);
      if (sourceId) onComplete?.({ source_id: sourceId, status: 'live' });

      setStatusText(
        data.status === 'committed_queued'
          ? 'Committed (queued for indexing).'
          : data.status === 'committed_processed_fallback'
            ? 'Committed (indexed inline fallback).'
            : 'Committed.'
      );

      // Refresh session + events once after commit.
      await fetchSession(session.id).catch(() => {});
      await fetchEvents(session.id).catch(() => {});
    } catch (e: any) {
      setError(e?.message || 'Failed to commit session');
    } finally {
      setBusy(false);
    }
  }, [fetchEvents, fetchSession, getAuthToken, headersForToken, onComplete, session?.id, session?.source_id]);

  const reset = useCallback(() => {
    setSession(null);
    setEvents([]);
    setTitle('');
    setChunk('');
    setSequenceNo(1);
    setEventType('text');
    setProcessNow(false);
    setEnqueueWhenReady(true);
    setCommitAsync(true);
    setStatusText('');
    setError(null);
  }, []);

  // Initial health probe
  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  // Poll session status when active, to reflect indexed_chars/appended_chars growth.
  useEffect(() => {
    if (!session?.id) return;
    if (pollTimerRef.current) window.clearInterval(pollTimerRef.current);
    pollTimerRef.current = window.setInterval(() => {
      fetchSession(session.id).catch(() => {});
    }, 4000);

    return () => {
      if (pollTimerRef.current) window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    };
  }, [fetchSession, session?.id]);

  const healthBadge = useMemo(() => {
    if (healthError) return { label: 'ERROR', className: 'bg-red-100 text-red-700' };
    if (!health) return { label: 'CHECKING', className: 'bg-slate-100 text-slate-600' };
    if (health.status === 'disabled') return { label: 'DISABLED', className: 'bg-slate-100 text-slate-600' };
    if (health.schema_available) return { label: 'READY', className: 'bg-green-100 text-green-700' };
    return { label: 'DEGRADED', className: 'bg-yellow-100 text-yellow-700' };
  }, [health, healthError]);

  return (
    <div className="bg-white rounded-[2rem] border border-slate-200 shadow-sm overflow-hidden">
      <div className="p-6 border-b border-slate-100 flex items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-black text-slate-800">Realtime Stream (Phase 5)</h3>
          <p className="text-sm text-slate-500 mt-1">
            Append text chunks in near real-time and index incrementally (no AssemblyAI).
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-1 rounded-lg text-[10px] font-black ${healthBadge.className}`}>
            {healthBadge.label}
          </span>
          <button
            onClick={fetchHealth}
            disabled={busy}
            className="px-3 py-2 rounded-xl text-xs font-bold border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="p-6 space-y-4 bg-slate-50/50">
        {!schemaAvailable && (
          <div className="p-4 bg-slate-100 border border-slate-200 rounded-2xl text-slate-700 text-sm">
            <div className="font-black">Realtime ingestion is not available on this backend.</div>
            <div className="mt-2 text-xs text-slate-600 font-medium">
              {health?.error || healthError || 'Health endpoint unavailable.'}
            </div>
            <div className="mt-2 text-xs text-slate-600 font-medium">
              To enable: set <span className="font-mono">ENABLE_REALTIME_INGESTION=true</span> on the backend service and
              ensure the Phase 5 migrations are applied in Supabase.
            </div>
          </div>
        )}

        {schemaAvailable && !session && (
          <div className="flex flex-col gap-3">
            <div className="flex gap-3">
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Optional title (e.g., Live call transcript)"
                className="flex-1 px-4 py-3 bg-white border border-slate-200 rounded-xl text-sm font-medium outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <button
                onClick={startSession}
                disabled={busy}
                className="px-6 py-3 bg-indigo-600 text-white rounded-xl text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 shadow-lg shadow-indigo-200"
              >
                Start
              </button>
            </div>
            <div className="text-xs text-slate-500 font-medium">
              This creates a realtime source + session, then you can append chunks.
            </div>
          </div>
        )}

        {schemaAvailable && session && (
          <div className="space-y-4">
            <div className="bg-white border border-slate-200 rounded-2xl p-4">
              <div className="flex flex-wrap gap-3 items-center justify-between">
                <div className="space-y-1">
                  <div className="text-xs text-slate-400 font-black uppercase tracking-widest">Session</div>
                  <div className="text-sm font-black text-slate-800 break-all">{session.id}</div>
                  <div className="text-xs text-slate-500 font-bold">
                    Status: <span className="text-slate-800">{String(session.status || 'unknown')}</span>
                    {session.source_id ? (
                      <>
                        {' '}
                        <span className="text-slate-300">|</span> Source:{' '}
                        <span className="font-mono text-slate-700">{session.source_id}</span>
                      </>
                    ) : null}
                  </div>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      if (!session?.id) return;
                      fetchSession(session.id).catch((e) => setError(e?.message || 'Failed to refresh session'));
                      fetchEvents(session.id).catch(() => {});
                    }}
                    disabled={busy}
                    className="px-3 py-2 rounded-xl text-xs font-bold border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                  >
                    Refresh
                  </button>
                  <button
                    onClick={reset}
                    disabled={busy}
                    className="px-3 py-2 rounded-xl text-xs font-bold border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                  >
                    New Session
                  </button>
                </div>
              </div>

              <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                  <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Sequence</div>
                  <div className="text-sm font-black text-slate-800">{sequenceNo}</div>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                  <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Appended</div>
                  <div className="text-sm font-black text-slate-800">{Number(session.appended_chars || 0)} chars</div>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                  <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Index Lag</div>
                  <div className="text-sm font-black text-slate-800">
                    {sessionLagChars === null ? '-' : `${sessionLagChars} chars`}
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-2xl p-4">
              <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
                <div className="flex items-center gap-2">
                  <div className="text-xs font-black text-slate-400 uppercase tracking-widest">Append Chunk</div>
                  <select
                    value={eventType}
                    onChange={(e) => setEventType(e.target.value as RealtimeEventType)}
                    className="px-3 py-2 rounded-xl border border-slate-200 text-xs font-bold text-slate-700 bg-white"
                    disabled={busy}
                  >
                    <option value="text">text</option>
                    <option value="transcript_partial">transcript_partial</option>
                    <option value="transcript_final">transcript_final</option>
                    <option value="marker">marker</option>
                  </select>
                </div>

                <div className="flex flex-wrap gap-3 items-center">
                  <label className="flex items-center gap-2 text-xs font-bold text-slate-600">
                    <input
                      type="checkbox"
                      checked={enqueueWhenReady}
                      onChange={(e) => setEnqueueWhenReady(e.target.checked)}
                      disabled={busy}
                    />
                    Enqueue when ready
                  </label>
                  <label className="flex items-center gap-2 text-xs font-bold text-slate-600">
                    <input
                      type="checkbox"
                      checked={processNow}
                      onChange={(e) => setProcessNow(e.target.checked)}
                      disabled={busy}
                    />
                    Process now
                  </label>
                  <label className="flex items-center gap-2 text-xs font-bold text-slate-600">
                    <input
                      type="checkbox"
                      checked={commitAsync}
                      onChange={(e) => setCommitAsync(e.target.checked)}
                      disabled={busy}
                    />
                    Commit async
                  </label>
                </div>
              </div>

              <textarea
                value={chunk}
                onChange={(e) => setChunk(e.target.value)}
                placeholder="Paste a transcript chunk (append-only). For testing, you can paste PHASE5_MARKER_12345 etc."
                disabled={busy}
                rows={4}
                className="mt-3 w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-sm font-medium outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
              />

              <div className="mt-3 flex gap-3">
                <button
                  onClick={appendChunk}
                  disabled={busy || !chunk.trim()}
                  className="px-6 py-3 bg-indigo-600 text-white rounded-xl text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 shadow-lg shadow-indigo-200"
                >
                  Append
                </button>
                <button
                  onClick={commitSession}
                  disabled={busy}
                  className="px-6 py-3 bg-slate-900 text-white rounded-xl text-sm font-bold hover:bg-slate-800 disabled:opacity-50"
                >
                  Commit
                </button>
              </div>

              {statusText && <div className="mt-3 text-xs text-slate-500 font-bold">{statusText}</div>}
              {error && (
                <div className="mt-3 p-3 bg-red-50 border border-red-100 rounded-xl text-red-700 text-xs font-bold">
                  {error}
                </div>
              )}
            </div>

            <div className="bg-white border border-slate-200 rounded-2xl p-4">
              <div className="flex items-center justify-between">
                <div className="text-xs font-black text-slate-400 uppercase tracking-widest">Recent Events</div>
                <button
                  onClick={() => {
                    if (!session?.id) return;
                    fetchEvents(session.id).catch((e) => setError(e?.message || 'Failed to fetch events'));
                  }}
                  disabled={busy}
                  className="px-3 py-2 rounded-xl text-xs font-bold border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                >
                  Load
                </button>
              </div>
              <div className="mt-3 space-y-2 max-h-56 overflow-auto">
                {events.length === 0 ? (
                  <div className="text-xs text-slate-500 font-medium">No events loaded yet.</div>
                ) : (
                  events
                    .slice(-12)
                    .reverse()
                    .map((ev) => (
                      <div key={ev.id} className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-xs font-black text-slate-700">
                            #{ev.sequence_no} <span className="text-slate-300">|</span>{' '}
                            <span className="text-slate-500">{ev.event_type}</span>
                          </div>
                          <div className="text-[10px] font-bold text-slate-400">
                            {new Date(ev.created_at).toLocaleTimeString()}
                          </div>
                        </div>
                        <div className="mt-2 text-xs text-slate-700 whitespace-pre-wrap break-words">
                          {ev.text_chunk}
                        </div>
                      </div>
                    ))
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
