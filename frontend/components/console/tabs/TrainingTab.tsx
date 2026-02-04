'use client';

import React, { useCallback, useEffect, useState, useMemo } from 'react';
import ChatInterface from '@/components/Chat/ChatInterface';
import { getSupabaseClient } from '@/lib/supabase/client';
import { resolveApiBaseUrl } from '@/lib/api';
import { useToast } from '@/components/ui/Toast';
import { EmptyState } from '@/components/ui/EmptyState';

interface ClarificationThread {
    id: string;
    question: string;
    options?: Array<{ label: string; value?: string; stance?: string; intensity?: number }>;
    memory_write_proposal?: { topic?: string; memory_type?: string };
    original_query?: string;
    created_at?: string;
    mode?: string;
    status?: string;
}

interface OwnerMemory {
    id: string;
    topic_normalized: string;
    memory_type: string;
    value: string;
    stance?: string | null;
    intensity?: number | null;
    confidence?: number | null;
    created_at?: string;
}

const PAGE_SIZE = 20;

export function TrainingTab({ twinId }: { twinId: string }) {
    const supabase = getSupabaseClient();
    const { showToast } = useToast();
    const [pending, setPending] = useState<ClarificationThread[]>([]);
    const [memories, setMemories] = useState<OwnerMemory[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [answers, setAnswers] = useState<Record<string, { answer: string; selected_option?: string }>>({});

    // Search and pagination state
    const [searchQuery, setSearchQuery] = useState('');
    const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) {
                setError('Not authenticated.');
                setLoading(false);
                return;
            }

            const backendUrl = resolveApiBaseUrl();
            const [pendingRes, memoryRes] = await Promise.all([
                fetch(`${backendUrl}/twins/${twinId}/clarifications?status=pending_owner`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                }),
                fetch(`${backendUrl}/twins/${twinId}/owner-memory?status=active`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                })
            ]);

            if (pendingRes.ok) {
                const data = await pendingRes.json();
                setPending(Array.isArray(data) ? data : []);
            } else {
                setPending([]);
            }

            if (memoryRes.ok) {
                const data = await memoryRes.json();
                setMemories(Array.isArray(data) ? data : []);
            } else {
                setMemories([]);
            }
        } catch (err) {
            console.error(err);
            setError('Failed to load training data.');
        } finally {
            setLoading(false);
        }
    }, [supabase, twinId]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const resolveClarification = async (thread: ClarificationThread) => {
        const entry = answers[thread.id];
        const answer = entry?.answer?.trim() || '';
        if (!answer) {
            setError('Please provide a one-sentence answer.');
            return;
        }
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) {
                setError('Not authenticated.');
                return;
            }
            const backendUrl = resolveApiBaseUrl();
            const res = await fetch(`${backendUrl}/twins/${twinId}/clarifications/${thread.id}/resolve`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    answer,
                    selected_option: entry?.selected_option || undefined
                })
            });
            if (!res.ok) {
                throw new Error(`Resolve failed (${res.status})`);
            }
            setAnswers((prev) => ({ ...prev, [thread.id]: { answer: '', selected_option: undefined } }));
            showToast('Memory saved successfully', 'success');
            fetchData();
        } catch (err) {
            console.error(err);
            setError('Failed to resolve clarification.');
        }
    };

    const deleteMemory = async (memoryId: string) => {
        setDeletingId(memoryId);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) {
                setError('Not authenticated.');
                return;
            }
            const backendUrl = resolveApiBaseUrl();
            const res = await fetch(`${backendUrl}/twins/${twinId}/owner-memory/${memoryId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) {
                throw new Error(`Delete failed (${res.status})`);
            }
            // Optimistically remove from list
            setMemories((prev) => prev.filter((m) => m.id !== memoryId));
            showToast('Memory deleted', 'success');
            setConfirmDeleteId(null);
        } catch (err) {
            console.error(err);
            showToast('Failed to delete memory', 'error');
        } finally {
            setDeletingId(null);
        }
    };

    // Filtered memories based on search
    const filteredMemories = useMemo(() => {
        if (!searchQuery.trim()) return memories;
        const q = searchQuery.toLowerCase();
        return memories.filter(
            (m) =>
                m.topic_normalized?.toLowerCase().includes(q) ||
                m.value?.toLowerCase().includes(q) ||
                m.memory_type?.toLowerCase().includes(q)
        );
    }, [memories, searchQuery]);

    const visibleMemories = filteredMemories.slice(0, visibleCount);
    const hasMore = visibleCount < filteredMemories.length;

    const loadMore = () => {
        setVisibleCount((prev) => prev + PAGE_SIZE);
    };

    return (
        <div className="p-6 space-y-6">
            {error && (
                <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200 flex items-center justify-between">
                    <span>{error}</span>
                    <button onClick={() => setError(null)} className="text-rose-300 hover:text-rose-100">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
            )}
            <div className="grid lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-6 items-start">
                <div className="min-w-0">
                    <ChatInterface
                        twinId={twinId}
                        mode="training"
                        onMemoryUpdated={fetchData}
                    />
                </div>
                <div className="space-y-6">
                    {/* Pending Clarifications */}
                    <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
                        <div className="flex items-center justify-between mb-4">
                            <div>
                                <h3 className="text-sm font-semibold text-white">Pending Clarifications</h3>
                                <p className="text-xs text-slate-400">Resolve public or owner questions</p>
                            </div>
                            <button
                                onClick={fetchData}
                                disabled={loading}
                                className="text-[10px] uppercase tracking-wider font-bold text-indigo-300 border border-indigo-400/40 px-2 py-1 rounded-lg hover:bg-indigo-500/10 disabled:opacity-50"
                            >
                                Refresh
                            </button>
                        </div>
                        {loading ? (
                            <div className="text-xs text-slate-400 flex items-center gap-2">
                                <div className="w-3 h-3 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                                Loading...
                            </div>
                        ) : pending.length === 0 ? (
                            <EmptyState
                                emoji="✅"
                                title="All caught up!"
                                description="No questions need review right now."
                                variant="subtle"
                            />
                        ) : (
                            <div className="space-y-4">
                                {pending.map((thread) => {
                                    const entry = answers[thread.id] || { answer: '', selected_option: undefined };
                                    return (
                                        <div key={thread.id} className="rounded-xl border border-white/10 bg-black/30 p-3 space-y-3">
                                            <div className="text-xs text-slate-400 uppercase tracking-wider">
                                                {thread.mode === 'public' ? 'Public question' : 'Owner training'}
                                            </div>
                                            <div className="text-sm text-white">{thread.question}</div>
                                            {thread.memory_write_proposal?.topic && (
                                                <div className="text-[10px] text-slate-400">
                                                    Topic: <span className="text-slate-200">{thread.memory_write_proposal.topic}</span> | Type: <span className="text-slate-200">{thread.memory_write_proposal.memory_type}</span>
                                                </div>
                                            )}
                                            {Array.isArray(thread.options) && thread.options.length > 0 && (
                                                <div className="space-y-2">
                                                    {thread.options.map((opt, idx) => (
                                                        <label key={idx} className="flex items-center gap-2 text-xs text-slate-300">
                                                            <input
                                                                type="radio"
                                                                name={`opt-${thread.id}`}
                                                                checked={entry.selected_option === opt.label}
                                                                onChange={() => setAnswers((prev) => ({
                                                                    ...prev,
                                                                    [thread.id]: {
                                                                        answer: opt.value || opt.label,
                                                                        selected_option: opt.label
                                                                    }
                                                                }))}
                                                            />
                                                            <span className="font-semibold">{opt.label}</span>
                                                        </label>
                                                    ))}
                                                </div>
                                            )}
                                            <input
                                                type="text"
                                                value={entry.answer}
                                                onChange={(e) => setAnswers((prev) => ({
                                                    ...prev,
                                                    [thread.id]: {
                                                        answer: e.target.value,
                                                        selected_option: undefined
                                                    }
                                                }))}
                                                placeholder="Answer in one sentence..."
                                                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500"
                                            />
                                            <div className="flex justify-end">
                                                <button
                                                    onClick={() => resolveClarification(thread)}
                                                    className="px-3 py-2 text-[10px] uppercase tracking-wider font-bold bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg transition-colors"
                                                >
                                                    Save Memory
                                                </button>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>

                    {/* Owner Memory Log */}
                    <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
                        <div className="flex items-center justify-between mb-4">
                            <div>
                                <h3 className="text-sm font-semibold text-white">Owner Memory Log</h3>
                                <p className="text-xs text-slate-400">Active beliefs, preferences, and stance</p>
                            </div>
                            <span className="text-[10px] text-slate-500">{filteredMemories.length} items</span>
                        </div>

                        {/* Search input */}
                        <div className="relative mb-4">
                            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                            <input
                                type="text"
                                value={searchQuery}
                                onChange={(e) => {
                                    setSearchQuery(e.target.value);
                                    setVisibleCount(PAGE_SIZE); // Reset pagination on search
                                }}
                                placeholder="Search memories..."
                                className="w-full bg-white/5 border border-white/10 rounded-lg pl-9 pr-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                            />
                        </div>

                        {loading ? (
                            <div className="text-xs text-slate-400 flex items-center gap-2">
                                <div className="w-3 h-3 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                                Loading...
                            </div>
                        ) : memories.length === 0 ? (
                            <EmptyState
                                emoji="🧠"
                                title="No memories yet"
                                description="Resolve clarifications or chat in training mode to build your twin's memory."
                                variant="subtle"
                            />
                        ) : filteredMemories.length === 0 ? (
                            <div className="text-xs text-slate-500 text-center py-4">
                                No memories match &ldquo;{searchQuery}&rdquo;
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {visibleMemories.map((mem) => (
                                    <div key={mem.id} className="group rounded-xl border border-white/10 bg-black/20 p-3 relative">
                                        {/* Delete confirmation overlay */}
                                        {confirmDeleteId === mem.id && (
                                            <div className="absolute inset-0 bg-black/80 backdrop-blur-sm rounded-xl flex items-center justify-center z-10">
                                                <div className="text-center">
                                                    <p className="text-xs text-white mb-3">Delete this memory?</p>
                                                    <div className="flex gap-2 justify-center">
                                                        <button
                                                            onClick={() => setConfirmDeleteId(null)}
                                                            className="px-3 py-1.5 text-[10px] font-bold text-slate-300 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
                                                        >
                                                            Cancel
                                                        </button>
                                                        <button
                                                            onClick={() => deleteMemory(mem.id)}
                                                            disabled={deletingId === mem.id}
                                                            className="px-3 py-1.5 text-[10px] font-bold text-white bg-rose-500 hover:bg-rose-600 rounded-lg transition-colors disabled:opacity-50"
                                                        >
                                                            {deletingId === mem.id ? 'Deleting...' : 'Delete'}
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        )}

                                        <div className="flex items-center justify-between">
                                            <div className="text-xs font-semibold text-white truncate pr-2">{mem.topic_normalized}</div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-[10px] text-slate-400 uppercase tracking-wider">{mem.memory_type}</span>
                                                <button
                                                    onClick={() => setConfirmDeleteId(mem.id)}
                                                    className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-rose-400 transition-all"
                                                    aria-label="Delete memory"
                                                >
                                                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                    </svg>
                                                </button>
                                            </div>
                                        </div>
                                        <div className="text-xs text-slate-300 mt-2">{mem.value}</div>
                                        <div className="mt-2 flex flex-wrap gap-2 text-[10px] text-slate-400">
                                            {mem.stance && <span>stance: {mem.stance}</span>}
                                            {mem.intensity != null && <span>intensity: {mem.intensity}/10</span>}
                                            {mem.confidence != null && <span>conf: {mem.confidence.toFixed(2)}</span>}
                                        </div>
                                    </div>
                                ))}

                                {/* Load more button */}
                                {hasMore && (
                                    <button
                                        onClick={loadMore}
                                        className="w-full py-2 text-xs font-medium text-indigo-300 hover:text-indigo-200 border border-white/10 rounded-lg hover:bg-white/5 transition-colors"
                                    >
                                        Load more ({filteredMemories.length - visibleCount} remaining)
                                    </button>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

export default TrainingTab;
