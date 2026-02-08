'use client';

import React, { useCallback, useEffect, useState, useMemo } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';
import { resolveApiBaseUrl } from '@/lib/api';
import { useToast } from '@/components/ui/Toast';
import { EmptyState } from '@/components/ui/EmptyState';
import { InterviewView, SimulatorView } from '@/components/training';
import { KnowledgeTab } from '@/components/console/tabs/KnowledgeTab';

// ... (Keep existing interfaces)
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
    status?: string;
    provenance?: Record<string, any>;
}

const PAGE_SIZE = 20;
const MEMORY_TYPES = ['belief', 'preference', 'stance', 'lens', 'tone_rule'];
const STANCE_OPTIONS = ['', 'positive', 'negative', 'neutral', 'mixed', 'unknown'];

type TrainingStep = 'intent' | 'interview' | 'knowledge' | 'inbox' | 'validate';

export function TrainingTab({ twinId }: { twinId: string }) {
    const supabase = getSupabaseClient();
    const { showToast } = useToast();

    // Core Data State
    const [pending, setPending] = useState<ClarificationThread[]>([]);
    const [memories, setMemories] = useState<OwnerMemory[]>([]);
    const [proposedMemories, setProposedMemories] = useState<OwnerMemory[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [answers, setAnswers] = useState<Record<string, { answer: string; selected_option?: string }>>({});

    // UI State
    const [currentStep, setCurrentStep] = useState<TrainingStep>('intent');
    const [newMemory, setNewMemory] = useState({
        topic_normalized: '',
        memory_type: 'stance',
        value: '',
        stance: '',
        intensity: 5
    });
    const [savingMemory, setSavingMemory] = useState(false);
    const [showAddMemory, setShowAddMemory] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editingDraft, setEditingDraft] = useState<Partial<OwnerMemory>>({});
    const [historyOpenId, setHistoryOpenId] = useState<string | null>(null);
    const [historyItems, setHistoryItems] = useState<Record<string, OwnerMemory[]>>({});
    const [historyLoadingId, setHistoryLoadingId] = useState<string | null>(null);
    const [twinSettings, setTwinSettings] = useState<any>({});
    const [intentProfile, setIntentProfile] = useState({
        use_case: '',
        audience: '',
        boundaries: ''
    });
    const [publicIntro, setPublicIntro] = useState('');
    const [savingIntent, setSavingIntent] = useState(false);

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
            const [pendingRes, memoryRes, proposedRes, twinRes] = await Promise.all([
                fetch(`${backendUrl}/twins/${twinId}/clarifications?status=pending_owner`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                }),
                fetch(`${backendUrl}/twins/${twinId}/owner-memory?status=active`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                }),
                fetch(`${backendUrl}/twins/${twinId}/owner-memory?status=proposed`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                }),
                fetch(`${backendUrl}/twins/${twinId}`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                })
            ]);

            if (pendingRes.ok) {
                const data = await pendingRes.json();
                setPending(Array.isArray(data) ? data : []);
            }
            if (memoryRes.ok) {
                const data = await memoryRes.json();
                setMemories(Array.isArray(data) ? data : []);
            }
            if (proposedRes.ok) {
                const data = await proposedRes.json();
                setProposedMemories(Array.isArray(data) ? data : []);
            }
            if (twinRes.ok) {
                const data = await twinRes.json();
                const settings = data?.settings || {};
                setTwinSettings(settings);
                const profile = settings.intent_profile || {};
                setIntentProfile({
                    use_case: profile.use_case || '',
                    audience: profile.audience || '',
                    boundaries: profile.boundaries || ''
                });
                setPublicIntro(settings.public_intro || '');
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

    // ... (Keep existing CRUD handlers: resolveClarification, deleteMemory, approveProposedMemory, toggleHistory, restoreFromHistory, createMemory, saveEdit, startEdit, cancelEdit)

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
            if (!token) return;
            const backendUrl = resolveApiBaseUrl();
            const res = await fetch(`${backendUrl}/twins/${twinId}/owner-memory/${memoryId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) throw new Error(`Delete failed (${res.status})`);
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

    const approveProposedMemory = async (mem: OwnerMemory) => {
        setSavingMemory(true);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) return;
            const backendUrl = resolveApiBaseUrl();
            const res = await fetch(`${backendUrl}/twins/${twinId}/owner-memory/${mem.id}`, {
                method: 'PATCH',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    topic_normalized: mem.topic_normalized,
                    memory_type: mem.memory_type,
                    value: mem.value,
                    stance: mem.stance || undefined,
                    intensity: mem.intensity ?? undefined
                })
            });
            if (!res.ok) throw new Error(`Approve failed (${res.status})`);
            showToast('Memory approved', 'success');
            fetchData();
        } catch (err) {
            console.error(err);
            setError('Failed to approve memory.');
        } finally {
            setSavingMemory(false);
        }
    };

    const toggleHistory = async (mem: OwnerMemory) => {
        if (historyOpenId === mem.id) {
            setHistoryOpenId(null);
            return;
        }
        setHistoryOpenId(mem.id);
        if (historyItems[mem.id]) return;
        setHistoryLoadingId(mem.id);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) return;
            const backendUrl = resolveApiBaseUrl();
            const res = await fetch(`${backendUrl}/twins/${twinId}/owner-memory/${mem.id}/history`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) throw new Error('History failed');
            const data = await res.json();
            setHistoryItems((prev) => ({ ...prev, [mem.id]: Array.isArray(data) ? data : [] }));
        } catch (err) {
            console.error(err);
        } finally {
            setHistoryLoadingId(null);
        }
    };

    const restoreFromHistory = async (current: OwnerMemory, historical: OwnerMemory) => {
        // (Implementation same as before, simplified for brevity in this tool call but included fully in file write)
        setSavingMemory(true);
        try {
            // ... existing logic
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) return;
            const backendUrl = resolveApiBaseUrl();
            const res = await fetch(`${backendUrl}/twins/${twinId}/owner-memory/${current.id}`, {
                method: 'PATCH',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    topic_normalized: historical.topic_normalized,
                    memory_type: historical.memory_type,
                    value: historical.value,
                    stance: historical.stance || undefined,
                    intensity: historical.intensity ?? undefined
                })
            });
            if (!res.ok) throw new Error('Restore failed');
            showToast('Memory restored', 'success');
            setHistoryOpenId(null);
            fetchData();
        } catch (err) {
            console.error(err);
            setError('Failed to restore memory.');
        } finally {
            setSavingMemory(false);
        }
    };

    const createMemory = async () => {
        if (!newMemory.topic_normalized.trim() || !newMemory.value.trim()) {
            setError('Topic and value are required.');
            return;
        }
        setSavingMemory(true);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) return;
            const backendUrl = resolveApiBaseUrl();
            const res = await fetch(`${backendUrl}/twins/${twinId}/owner-memory`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    topic_normalized: newMemory.topic_normalized.trim(),
                    memory_type: newMemory.memory_type,
                    value: newMemory.value.trim(),
                    stance: newMemory.stance || undefined,
                    intensity: newMemory.intensity
                })
            });
            if (!res.ok) throw new Error('Create failed');
            showToast('Memory created', 'success');
            setNewMemory({ topic_normalized: '', memory_type: 'stance', value: '', stance: '', intensity: 5 });
            setShowAddMemory(false);
            fetchData();
        } catch (err) {
            console.error(err);
            setError('Failed to create memory.');
        } finally {
            setSavingMemory(false);
        }
    };

    const startEdit = (mem: OwnerMemory) => {
        setEditingId(mem.id);
        setEditingDraft({
            topic_normalized: mem.topic_normalized,
            memory_type: mem.memory_type,
            value: mem.value,
            stance: mem.stance || '',
            intensity: mem.intensity ?? 5
        });
    };

    const cancelEdit = () => {
        setEditingId(null);
        setEditingDraft({});
    };

    const saveEdit = async () => {
        // ... (Existing save logic)
        if (!editingId) return;
        setSavingMemory(true);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) return;
            const backendUrl = resolveApiBaseUrl();
            const res = await fetch(`${backendUrl}/twins/${twinId}/owner-memory/${editingId}`, {
                method: 'PATCH',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    topic_normalized: editingDraft.topic_normalized,
                    memory_type: editingDraft.memory_type,
                    value: editingDraft.value,
                    stance: editingDraft.stance || undefined,
                    intensity: editingDraft.intensity
                })
            });
            if (!res.ok) throw new Error('Update failed');
            showToast('Memory updated', 'success');
            cancelEdit();
            fetchData();
        } catch (err) {
            console.error(err);
            setError('Failed to update memory.');
        } finally {
            setSavingMemory(false);
        }
    };

    const scrollToSection = (sectionId: string) => {
        if (typeof document === 'undefined') return;
        const el = document.getElementById(sectionId);
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    };

    const saveIntentProfile = async () => {
        setSavingIntent(true);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) return;
            const backendUrl = resolveApiBaseUrl();
            const nextSettings = {
                ...twinSettings,
                intent_profile: {
                    use_case: intentProfile.use_case.trim(),
                    audience: intentProfile.audience.trim(),
                    boundaries: intentProfile.boundaries.trim()
                },
                public_intro: publicIntro.trim()
            };
            const res = await fetch(`${backendUrl}/twins/${twinId}`, {
                method: 'PATCH',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({ settings: nextSettings })
            });
            if (!res.ok) throw new Error('Save failed');
            setTwinSettings(nextSettings);
            showToast('Intent & intro saved', 'success');
            setCurrentStep('interview');
            scrollToSection('training-interview');
        } catch (err) {
            console.error(err);
            setError('Failed to save intent profile.');
        } finally {
            setSavingIntent(false);
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
    const interviewProposals = useMemo(
        () =>
            proposedMemories.filter(
                (memory) =>
                    (memory.provenance as Record<string, any> | undefined)?.source_type === 'interview'
            ),
        [proposedMemories]
    );

    return (
        <div className="flex flex-col h-[calc(100vh-theme(spacing.32))]">
            {/* Header */}
            <div className="bg-[#111117] border-b border-white/10 px-6 py-4">
                <div className="max-w-5xl mx-auto">
                    <h2 className="text-xl font-bold text-white">Training Module</h2>
                    <p className="text-sm text-slate-400">Complete each step in order to train your twin end-to-end.</p>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 overflow-y-auto p-6 bg-[#0a0a0f]">
                <div className="max-w-6xl mx-auto space-y-12">
                    {/* STEP 1: INTENT */}
                    <section id="training-intent" className="max-w-3xl mx-auto space-y-6">
                        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
                            <div className="flex items-center justify-between mb-4">
                                <div>
                                    <h2 className="text-xl font-bold text-white">Step 1. Intent & Public Intro</h2>
                                    <p className="text-sm text-slate-400">
                                        Start by telling your twin what it is for and how you want users to know you.
                                    </p>
                                </div>
                                <span className="text-xs text-slate-500">Current: {currentStep === 'intent' ? 'Active' : 'Saved'}</span>
                            </div>
                            <div className="space-y-4">
                                <div>
                                    <label className="text-xs uppercase tracking-wider text-slate-400">Primary use case</label>
                                    <textarea
                                        rows={2}
                                        value={intentProfile.use_case}
                                        onChange={(e) => setIntentProfile(p => ({ ...p, use_case: e.target.value }))}
                                        placeholder="e.g., A VC twin that helps founders understand my investment philosophy"
                                        className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-white"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs uppercase tracking-wider text-slate-400">Audience & outcomes</label>
                                    <textarea
                                        rows={2}
                                        value={intentProfile.audience}
                                        onChange={(e) => setIntentProfile(p => ({ ...p, audience: e.target.value }))}
                                        placeholder="Who will use this twin and what should it help them accomplish?"
                                        className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-white"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs uppercase tracking-wider text-slate-400">Boundaries</label>
                                    <textarea
                                        rows={2}
                                        value={intentProfile.boundaries}
                                        onChange={(e) => setIntentProfile(p => ({ ...p, boundaries: e.target.value }))}
                                        placeholder="Topics to avoid, when to escalate, or anything it should never do."
                                        className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-white"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs uppercase tracking-wider text-slate-400">Public intro (how users should know you)</label>
                                    <textarea
                                        rows={3}
                                        value={publicIntro}
                                        onChange={(e) => setPublicIntro(e.target.value)}
                                        placeholder="A short intro you want the twin to use when asked about you."
                                        className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-white"
                                    />
                                </div>
                            </div>
                            <div className="flex justify-end pt-4">
                                <button
                                    onClick={saveIntentProfile}
                                    disabled={savingIntent}
                                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium"
                                >
                                    {savingIntent ? 'Saving...' : 'Save & Continue'}
                                </button>
                            </div>
                        </div>
                    </section>

                    {/* STEP 2: INTERVIEW */}
                    <section id="training-interview" className="max-w-3xl mx-auto space-y-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-xl font-bold text-white">Step 2. Interview</h2>
                                <p className="text-sm text-slate-400">Answer questions so the twin can learn your intent, goals, and preferences.</p>
                            </div>
                            <button
                                onClick={() => scrollToSection('training-knowledge')}
                                className="text-xs text-indigo-300 hover:text-indigo-200"
                            >
                                Skip to Knowledge
                            </button>
                        </div>
                        <InterviewView
                            onComplete={() => {
                                setCurrentStep('knowledge');
                                scrollToSection('training-knowledge');
                            }}
                            onDataAvailable={(data) => {
                                const extracted = Array.isArray(data?.extracted_memories) ? data.extracted_memories.length : 0;
                                const proposed = Number(data?.proposed_count || 0);
                                const notes = Array.isArray(data?.notes) ? data.notes : [];

                                if (proposed > 0) {
                                    showToast(`Interview saved. ${proposed} memory proposal(s) sent to Inbox.`, 'success');
                                } else if (extracted > 0) {
                                    showToast('Interview saved, but no memory proposals were generated. Check Step 4 diagnostics.', 'warning');
                                } else {
                                    showToast('Interview saved, but no memories were extracted. Try fuller answers and stop recording after a full response.', 'warning');
                                }

                                if (notes.length > 0) {
                                    console.warn('[Interview] Finalize notes:', notes);
                                }
                                fetchData();
                                scrollToSection('training-inbox');
                            }}
                        />
                    </section>

                    {/* STEP 3: KNOWLEDGE */}
                    <section id="training-knowledge" className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-xl font-bold text-white">Step 3. Knowledge Ingestion</h2>
                                <p className="text-sm text-slate-400">Upload documents or add links to grow the knowledge base.</p>
                            </div>
                            <button
                                onClick={() => scrollToSection('training-inbox')}
                                className="text-xs text-indigo-300 hover:text-indigo-200"
                            >
                                Next: Inbox
                            </button>
                        </div>
                        <KnowledgeTab
                            twinId={twinId}
                            onUrlSubmit={async (url) => {
                                try {
                                    const backendUrl = resolveApiBaseUrl();
                                    const isE2EBypass =
                                        process.env.NODE_ENV !== 'production' &&
                                        process.env.NEXT_PUBLIC_E2E_BYPASS_AUTH === '1';
                                    const headers: Record<string, string> = {
                                        'Content-Type': 'application/json'
                                    };
                                    if (!isE2EBypass) {
                                        const { data: { session } } = await supabase.auth.getSession();
                                        const token = session?.access_token;
                                        if (!token) return;
                                        headers['Authorization'] = `Bearer ${token}`;
                                    }
                                    const res = await fetch(`${backendUrl}/ingest/url/${twinId}`, {
                                        method: 'POST',
                                        headers,
                                        body: JSON.stringify({ url })
                                    });
                                    if (!res.ok) {
                                        const errText = await res.text();
                                        throw new Error(errText || 'Ingest failed');
                                    }
                                    showToast('URL added to knowledge base', 'success');
                                } catch (e) {
                                    console.error(e);
                                    showToast('Failed to add URL', 'error');
                                    throw e;
                                }
                            }}
                            onUpload={async (files) => {
                                try {
                                    const backendUrl = resolveApiBaseUrl();
                                    const isE2EBypass =
                                        process.env.NODE_ENV !== 'production' &&
                                        process.env.NEXT_PUBLIC_E2E_BYPASS_AUTH === '1';
                                    const headers: Record<string, string> = {};
                                    if (!isE2EBypass) {
                                        const { data: { session } } = await supabase.auth.getSession();
                                        const token = session?.access_token;
                                        if (!token) return;
                                        headers['Authorization'] = `Bearer ${token}`;
                                    }

                                    let successCount = 0;
                                    for (const file of files) {
                                        const formData = new FormData();
                                        formData.append('file', file);
                                        const res = await fetch(`${backendUrl}/ingest/file/${twinId}`, {
                                            method: 'POST',
                                            headers,
                                            body: formData
                                        });
                                        if (res.ok) {
                                            successCount++;
                                        } else {
                                            const errText = await res.text();
                                            throw new Error(errText || `Upload failed (${res.status})`);
                                        }
                                    }
                                    showToast(`Started processing ${successCount} files`, 'success');
                                } catch (e) {
                                    console.error(e);
                                    showToast('Failed to upload files', 'error');
                                    throw e;
                                }
                            }}
                        />
                    </section>

                    {/* STEP 4: INBOX */}
                    <section id="training-inbox" className="space-y-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-xl font-bold text-white">Step 4. Inbox & Memory Review</h2>
                                <p className="text-sm text-slate-400">Approve, edit, or reject proposed memories and respond to clarifications.</p>
                            </div>
                            <button
                                onClick={() => scrollToSection('training-validate')}
                                className="text-xs text-indigo-300 hover:text-indigo-200"
                            >
                                Next: Validate
                            </button>
                        </div>

                        <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
                            <h3 className="text-sm font-semibold text-white mb-2">Step 1 + Step 2 Summary</h3>
                            <div className="grid md:grid-cols-2 gap-4 text-xs">
                                <div className="rounded-xl border border-white/10 bg-black/20 p-3 space-y-2">
                                    <div className="text-[10px] uppercase tracking-wider text-slate-400">Intent Profile</div>
                                    <div className="text-slate-200">
                                        <span className="text-slate-400">Use case:</span>{' '}
                                        {intentProfile.use_case || 'Not set'}
                                    </div>
                                    <div className="text-slate-200">
                                        <span className="text-slate-400">Audience:</span>{' '}
                                        {intentProfile.audience || 'Not set'}
                                    </div>
                                    <div className="text-slate-200">
                                        <span className="text-slate-400">Boundaries:</span>{' '}
                                        {intentProfile.boundaries || 'Not set'}
                                    </div>
                                </div>
                                <div className="rounded-xl border border-white/10 bg-black/20 p-3 space-y-2">
                                    <div className="text-[10px] uppercase tracking-wider text-slate-400">Interview Signals</div>
                                    <div className="text-slate-200">
                                        <span className="text-slate-400">Proposals from interview:</span>{' '}
                                        {interviewProposals.length}
                                    </div>
                                    {interviewProposals.length === 0 ? (
                                        <div className="text-slate-400">
                                            No interview proposals yet. Complete Step 2 and press Stop Interview.
                                        </div>
                                    ) : (
                                        <div className="space-y-1">
                                            {interviewProposals.slice(0, 3).map((memory) => (
                                                <div key={memory.id} className="text-slate-300">
                                                    • {memory.value}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>

                        <div className="grid lg:grid-cols-[2fr_1fr] gap-6 items-start">
                            <div className="space-y-6">
                                {/* Owner Memory Log - Main View */}
                                <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
                                    <div className="flex items-center justify-between mb-4">
                                        <div>
                                            <h3 className="text-sm font-semibold text-white">Owner Memory Log</h3>
                                            <p className="text-xs text-slate-400">Active beliefs, preferences, and stance</p>
                                        </div>
                                        <div className="flex gap-2">
                                            <div className="relative">
                                                <input
                                                    type="text"
                                                    value={searchQuery}
                                                    onChange={(e) => setSearchQuery(e.target.value)}
                                                    placeholder="Search..."
                                                    className="bg-black/30 border border-white/10 rounded-lg pl-3 pr-2 py-1 text-xs text-white w-32 focus:w-48 transition-all"
                                                />
                                            </div>
                                            <button
                                                onClick={() => setShowAddMemory((prev) => !prev)}
                                                className="text-xs bg-indigo-500/20 text-indigo-300 px-3 py-1 rounded-lg hover:bg-indigo-500/30"
                                            >
                                                {showAddMemory ? 'Close' : '+ Add'}
                                            </button>
                                        </div>
                                    </div>

                                    {/* Memory Items */}
                                    <div className="space-y-3">
                                        {showAddMemory && (
                                            <div className="rounded-xl border border-white/10 bg-black/30 p-3 space-y-3">
                                                <div className="grid gap-3 md:grid-cols-2">
                                                    <div className="space-y-1">
                                                        <label className="text-[10px] uppercase tracking-wider text-slate-400">Topic</label>
                                                        <input
                                                            type="text"
                                                            value={newMemory.topic_normalized}
                                                            onChange={(e) => setNewMemory(p => ({ ...p, topic_normalized: e.target.value }))}
                                                            placeholder="e.g., Green flags"
                                                            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs text-white"
                                                        />
                                                    </div>
                                                    <div className="space-y-1">
                                                        <label className="text-[10px] uppercase tracking-wider text-slate-400">Type</label>
                                                        <select
                                                            value={newMemory.memory_type}
                                                            onChange={(e) => setNewMemory(p => ({ ...p, memory_type: e.target.value }))}
                                                            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs text-white"
                                                        >
                                                            {MEMORY_TYPES.map((type) => (
                                                                <option key={type} value={type}>{type}</option>
                                                            ))}
                                                        </select>
                                                    </div>
                                                </div>
                                                <div className="space-y-1">
                                                    <label className="text-[10px] uppercase tracking-wider text-slate-400">Value</label>
                                                    <textarea
                                                        rows={3}
                                                        value={newMemory.value}
                                                        onChange={(e) => setNewMemory(p => ({ ...p, value: e.target.value }))}
                                                        placeholder="Write the memory in your own words."
                                                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs text-white"
                                                    />
                                                </div>
                                                <div className="grid gap-3 md:grid-cols-2">
                                                    <div className="space-y-1">
                                                        <label className="text-[10px] uppercase tracking-wider text-slate-400">Stance</label>
                                                        <select
                                                            value={newMemory.stance}
                                                            onChange={(e) => setNewMemory(p => ({ ...p, stance: e.target.value }))}
                                                            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs text-white"
                                                        >
                                                            {STANCE_OPTIONS.map((option) => (
                                                                <option key={option} value={option}>{option || 'none'}</option>
                                                            ))}
                                                        </select>
                                                    </div>
                                                    <div className="space-y-1">
                                                        <label className="text-[10px] uppercase tracking-wider text-slate-400">Intensity</label>
                                                        <input
                                                            type="number"
                                                            min={1}
                                                            max={10}
                                                            value={newMemory.intensity}
                                                            onChange={(e) => setNewMemory(p => ({ ...p, intensity: Number(e.target.value) }))}
                                                            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs text-white"
                                                        />
                                                    </div>
                                                </div>
                                                <div className="flex justify-end gap-2">
                                                    <button
                                                        onClick={() => setShowAddMemory(false)}
                                                        className="px-3 py-1.5 text-[10px] text-slate-400"
                                                    >
                                                        Cancel
                                                    </button>
                                                    <button
                                                        onClick={createMemory}
                                                        disabled={savingMemory}
                                                        className="px-3 py-1.5 text-[10px] bg-emerald-500 text-white rounded-lg disabled:opacity-50"
                                                    >
                                                        {savingMemory ? 'Saving...' : 'Save'}
                                                    </button>
                                                </div>
                                            </div>
                                        )}
                                        {visibleMemories.length === 0 && !showAddMemory && (
                                            <div className="rounded-xl border border-dashed border-white/10 bg-black/10 p-4 text-xs text-slate-400">
                                                No approved memories yet. Complete an interview, approve proposals, or add one manually.
                                            </div>
                                        )}
                                        {visibleMemories.map((mem) => (
                                            <div key={mem.id} className="group rounded-xl border border-white/10 bg-black/20 p-3 relative">
                                                {confirmDeleteId === mem.id && (
                                                    <div className="absolute inset-0 bg-black/80 backdrop-blur-sm rounded-xl flex items-center justify-center z-10">
                                                        <div className="text-center">
                                                            <p className="text-xs text-white mb-3">Delete this memory?</p>
                                                            <div className="flex gap-2 justify-center">
                                                                <button onClick={() => setConfirmDeleteId(null)} className="px-3 py-1.5 text-[10px] font-bold text-slate-300 bg-white/10 hover:bg-white/20 rounded-lg">Cancel</button>
                                                                <button onClick={() => deleteMemory(mem.id)} className="px-3 py-1.5 text-[10px] font-bold text-white bg-rose-500 hover:bg-rose-600 rounded-lg">Delete</button>
                                                            </div>
                                                        </div>
                                                    </div>
                                                )}
                                                <div className="flex items-center justify-between">
                                                    <div className="text-xs font-semibold text-white truncate pr-2">{mem.topic_normalized}</div>
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-[10px] text-slate-400 uppercase tracking-wider">{mem.memory_type}</span>
                                                        <button onClick={() => startEdit(mem)} className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-indigo-300 transition-all">
                                                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.232 5.232l3.536 3.536M9 13l6.232-6.232a2 2 0 012.828 0l1.172 1.172a2 2 0 010 2.828L12 17H9v-4z" /></svg>
                                                        </button>
                                                        <button onClick={() => setConfirmDeleteId(mem.id)} className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-rose-400 transition-all">
                                                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                                        </button>
                                                    </div>
                                                </div>
                                                {editingId === mem.id ? (
                                                    <div className="mt-3 space-y-2">
                                                        {/* Edit Form */}
                                                        <input type="text" value={editingDraft.topic_normalized || ''} onChange={(e) => setEditingDraft(p => ({ ...p, topic_normalized: e.target.value }))} className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs text-white" />
                                                        <input type="text" value={editingDraft.value || ''} onChange={(e) => setEditingDraft(p => ({ ...p, value: e.target.value }))} className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs text-white" />
                                                        <div className="flex justify-end gap-2">
                                                            <button onClick={cancelEdit} className="px-3 py-1.5 text-[10px] text-slate-400">Cancel</button>
                                                            <button onClick={saveEdit} className="px-3 py-1.5 text-[10px] bg-emerald-500 text-white rounded-lg">Save</button>
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <div className="text-xs text-slate-300 mt-1">{mem.value}</div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>

                            <div className="space-y-6">
                                {/* Pending Clarifications */}
                                <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
                                    <h3 className="text-sm font-semibold text-white mb-4">Pending Clarifications</h3>
                                    {pending.length === 0 ? (
                                        <EmptyState emoji="✅" title="All caught up!" description="No questions need review." variant="subtle" />
                                    ) : (
                                        <div className="space-y-4">
                                            {pending.map((thread) => (
                                                <div key={thread.id} className="rounded-xl border border-white/10 bg-black/30 p-3 space-y-3">
                                                    <p className="text-sm text-white">{thread.question}</p>
                                                    <input
                                                        type="text"
                                                        placeholder="Answer..."
                                                        value={answers[thread.id]?.answer || ''}
                                                        onChange={(e) => setAnswers(prev => ({ ...prev, [thread.id]: { answer: e.target.value } }))}
                                                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs text-white"
                                                    />
                                                    <div className="flex justify-end">
                                                        <button onClick={() => resolveClarification(thread)} className="px-3 py-2 text-[10px] bg-emerald-500 text-white rounded-lg">Save</button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                {/* Proposed Memories */}
                                <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
                                    <h3 className="text-sm font-semibold text-white mb-4">Proposed Memories</h3>
                                    {proposedMemories.length === 0 ? (
                                        <EmptyState emoji="🧠" title="No proposals" description="Complete an interview to generate." variant="subtle" />
                                    ) : (
                                        <div className="space-y-3">
                                            {proposedMemories.map((mem) => (
                                                <div key={mem.id} className="rounded-xl border border-white/10 bg-black/30 p-3 space-y-2">
                                                    <div className="text-xs font-semibold text-white">{mem.topic_normalized}</div>
                                                    <div className="text-xs text-slate-300">{mem.value}</div>
                                                    <div className="flex justify-end gap-2">
                                                        <button onClick={() => deleteMemory(mem.id)} className="text-[10px] text-rose-400">Reject</button>
                                                        <button onClick={() => approveProposedMemory(mem)} className="px-3 py-1.5 text-[10px] bg-emerald-500 text-white rounded-lg">Approve</button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* STEP 5: VALIDATE */}
                    <section id="training-validate" className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-xl font-bold text-white">Step 5. Validate</h2>
                                <p className="text-sm text-slate-400">Test your twin as a guest and verify responses match intent.</p>
                            </div>
                            <button
                                onClick={() => scrollToSection('training-checklist')}
                                className="text-xs text-indigo-300 hover:text-indigo-200"
                            >
                                Go to Checklist
                            </button>
                        </div>
                        <div className="max-w-5xl mx-auto">
                            <SimulatorView twinId={twinId} />
                        </div>
                    </section>

                    {/* CHECKLIST */}
                    <section id="training-checklist" className="space-y-4">
                        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
                            <h2 className="text-xl font-bold text-white mb-2">Verification Checklist</h2>
                            <p className="text-sm text-slate-400 mb-4">Use this to validate training, ingestion, and summaries.</p>

                            <div className="space-y-4 text-sm text-slate-300">
                                <div>
                                    <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">Owner Training Flow</div>
                                    <ul className="list-disc list-inside space-y-1">
                                        <li>Go to Training → Step 1 (Intent).</li>
                                        <li>Fill Use case, Audience, Boundaries, Public intro, click Save & Continue.</li>
                                        <li>Refresh the page and confirm the fields persist.</li>
                                        <li>Complete the Interview.</li>
                                        <li>Open Inbox and approve 2–3 proposed memories.</li>
                                        <li>Go to Validate and ask: “What’s your primary use case?”</li>
                                        <li>Ask: “What should users never ask you?”</li>
                                        <li>Confirm responses reflect Intent Summary.</li>
                                    </ul>
                                </div>

                                <div>
                                    <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">Ingestion Verification By Channel</div>
                                    <ul className="list-disc list-inside space-y-1">
                                        <li>After each source ingests, confirm: status moves from processing → live.</li>
                                        <li>Confirm chunk count increases.</li>
                                        <li>Ask a question about the ingested content and verify citations.</li>
                                    </ul>
                                </div>

                                <div>
                                    <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">Document Upload (PDF/DOCX)</div>
                                    <ul className="list-disc list-inside space-y-1">
                                        <li>Upload a document.</li>
                                        <li>Wait for status to show live.</li>
                                        <li>Ask a question directly from the document.</li>
                                        <li>Verify citations in response.</li>
                                    </ul>
                                </div>

                                <div>
                                    <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">YouTube</div>
                                    <ul className="list-disc list-inside space-y-1">
                                        <li>Paste a public YouTube URL.</li>
                                        <li>Wait for live.</li>
                                        <li>Ask a question about a specific section.</li>
                                        <li>Verify citations in response.</li>
                                    </ul>
                                </div>

                                <div>
                                    <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">Podcast (RSS)</div>
                                    <ul className="list-disc list-inside space-y-1">
                                        <li>Paste a valid RSS feed URL.</li>
                                        <li>Wait for live.</li>
                                        <li>Ask a question referencing a specific episode.</li>
                                        <li>Verify citations in response.</li>
                                    </ul>
                                </div>

                                <div>
                                    <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">X Thread</div>
                                    <ul className="list-disc list-inside space-y-1">
                                        <li>Paste a public thread URL.</li>
                                        <li>Wait for live.</li>
                                        <li>Ask a question about the thread.</li>
                                        <li>Verify citations in response.</li>
                                    </ul>
                                </div>

                                <div>
                                    <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">Chunk Retention + Summarization</div>
                                    <ul className="list-disc list-inside space-y-1">
                                        <li>Open Knowledge Profile and confirm total chunks &gt; 0 and fact/opinion counts updated.</li>
                                        <li>Refresh the page and confirm counts don’t reset.</li>
                                        <li>Ask: “Summarize my views on &lt;topic&gt; in 3 bullets.”</li>
                                        <li>Ensure responses are grounded and cite the correct sources.</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </section>
                </div>
            </div>
        </div>
    );
}
