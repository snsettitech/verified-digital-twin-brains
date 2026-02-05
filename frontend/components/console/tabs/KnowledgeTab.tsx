'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';
import { resolveApiBaseUrl } from '@/lib/api';

interface Source {
    id: string;
    name: string;
    type: 'document' | 'url' | 'interview';
    status: 'approved' | 'pending' | 'processing';
    createdAt: string;
    chunks?: number;
}

interface KnowledgeTabProps {
    twinId: string;
    sources?: Source[];
    onUpload?: (files: File[]) => void;
    onUrlSubmit?: (url: string) => void;
}

export function KnowledgeTab({ twinId, sources = [], onUpload, onUrlSubmit }: KnowledgeTabProps) {
    const supabase = getSupabaseClient();
    const [activeView, setActiveView] = useState<'list' | 'graph'>('list');
    const [showUploadModal, setShowUploadModal] = useState(false);
    const [url, setUrl] = useState('');
    const [loadedSources, setLoadedSources] = useState<Source[]>(sources);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const retryRef = useRef(0);

    const fetchSources = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) {
                if (retryRef.current < 5) {
                    retryRef.current += 1;
                    setTimeout(fetchSources, 600);
                } else {
                    setError('Not authenticated.');
                    setLoadedSources([]);
                }
                return;
            }
            const backendUrl = resolveApiBaseUrl();
            const res = await fetch(`${backendUrl}/sources/${twinId}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) {
                const errText = await res.text();
                throw new Error(errText || 'Failed to load sources');
            }
            const data = await res.json();
            const mapped = (Array.isArray(data) ? data : []).map((source: any) => {
                const rawStatus = source.staging_status || source.status || 'pending';
                let status: Source['status'] = 'pending';
                if (['live', 'approved', 'processed'].includes(rawStatus)) {
                    status = 'approved';
                } else if (['processing', 'training'].includes(rawStatus)) {
                    status = 'processing';
                }
                const filename = source.filename || source.file_url || 'Untitled source';
                const isUrl = typeof filename === 'string' && (filename.startsWith('http://') || filename.startsWith('https://'));
                return {
                    id: source.id,
                    name: filename,
                    type: isUrl ? 'url' : 'document',
                    status,
                    createdAt: source.created_at ? new Date(source.created_at).toLocaleDateString() : '',
                    chunks: source.chunk_count || undefined
                } as Source;
            });
            setLoadedSources(mapped);
        } catch (err: any) {
            console.error(err);
            setError('Failed to load sources.');
            setLoadedSources([]);
        } finally {
            setLoading(false);
        }
    }, [supabase, twinId]);

    useEffect(() => {
        fetchSources();
        const { data } = supabase.auth.onAuthStateChange((_event, session) => {
            if (session?.access_token) {
                retryRef.current = 0;
                fetchSources();
            }
        });
        return () => {
            data?.subscription?.unsubscribe();
        };
    }, [fetchSources, supabase]);

    const statusColors = {
        approved: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
        pending: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
        processing: 'bg-blue-500/20 text-blue-400 border-blue-500/30'
    };

    const typeIcons = {
        document: '📄',
        url: '🔗',
        interview: '🎙️'
    };

    const handleUrlSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (url.trim()) {
            onUrlSubmit?.(url.trim());
            setUrl('');
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
                    placeholder="Paste a URL to add content..."
                    className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                />
                <button
                    type="submit"
                    disabled={!url.trim()}
                    className="px-6 py-3 text-sm font-medium text-white bg-white/10 hover:bg-white/15 border border-white/10 rounded-xl transition-all disabled:opacity-50"
                >
                    Add URL
                </button>
            </form>

            {/* Content View */}
            {activeView === 'list' ? (
                <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden">
                    {/* Table Header */}
                    <div className="grid grid-cols-12 gap-4 px-6 py-3 bg-white/5 border-b border-white/10 text-xs font-medium text-slate-400 uppercase tracking-wider">
                        <div className="col-span-5">Source</div>
                        <div className="col-span-2">Type</div>
                        <div className="col-span-2">Status</div>
                        <div className="col-span-2">Added</div>
                        <div className="col-span-1">Actions</div>
                    </div>

                    {/* Table Body */}
                    <div className="divide-y divide-white/5">
                        {loading ? (
                            <div className="px-6 py-8 text-sm text-slate-400">Loading sources...</div>
                        ) : error ? (
                            <div className="px-6 py-8 text-sm text-rose-300">{error}</div>
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
                                            <p className="text-white font-medium text-sm">{source.name}</p>
                                            {source.chunks && (
                                                <p className="text-slate-500 text-xs">{source.chunks} chunks</p>
                                            )}
                                        </div>
                                    </div>
                                    <div className="col-span-2">
                                        <span className="text-slate-400 text-sm capitalize">{source.type}</span>
                                    </div>
                                    <div className="col-span-2">
                                        <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-lg border ${statusColors[source.status]}`}>
                                            {source.status}
                                        </span>
                                    </div>
                                    <div className="col-span-2">
                                        <span className="text-slate-400 text-sm">{source.createdAt}</span>
                                    </div>
                                    <div className="col-span-1">
                                        <button className="p-1 text-slate-400 hover:text-white transition-colors">
                                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
                                            </svg>
                                        </button>
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

                        {/* Drop Zone */}
                        <div className="border-2 border-dashed border-white/20 rounded-xl p-8 text-center hover:border-indigo-500/50 transition-colors">
                            <svg className="w-12 h-12 mx-auto mb-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                            </svg>
                            <p className="text-white font-medium mb-1">Drop files here or click to browse</p>
                            <p className="text-slate-500 text-sm">PDF, DOC, TXT, MD - Max 50MB</p>
                        </div>

                        <div className="flex justify-end gap-3 mt-6">
                            <button
                                onClick={() => setShowUploadModal(false)}
                                className="px-4 py-2 text-sm font-medium text-slate-400 hover:text-white transition-colors"
                            >
                                Cancel
                            </button>
                            <button className="px-4 py-2 text-sm font-semibold text-white bg-gradient-to-r from-indigo-600 to-purple-600 rounded-lg">
                                Upload
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default KnowledgeTab;
