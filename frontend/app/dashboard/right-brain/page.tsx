'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import InterviewInterface from '../../../components/Chat/InterviewInterface';
import BrainGraph from '../../../components/Brain/BrainGraph';
import { useTwin } from '@/lib/context/TwinContext';
import { getSupabaseClient } from '@/lib/supabase/client';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export default function RightBrainPage() {
    const router = useRouter();
    const { activeTwin, isLoading, twins, refreshTwins, user } = useTwin();
    const supabase = getSupabaseClient();

    const [refreshGraphTrigger, setRefreshGraphTrigger] = useState(0);
    const [nodeCount, setNodeCount] = useState(0);
    const [sessionTime, setSessionTime] = useState(0);
    const [creatingTwin, setCreatingTwin] = useState(false);
    const [createError, setCreateError] = useState<string | null>(null);

    // Session timer
    useEffect(() => {
        const interval = setInterval(() => {
            setSessionTime(prev => prev + 1);
        }, 1000);
        return () => clearInterval(interval);
    }, []);

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const handleGraphUpdate = () => {
        setRefreshGraphTrigger(prev => prev + 1);
        setNodeCount(prev => prev + 1);
    };

    // Quick create a default twin
    const createDefaultTwin = useCallback(async () => {
        setCreatingTwin(true);
        setCreateError(null);

        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;

            if (!token) {
                setCreateError('Not authenticated. Please log in again.');
                return;
            }

            // CRITICAL: user.tenant_id comes from the synced user record (tenants table UUID)
            // DO NOT use session.user.id - that's the auth UUID which is DIFFERENT
            if (!user?.tenant_id) {
                setCreateError('No tenant associated. Please refresh the page.');
                return;
            }

            const response = await fetch(`${API_BASE_URL}/twins`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name: user?.full_name ? `${user.full_name}'s Twin` : 'My Digital Twin',
                    tenant_id: user.tenant_id,  // FIX: Use actual tenant UUID, not auth user ID
                    specialization: 'vc-brain',
                    settings: {}
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to create twin');
            }

            // Refresh twins list to pick up the new twin
            await refreshTwins();

        } catch (error: any) {
            console.error('Error creating twin:', error);
            setCreateError(error.message || 'Failed to create twin');
        } finally {
            setCreatingTwin(false);
        }
    }, [supabase, user, refreshTwins]);

    // Loading state
    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-[calc(100vh-theme(spacing.20))]">
                <div className="text-center">
                    <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                    <p className="text-slate-500">Loading your twin...</p>
                </div>
            </div>
        );
    }

    // No twin state - Show inline creation instead of redirect
    if (!activeTwin || twins.length === 0) {
        return (
            <div className="flex items-center justify-center h-[calc(100vh-theme(spacing.20))] bg-gradient-to-br from-slate-50 via-white to-indigo-50/30">
                <div className="text-center max-w-lg p-8">
                    <div className="w-20 h-20 bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-2xl shadow-indigo-500/40">
                        <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                    </div>
                    <h2 className="text-3xl font-black text-slate-900 mb-3">Start Your Interview</h2>
                    <p className="text-slate-500 mb-8 text-lg">
                        Let's create your digital twin and begin the cognitive interview.
                        I'll learn about you through conversation.
                    </p>

                    {createError && (
                        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
                            {createError}
                        </div>
                    )}

                    <div className="space-y-4">
                        <button
                            onClick={createDefaultTwin}
                            disabled={creatingTwin}
                            className="w-full px-8 py-4 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-2xl font-bold text-lg hover:shadow-2xl hover:shadow-indigo-500/40 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3"
                        >
                            {creatingTwin ? (
                                <>
                                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                                    Creating Your Twin...
                                </>
                            ) : (
                                <>
                                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                                    </svg>
                                    Start Interview Now
                                </>
                            )}
                        </button>

                        <button
                            onClick={() => router.push('/onboarding')}
                            className="w-full px-8 py-3 bg-white border-2 border-slate-200 text-slate-600 rounded-2xl font-semibold hover:border-indigo-300 hover:text-indigo-600 transition-all"
                        >
                            Go Through Full Onboarding Instead
                        </button>
                    </div>

                    <p className="text-xs text-slate-400 mt-6">
                        You can customize your twin's specialization later in Settings
                    </p>
                </div>
            </div>
        );
    }


    return (
        <div className="flex flex-col h-[calc(100vh-theme(spacing.20))] p-6 md:p-10 max-w-[1920px] mx-auto w-full bg-gradient-to-br from-slate-50 via-white to-indigo-50/30">
            {/* Premium Header */}
            <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                    <div className="relative">
                        <div className="w-14 h-14 bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 rounded-2xl flex items-center justify-center text-white shadow-2xl shadow-indigo-500/40 animate-pulse-glow">
                            <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M22 12h-4l-3 9L9 3l-3 9H2" /></svg>
                        </div>
                        <div className="absolute -bottom-1 -right-1 w-5 h-5 bg-green-500 border-4 border-white rounded-full animate-pulse"></div>
                    </div>
                    <div>
                        <h1 className="text-3xl font-black tracking-tight bg-gradient-to-r from-slate-900 via-indigo-900 to-purple-900 bg-clip-text text-transparent">Right Brain Training</h1>
                        <p className="text-slate-500 font-medium flex items-center gap-2">
                            <span className="w-2 h-2 bg-indigo-500 rounded-full"></span>
                            Cognitive Interview Session
                        </p>
                    </div>
                </div>

                {/* Session Stats */}
                <div className="flex items-center gap-4">
                    <div className="glass-card px-4 py-2 flex items-center gap-3">
                        <div className="text-center">
                            <div className="text-2xl font-black text-indigo-600">{nodeCount}</div>
                            <div className="text-[10px] uppercase tracking-widest text-slate-400 font-bold">Concepts</div>
                        </div>
                        <div className="w-px h-8 bg-slate-200"></div>
                        <div className="text-center">
                            <div className="text-2xl font-black text-purple-600 font-mono">{formatTime(sessionTime)}</div>
                            <div className="text-[10px] uppercase tracking-widest text-slate-400 font-bold">Session</div>
                        </div>
                    </div>
                    <div className="px-4 py-2 bg-gradient-to-r from-purple-50 to-pink-50 text-purple-700 text-xs font-bold rounded-xl border border-purple-100 uppercase tracking-widest flex items-center gap-2 shadow-lg shadow-purple-100/50">
                        <div className="relative">
                            <span className="w-2 h-2 bg-purple-500 rounded-full block"></span>
                            <span className="absolute inset-0 w-2 h-2 bg-purple-500 rounded-full animate-ping"></span>
                        </div>
                        Scribe Recording
                    </div>
                </div>
            </div>

            {/* Main Grid with Glass Divider */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-0 relative">
                {/* Glass Divider */}
                <div className="hidden lg:block absolute left-1/2 top-4 bottom-4 w-px bg-gradient-to-b from-transparent via-slate-200 to-transparent transform -translate-x-1/2 z-10"></div>

                {/* Left Pane: Interview Chat */}
                <div className="flex flex-col h-full min-h-0">
                    <InterviewInterface
                        twinId={activeTwin.id}
                        onGraphUpdate={handleGraphUpdate}
                    />
                </div>

                {/* Right Pane: Live Graph Visualization */}
                <div className="bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-900 rounded-3xl border border-slate-700/50 shadow-2xl overflow-hidden flex flex-col h-full min-h-0 relative">
                    {/* Graph Header Overlay */}
                    <div className="absolute top-0 left-0 right-0 p-6 bg-gradient-to-b from-slate-900 to-transparent z-10">
                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="text-sm font-black text-white/80 uppercase tracking-widest">Mental Model</h3>
                                <p className="text-xs text-slate-400 mt-1">Live knowledge graph • Updates in real-time</p>
                            </div>
                            <div className="flex items-center gap-2">
                                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                                <span className="text-xs text-green-400 font-bold">SYNCED</span>
                            </div>
                        </div>
                    </div>

                    <BrainGraph
                        twinId={activeTwin.id}
                        refreshTrigger={refreshGraphTrigger}
                    />

                    {/* Graph Legend Overlay */}
                    <div className="absolute bottom-4 left-4 right-4 p-4 bg-slate-800/80 backdrop-blur-xl rounded-2xl border border-slate-700/50">
                        <div className="flex items-center justify-between text-xs">
                            <div className="flex items-center gap-4">
                                <div className="flex items-center gap-2">
                                    <div className="w-3 h-3 rounded-full bg-indigo-500"></div>
                                    <span className="text-slate-300">Concept</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="w-3 h-3 rounded-full bg-purple-500"></div>
                                    <span className="text-slate-300">Self</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
                                    <span className="text-slate-300">Knowledge</span>
                                </div>
                            </div>
                            <div className="text-slate-400 font-mono">{nodeCount} nodes</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}


