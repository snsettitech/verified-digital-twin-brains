'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';
import { resolveApiBaseUrl } from '@/lib/api';
import { useTwin } from '@/lib/context/TwinContext';

type JsonValue = Record<string, unknown> | unknown[] | string | number | boolean | null;

export default function RetrievalDebugPage() {
    const { activeTwin } = useTwin();
    const baseUrl = resolveApiBaseUrl();
    const twinId = activeTwin?.id || '';

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [query, setQuery] = useState('who are you');
    const [topK, setTopK] = useState(8);

    const [healthData, setHealthData] = useState<JsonValue>(null);
    const [namespaceData, setNamespaceData] = useState<JsonValue>(null);
    const [metricsData, setMetricsData] = useState<JsonValue>(null);
    const [retrievalData, setRetrievalData] = useState<JsonValue>(null);
    const [vectorData, setVectorData] = useState<JsonValue>(null);

    const canRun = !!twinId;

    const getAuthHeaders = useCallback(async () => {
        const supabase = getSupabaseClient();
        const { data: { session } } = await supabase.auth.getSession();
        if (!session?.access_token) {
            throw new Error('Not authenticated');
        }
        return {
            Authorization: `Bearer ${session.access_token}`,
            'Content-Type': 'application/json',
        };
    }, []);

    const fetchJson = useCallback(
        async (url: string, init?: RequestInit) => {
            const headers = await getAuthHeaders();
            const res = await fetch(url, {
                ...init,
                headers: {
                    ...headers,
                    ...(init?.headers || {}),
                },
            });
            if (!res.ok) {
                let details = '';
                try {
                    details = JSON.stringify(await res.json());
                } catch {
                    details = await res.text();
                }
                throw new Error(`${res.status} ${res.statusText}${details ? ` - ${details}` : ''}`);
            }
            return res.json();
        },
        [getAuthHeaders],
    );

    const refreshDiagnostics = useCallback(async () => {
        if (!twinId) return;
        setLoading(true);
        setError(null);
        try {
            const [health, namespaces, metrics] = await Promise.all([
                fetchJson(`${baseUrl}/debug/retrieval/health?twin_id=${encodeURIComponent(twinId)}`),
                fetchJson(`${baseUrl}/debug/retrieval/namespaces/${encodeURIComponent(twinId)}`),
                fetchJson(`${baseUrl}/debug/retrieval/metrics`),
            ]);
            setHealthData(health);
            setNamespaceData(namespaces);
            setMetricsData(metrics);
        } catch (err) {
            console.error(err);
            setError(err instanceof Error ? err.message : 'Failed to load diagnostics.');
        } finally {
            setLoading(false);
        }
    }, [baseUrl, fetchJson, twinId]);

    const runRetrievalDebug = useCallback(async () => {
        if (!twinId || !query.trim()) return;
        setLoading(true);
        setError(null);
        try {
            const payload = {
                query: query.trim(),
                twin_id: twinId,
                top_k: topK,
            };
            const [retrieval, vector] = await Promise.all([
                fetchJson(`${baseUrl}/debug/retrieval`, {
                    method: 'POST',
                    body: JSON.stringify(payload),
                }),
                fetchJson(`${baseUrl}/debug/retrieval/vector-search`, {
                    method: 'POST',
                    body: JSON.stringify(payload),
                }),
            ]);
            setRetrievalData(retrieval);
            setVectorData(vector);
        } catch (err) {
            console.error(err);
            setError(err instanceof Error ? err.message : 'Failed to run retrieval debug.');
        } finally {
            setLoading(false);
        }
    }, [baseUrl, fetchJson, query, topK, twinId]);

    useEffect(() => {
        if (twinId) {
            refreshDiagnostics();
        } else {
            setHealthData(null);
            setNamespaceData(null);
            setMetricsData(null);
            setRetrievalData(null);
            setVectorData(null);
            setError(null);
        }
    }, [refreshDiagnostics, twinId]);

    const sections = useMemo(
        () => [
            { title: 'Health', data: healthData },
            { title: 'Namespaces', data: namespaceData },
            { title: 'Metrics', data: metricsData },
            { title: 'Retrieval Result', data: retrievalData },
            { title: 'Raw Vector Search', data: vectorData },
        ],
        [healthData, metricsData, namespaceData, retrievalData, vectorData],
    );

    return (
        <div className="min-h-screen bg-[#0a0a0f] text-white p-6 md:p-10">
            <div className="max-w-6xl mx-auto space-y-4">
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <h1 className="text-2xl font-black tracking-tight">Retrieval Debug</h1>
                        <p className="text-sm text-slate-400 mt-1">
                            Dedicated diagnostics page for retrieval health, namespace coverage, and query behavior.
                        </p>
                    </div>
                    <Link
                        href="/dashboard/simulator"
                        className="px-3 py-2 text-xs font-semibold rounded-lg border border-white/15 bg-white/5 hover:bg-white/10 transition-colors"
                    >
                        Back to Hub
                    </Link>
                </div>

                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 space-y-3">
                    <div className="text-xs uppercase tracking-wider text-slate-400">Debug Controls</div>
                    <div className="grid grid-cols-1 md:grid-cols-[1fr_100px_220px] gap-3">
                        <input
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="Enter test query..."
                            className="px-3 py-2 rounded-xl bg-black/30 border border-white/10 text-sm"
                        />
                        <input
                            type="number"
                            min={1}
                            max={20}
                            value={topK}
                            onChange={(e) => setTopK(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
                            className="px-3 py-2 rounded-xl bg-black/30 border border-white/10 text-sm"
                        />
                        <div className="flex items-center gap-2">
                            <button
                                onClick={refreshDiagnostics}
                                disabled={!canRun || loading}
                                className="px-3 py-2 text-xs font-semibold rounded-lg bg-slate-700 hover:bg-slate-600 disabled:opacity-50"
                            >
                                Refresh
                            </button>
                            <button
                                onClick={runRetrievalDebug}
                                disabled={!canRun || loading || !query.trim()}
                                className="px-3 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50"
                            >
                                Run Query
                            </button>
                        </div>
                    </div>
                    <div className="text-xs text-slate-400">
                        Active Twin: <span className="text-slate-200">{twinId || 'None selected'}</span>
                    </div>
                    {error && <div className="text-xs text-rose-300">{error}</div>}
                </div>

                <div className="grid grid-cols-1 gap-4">
                    {sections.map((section) => (
                        <section key={section.title} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                            <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">{section.title}</div>
                            <pre className="text-xs text-slate-200 bg-black/30 border border-white/10 rounded-xl p-3 overflow-x-auto">
                                {JSON.stringify(section.data ?? { message: 'No data yet' }, null, 2)}
                            </pre>
                        </section>
                    ))}
                </div>
            </div>
        </div>
    );
}
