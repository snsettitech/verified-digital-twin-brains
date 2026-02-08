'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';
import { resolveApiBaseUrl } from '@/lib/api';

interface Source {
    id: string;
    name: string;
    type: 'document' | 'url' | 'interview';
    provider?: string;
    citationUrl?: string | null;
    status: 'live' | 'pending' | 'processing' | 'error';
    createdAt: string;
    updatedAt?: string;
    chunks?: number;
    lastStep?: string;
    lastError?: any;
}

interface KnowledgeTabProps {
    twinId: string;
    sources?: Source[];
    onUpload?: (files: File[]) => Promise<any> | any;
    onUrlSubmit?: (url: string) => Promise<any> | any;
}

type SourceEvent = {
    id: string;
    provider: string;
    step: string;
    status: string;
    message?: string | null;
    error?: any;
    started_at?: string | null;
    created_at?: string | null;
};

type IngestionLog = {
    id: string;
    log_level: string;
    message: string;
    metadata?: any;
    created_at?: string | null;
};

function inferProviderFromText(text: string): string {
    const t = (text || '').toLowerCase();
    if (t.includes('youtube.com') || t.includes('youtu.be') || t.includes('youtube:')) return 'youtube';
    if (t.includes('x.com') || t.includes('twitter.com') || t.includes('x thread')) return 'x';
    if (t.includes('linkedin.com')) return 'linkedin';
    if (t.includes('.rss') || t.includes('podcast') || t.includes('anchor.fm') || t.includes('podbean')) return 'podcast';
    if (t.startsWith('http://') || t.startsWith('https://')) return 'web';
    return 'file';
}

function formatUpdatedAt(iso?: string): string {
    if (!iso) return '';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '';
    return d.toLocaleString();
}

export function KnowledgeTab({ twinId, sources = [], onUpload, onUrlSubmit }: KnowledgeTabProps) {
    const supabase = getSupabaseClient();
    const isE2EBypass =
        process.env.NODE_ENV !== 'production' &&
        process.env.NEXT_PUBLIC_E2E_BYPASS_AUTH === '1';
    const [activeView, setActiveView] = useState<'list' | 'graph'>('list');
    const [showUploadModal, setShowUploadModal] = useState(false);
    const [url, setUrl] = useState('');
    const [loadedSources, setLoadedSources] = useState<Source[]>(sources);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [submittingUrl, setSubmittingUrl] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const retryRef = useRef(0);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const [diagOpen, setDiagOpen] = useState(false);
    const [diagSource, setDiagSource] = useState<Source | null>(null);
    const [diagEvents, setDiagEvents] = useState<SourceEvent[]>([]);
    const [diagLogs, setDiagLogs] = useState<IngestionLog[]>([]);
    const [diagLoading, setDiagLoading] = useState(false);
    const [diagError, setDiagError] = useState<string | null>(null);

    const fetchSources = useCallback(async (opts?: { quiet?: boolean }): Promise<Source[]> => {
        const quiet = Boolean(opts?.quiet);
        if (!quiet) {
            setLoading(true);
            setError(null);
            setNotice(null);
        }
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token && !isE2EBypass) {
                if (retryRef.current < 5) {
                    retryRef.current += 1;
                    setTimeout(fetchSources, 600);
                } else {
                    setError('Not authenticated.');
                    setLoadedSources([]);
                }
                return [];
            }
            const backendUrl = resolveApiBaseUrl();
            const headers: Record<string, string> = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;
            const res = await fetch(`${backendUrl}/sources/${twinId}`, {
                headers
            });
            if (!res.ok) {
                const errText = await res.text();
                throw new Error(errText || 'Failed to load sources');
            }
            const data = await res.json();
            const mapped = (Array.isArray(data) ? data : []).map((source: any) => {
                const rawStatus = (source.status || 'pending').toString().toLowerCase();
                let status: Source['status'] = 'pending';
                if (['live', 'processed', 'indexed'].includes(rawStatus)) status = 'live';
                else if (rawStatus === 'processing') status = 'processing';
                else if (rawStatus === 'error' || rawStatus === 'failed') status = 'error';

                const filename = source.filename || source.file_url || source.citation_url || 'Untitled source';
                const isUrl = typeof filename === 'string' && (filename.startsWith('http://') || filename.startsWith('https://'));
                return {
                    id: source.id,
                    name: filename,
                    type: isUrl ? 'url' : 'document',
                    provider: source.last_provider || inferProviderFromText(source.citation_url || filename),
                    citationUrl: source.citation_url || source.file_url || null,
                    status,
                    createdAt: source.created_at ? new Date(source.created_at).toLocaleDateString() : '',
                    updatedAt: source.last_event_at || source.last_error_at || source.created_at || undefined,
                    chunks: source.chunk_count || undefined,
                    lastStep: source.last_step || undefined,
                    lastError: source.last_error || undefined
                } as Source;
            });
            setLoadedSources(mapped);
            return mapped;
        } catch (err: any) {
            console.error(err);
            if (!quiet) setError('Failed to load sources.');
            setLoadedSources([]);
            return [];
        } finally {
            if (!quiet) setLoading(false);
        }
    }, [supabase, twinId, isE2EBypass]);

    useEffect(() => {
        fetchSources();
        const { data } = supabase.auth.onAuthStateChange((_event: string, session: { access_token?: string } | null) => {
            if (session?.access_token) {
                retryRef.current = 0;
                fetchSources();
            }
        });
        return () => {
            data?.subscription?.unsubscribe();
        };
    }, [fetchSources, supabase]);

    const statusColors: Record<Source['status'], string> = {
        live: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
        pending: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
        processing: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
        error: 'bg-rose-500/15 text-rose-300 border-rose-500/30'
    };

    const typeIcons = {
        document: '📄',
        url: '🔗',
        interview: '🎙️'
    };

    const startPolling = useCallback(() => {
        if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }

        const startedAt = Date.now();
        const pollMs = 2000;
        const timeoutMs = 90_000;

        pollRef.current = setInterval(async () => {
            const current = await fetchSources({ quiet: true });
            const inFlight = current.some((s) => s.status === 'pending' || s.status === 'processing');

            if (!inFlight) {
                if (pollRef.current) clearInterval(pollRef.current);
                pollRef.current = null;
                return;
            }

            if (Date.now() - startedAt > timeoutMs) {
                if (pollRef.current) clearInterval(pollRef.current);
                pollRef.current = null;
                setNotice('Still processing. Open diagnostics for details or retry.');
            }
        }, pollMs);
    }, [fetchSources]);

    useEffect(() => {
        return () => {
            if (pollRef.current) clearInterval(pollRef.current);
        };
    }, []);

    const retrySource = useCallback(async (sourceId: string) => {
        setError(null);
        setNotice(null);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token && !isE2EBypass) throw new Error('Not authenticated');

            const backendUrl = resolveApiBaseUrl();
            const headers: Record<string, string> = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;
            const res = await fetch(`${backendUrl}/sources/${sourceId}/retry`, {
                method: 'POST',
                headers
            });
            if (!res.ok) {
                const errText = await res.text();
                throw new Error(errText || `Retry failed (${res.status})`);
            }

            await fetchSources();
            startPolling();
        } catch (e) {
            console.error(e);
            setError('Failed to retry source.');
        }
    }, [fetchSources, startPolling, supabase, isE2EBypass]);

    const openDiagnostics = useCallback(async (source: Source) => {
        setDiagOpen(true);
        setDiagSource(source);
        setDiagLoading(true);
        setDiagError(null);
        setDiagEvents([]);
        setDiagLogs([]);

        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token && !isE2EBypass) throw new Error('Not authenticated');

            const backendUrl = resolveApiBaseUrl();
            const headers: Record<string, string> = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;
            const [eventsRes, logsRes] = await Promise.all([
                fetch(`${backendUrl}/sources/${source.id}/events`, { headers }),
                fetch(`${backendUrl}/sources/${source.id}/logs`, { headers })
            ]);

            if (eventsRes.ok) {
                const eventsData = await eventsRes.json();
                setDiagEvents(Array.isArray(eventsData) ? (eventsData as SourceEvent[]) : []);
            } else {
                try {
                    const j = await eventsRes.json();
                    setDiagError(j?.detail || 'Diagnostics events unavailable.');
                } catch {
                    setDiagError('Diagnostics events unavailable.');
                }
            }

            if (logsRes.ok) {
                const logsData = await logsRes.json();
                setDiagLogs(Array.isArray(logsData) ? (logsData as IngestionLog[]) : []);
            }
        } catch (e: any) {
            console.error(e);
            setDiagError(e?.message || 'Failed to load diagnostics.');
        } finally {
            setDiagLoading(false);
        }
    }, [supabase, isE2EBypass]);

    const handleUrlSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        const trimmed = url.trim();
        if (!trimmed) return;

        setSubmittingUrl(true);
        setError(null);
        setNotice(null);
        try {
            const result = onUrlSubmit?.(trimmed);
            if (result && typeof (result as Promise<any>).then === 'function') {
                await result;
            }
            setUrl('');
            await fetchSources();
            startPolling();
        } catch (err) {
            console.error(err);
            setError('Failed to add URL.');
        } finally {
            setSubmittingUrl(false);
        }
    };

    return (
        <div className="p-6 space-y-6">
            {/* Header Actions */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setActiveView('list')}
                        className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${activeView === 'list'
                            ? 'bg-white/10 text-white'
                            : 'text-slate-400 hover:text-white hover:bg-white/5'
                            }`}
                    >
                        <span className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                            </svg>
                            List View
                        </span>
                    </button>
                    <button
                        onClick={() => setActiveView('graph')}
                        className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${activeView === 'graph'
                            ? 'bg-white/10 text-white'
                            : 'text-slate-400 hover:text-white hover:bg-white/5'
                            }`}
                    >
                        <span className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                            </svg>
                            Graph View
                        </span>
                    </button>
                </div>

                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setShowUploadModal(true)}
                        className="px-4 py-2 text-sm font-semibold text-white bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 rounded-lg shadow-lg shadow-indigo-500/20 transition-all"
                    >
                        <span className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                            </svg>
                            Add Knowledge
                        </span>
                    </button>
                </div>
            </div>

            {/* Add URL Quick Form */}
            <form onSubmit={handleUrlSubmit} className="flex gap-3">
                <input
                    type="url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="Paste a URL (YouTube, X thread, RSS, LinkedIn, website)..."
                    className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                />
                <button
                    type="submit"
                    disabled={!url.trim() || submittingUrl}
                    className="px-6 py-3 text-sm font-medium text-white bg-white/10 hover:bg-white/15 border border-white/10 rounded-xl transition-all disabled:opacity-50"
                >
                    {submittingUrl ? 'Adding...' : 'Add URL'}
                </button>
            </form>

            {/* Content View */}
            {activeView === 'list' ? (
                <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden">
                    {/* Table Header */}
                    <div className="grid grid-cols-12 gap-4 px-6 py-3 bg-white/5 border-b border-white/10 text-xs font-medium text-slate-400 uppercase tracking-wider">
                        <div className="col-span-5">Source</div>
                        <div className="col-span-1">Provider</div>
                        <div className="col-span-2">Status</div>
                        <div className="col-span-2">Step</div>
                        <div className="col-span-1">Updated</div>
                        <div className="col-span-1">Actions</div>
                    </div>

                    {/* Table Body */}
                    <div className="divide-y divide-white/5">
                        {loading ? (
                            <div className="px-6 py-8 text-sm text-slate-400">Loading sources...</div>
                        ) : error ? (
                            <div className="px-6 py-8 text-sm text-rose-300">{error}</div>
                        ) : notice ? (
                            <div className="px-6 py-4 text-xs text-amber-200 bg-amber-500/10 border-b border-amber-500/20">
                                {notice}
                            </div>
                        ) : loadedSources.length === 0 ? (
                            <div className="px-6 py-12 text-center">
                                <div className="w-16 h-16 mx-auto mb-4 bg-white/5 rounded-2xl flex items-center justify-center">
                                    <svg className="w-8 h-8 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                                    </svg>
                                </div>
                                <h3 className="text-lg font-semibold text-white mb-1">No knowledge sources yet</h3>
                                <p className="text-slate-400 text-sm mb-4">Add documents, URLs, or complete an interview to train your twin.</p>
                                <button
                                    onClick={() => setShowUploadModal(true)}
                                    className="px-4 py-2 text-sm font-semibold text-white bg-gradient-to-r from-indigo-600 to-purple-600 rounded-lg"
                                >
                                    Add Your First Source
                                </button>
                            </div>
                        ) : (
                            loadedSources.map((source) => (
                                <div key={source.id} className="grid grid-cols-12 gap-4 px-6 py-4 items-center hover:bg-white/5 transition-colors">
                                    <div className="col-span-5 flex items-center gap-3">
                                        <span className="text-xl">{typeIcons[source.type]}</span>
                                        <div>
                                            {source.citationUrl ? (
                                                <a
                                                    href={source.citationUrl}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="text-white font-medium text-sm hover:text-indigo-200"
                                                    title={source.name}
                                                >
                                                    {source.name}
                                                </a>
                                            ) : (
                                                <p className="text-white font-medium text-sm" title={source.name}>
                                                    {source.name}
                                                </p>
                                            )}
                                            {source.chunks && (
                                                <p className="text-slate-500 text-xs">{source.chunks} chunks</p>
                                            )}
                                            {source.status === 'error' && (source.lastError?.message || source.lastError?.code) ? (
                                                <p className="text-rose-200 text-xs mt-1 truncate" title={source.lastError?.message || source.lastError?.code}>
                                                    {source.lastError?.code ? `${source.lastError.code}: ` : ''}
                                                    {source.lastError?.message || 'Ingestion failed'}
                                                </p>
                                            ) : null}
                                        </div>
                                    </div>
                                    <div className="col-span-1">
                                        <span className="text-slate-400 text-xs uppercase">{source.provider || '-'}</span>
                                    </div>
                                    <div className="col-span-2">
                                        <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-lg border ${statusColors[source.status]}`}>
                                            {source.status}
                                        </span>
                                    </div>
                                    <div className="col-span-2">
                                        <span className="text-slate-300 text-xs">
                                            {source.lastStep || (source.status === 'pending' ? 'queued' : source.status)}
                                        </span>
                                    </div>
                                    <div className="col-span-1">
                                        <span className="text-slate-500 text-xs" title={source.updatedAt || undefined}>
                                            {formatUpdatedAt(source.updatedAt) || '-'}
                                        </span>
                                    </div>
                                    <div className="col-span-1">
                                        <div className="flex items-center justify-end gap-2">
                                            <button
                                                onClick={() => openDiagnostics(source)}
                                                className="px-2 py-1 text-[11px] bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-slate-200"
                                            >
                                                Diagnostics
                                            </button>
                                            <button
                                                onClick={() => retrySource(source.id)}
                                                disabled={source.status !== 'error' && source.status !== 'processing'}
                                                className="px-2 py-1 text-[11px] bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-slate-200 disabled:opacity-40"
                                            >
                                                Retry
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            ) : (
                /* Graph View Placeholder */
                <div className="bg-white/5 border border-white/10 rounded-2xl p-12 text-center">
                    <div className="w-20 h-20 mx-auto mb-4 bg-gradient-to-br from-indigo-500/20 to-purple-500/20 rounded-2xl flex items-center justify-center">
                        <svg className="w-10 h-10 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                        </svg>
                    </div>
                    <h3 className="text-lg font-semibold text-white mb-1">Knowledge Graph</h3>
                    <p className="text-slate-400 text-sm mb-4">Visual representation of your twin's knowledge structure.</p>
                    <p className="text-slate-500 text-xs">Coming soon - requires graph database integration</p>
                </div>
            )}

            {/* Upload Modal */}
            {showUploadModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
                    <div className="bg-[#111117] border border-white/10 rounded-2xl p-6 w-full max-w-lg">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-bold text-white">Add Knowledge</h2>
                            <button
                                onClick={() => setShowUploadModal(false)}
                                className="p-1 text-slate-400 hover:text-white transition-colors"
                            >
                                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>

                        <UploadModalContent
                            uploading={uploading}
                            onCancel={() => setShowUploadModal(false)}
                            onUpload={async (files) => {
                                if (!files.length) return;
                                setUploading(true);
                                setError(null);
                                setNotice(null);
                                try {
                                    const result = onUpload?.(files);
                                    if (result && typeof (result as Promise<any>).then === 'function') {
                                        await result;
                                    }
                                    await fetchSources();
                                    startPolling();
                                    setShowUploadModal(false);
                                } catch (e) {
                                    console.error(e);
                                    setError('Failed to upload files.');
                                } finally {
                                    setUploading(false);
                                }
                            }}
                        />
                    </div>
                </div>
            )}

            {/* Diagnostics Drawer */}
            {diagOpen && diagSource && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
                    <div className="bg-[#111117] border border-white/10 rounded-2xl w-full max-w-3xl max-h-[85vh] overflow-hidden">
                        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
                            <div className="min-w-0">
                                <div className="text-sm font-semibold text-white truncate">{diagSource.name}</div>
                                <div className="text-[11px] text-slate-400">
                                    Provider: <span className="text-slate-200">{diagSource.provider || inferProviderFromText(diagSource.citationUrl || diagSource.name)}</span>
                                    {' '}| Status: <span className="text-slate-200">{diagSource.status}</span>
                                    {diagSource.lastStep ? (
                                        <>
                                            {' '}| Step: <span className="text-slate-200">{diagSource.lastStep}</span>
                                        </>
                                    ) : null}
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => retrySource(diagSource.id)}
                                    className="px-3 py-1.5 text-xs bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-slate-200"
                                >
                                    Retry
                                </button>
                                <button
                                    onClick={() => {
                                        setDiagOpen(false);
                                        setDiagSource(null);
                                    }}
                                    className="p-1 text-slate-400 hover:text-white transition-colors"
                                >
                                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>
                        </div>

                        <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(85vh-64px)]">
                            {diagLoading ? <div className="text-sm text-slate-400">Loading diagnostics...</div> : null}
                            {diagError ? (
                                <div className="text-xs text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded-xl p-3">{diagError}</div>
                            ) : null}

                            <div className="bg-black/20 border border-white/10 rounded-2xl p-4">
                                <div className="text-xs font-semibold text-white mb-2">Last Error</div>
                                {diagSource.lastError ? (
                                    <pre className="text-[11px] text-rose-200 whitespace-pre-wrap break-words">{JSON.stringify(diagSource.lastError, null, 2)}</pre>
                                ) : diagLogs.find((l) => l.log_level === 'error') ? (
                                    <pre className="text-[11px] text-rose-200 whitespace-pre-wrap break-words">
                                        {JSON.stringify(diagLogs.find((l) => l.log_level === 'error'), null, 2)}
                                    </pre>
                                ) : (
                                    <div className="text-xs text-slate-400">No error recorded for this source.</div>
                                )}
                            </div>

                            <div className="bg-black/20 border border-white/10 rounded-2xl p-4">
                                <div className="text-xs font-semibold text-white mb-3">Step Timeline</div>
                                {diagEvents.length === 0 ? (
                                    <div className="text-xs text-slate-400">
                                        No step events available. Apply `20260207_ingestion_diagnostics.sql` and retry to enable step-level diagnostics.
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        {diagEvents.map((ev) => (
                                            <div key={ev.id} className="flex items-start justify-between gap-3 border border-white/10 rounded-xl p-3">
                                                <div className="min-w-0">
                                                    <div className="text-xs text-white">
                                                        <span className="uppercase text-slate-400">{ev.provider}</span> {ev.step}{' '}
                                                        <span
                                                            className={
                                                                ev.status === 'error'
                                                                    ? 'text-rose-300'
                                                                    : ev.status === 'completed'
                                                                    ? 'text-emerald-300'
                                                                    : 'text-amber-300'
                                                            }
                                                        >
                                                            [{ev.status}]
                                                        </span>
                                                    </div>
                                                    {ev.message ? <div className="text-[11px] text-slate-400 mt-1">{ev.message}</div> : null}
                                                    {ev.error ? (
                                                        <pre className="text-[10px] text-rose-200 mt-2 whitespace-pre-wrap break-words">{JSON.stringify(ev.error, null, 2)}</pre>
                                                    ) : null}
                                                </div>
                                                <div className="text-[10px] text-slate-500 whitespace-nowrap">{formatUpdatedAt(ev.started_at || ev.created_at || undefined) || '-'}</div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>

                            <div className="bg-black/20 border border-white/10 rounded-2xl p-4">
                                <div className="text-xs font-semibold text-white mb-3">Ingestion Logs</div>
                                {diagLogs.length === 0 ? (
                                    <div className="text-xs text-slate-400">No logs for this source.</div>
                                ) : (
                                    <div className="space-y-2">
                                        {diagLogs.slice(0, 30).map((l) => (
                                            <div key={l.id} className="border border-white/10 rounded-xl p-3">
                                                <div className="flex items-center justify-between gap-3">
                                                    <div className="text-[11px] text-slate-300">
                                                        <span className="uppercase text-slate-500">{l.log_level}</span> {l.message}
                                                    </div>
                                                    <div className="text-[10px] text-slate-600 whitespace-nowrap">{formatUpdatedAt(l.created_at || undefined) || '-'}</div>
                                                </div>
                                                {l.metadata ? (
                                                    <pre className="mt-2 text-[10px] text-slate-500 whitespace-pre-wrap break-words">{JSON.stringify(l.metadata, null, 2)}</pre>
                                                ) : null}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default KnowledgeTab;

function UploadModalContent({
    onUpload,
    onCancel,
    uploading = false
}: {
    onUpload: (files: File[]) => Promise<void> | void;
    onCancel: () => void;
    uploading?: boolean;
}) {
    const [mode, setMode] = useState<'file' | 'paste'>('file');
    const [files, setFiles] = useState<File[]>([]);
    const [pastedTitle, setPastedTitle] = useState<string>('');
    const [pastedText, setPastedText] = useState<string>('');
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            setFiles(Array.from(e.dataTransfer.files));
        }
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            setFiles(Array.from(e.target.files));
        }
    };

    return (
        <>
            <div className="flex items-center gap-2 mb-4">
                <button
                    onClick={() => setMode('file')}
                    className={`px-3 py-1.5 text-xs font-semibold rounded-lg border ${
                        mode === 'file' ? 'bg-white/10 text-white border-white/15' : 'bg-transparent text-slate-400 border-white/10 hover:bg-white/5'
                    }`}
                >
                    Upload files
                </button>
                <button
                    onClick={() => setMode('paste')}
                    className={`px-3 py-1.5 text-xs font-semibold rounded-lg border ${
                        mode === 'paste' ? 'bg-white/10 text-white border-white/15' : 'bg-transparent text-slate-400 border-white/10 hover:bg-white/5'
                    }`}
                >
                    Paste text
                </button>
            </div>

            {mode === 'paste' ? (
                <div className="space-y-3">
                    <div className="space-y-1">
                        <label className="text-xs uppercase tracking-wider text-slate-400">Title (optional)</label>
                        <input
                            value={pastedTitle}
                            onChange={(e) => setPastedTitle(e.target.value)}
                            placeholder="e.g., LinkedIn export, Notes"
                            className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                        />
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs uppercase tracking-wider text-slate-400">Text</label>
                        <textarea
                            rows={8}
                            value={pastedText}
                            onChange={(e) => setPastedText(e.target.value)}
                            placeholder="Paste any text you want your twin to remember and cite."
                            className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                        />
                    </div>
                </div>
            ) : (
                <div
                    className="border-2 border-dashed border-white/20 rounded-xl p-8 text-center hover:border-indigo-500/50 transition-colors cursor-pointer"
                    onDrop={handleDrop}
                    onDragOver={(e) => e.preventDefault()}
                    onClick={() => fileInputRef.current?.click()}
                >
                    <input type="file" ref={fileInputRef} className="hidden" onChange={handleFileSelect} multiple />
                    <svg className="w-12 h-12 mx-auto mb-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                    {files.length > 0 ? (
                        <div className="space-y-1">
                            <p className="text-white font-medium">{files.length} file(s) selected</p>
                            <ul className="text-xs text-slate-400">
                                {files.map((f, i) => (
                                    <li key={i}>{f.name}</li>
                                ))}
                            </ul>
                        </div>
                    ) : (
                        <>
                            <p className="text-white font-medium mb-1">Drop files here or click to browse</p>
                            <p className="text-slate-500 text-sm">PDF, DOCX, XLSX, TXT, MD</p>
                        </>
                    )}
                </div>
            )}

            <div className="flex justify-end gap-3 mt-6">
                <button onClick={onCancel} className="px-4 py-2 text-sm font-medium text-slate-400 hover:text-white transition-colors">
                    Cancel
                </button>
                <button
                    onClick={async () => {
                        if (mode === 'paste') {
                            const text = pastedText.trim();
                            if (!text) return;
                            const safeName = (pastedTitle || `pasted_${new Date().toISOString()}`).replace(/[\\/:*?\"<>|]+/g, '_');
                            const file = new File([text], `${safeName}.txt`, { type: 'text/plain' });
                            await onUpload([file]);
                            setPastedTitle('');
                            setPastedText('');
                            return;
                        }
                        if (files.length > 0) {
                            await onUpload(files);
                            setFiles([]);
                        }
                    }}
                    disabled={(mode === 'paste' ? pastedText.trim().length === 0 : files.length === 0) || uploading}
                    className="px-4 py-2 text-sm font-semibold text-white bg-gradient-to-r from-indigo-600 to-purple-600 rounded-lg disabled:opacity-50"
                >
                    {uploading ? 'Uploading...' : 'Upload'}
                </button>
            </div>
        </>
    );
}
