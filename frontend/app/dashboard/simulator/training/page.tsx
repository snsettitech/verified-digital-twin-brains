'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';
import { resolveApiBaseUrl } from '@/lib/api';
import { useTwin } from '@/lib/context/TwinContext';
import { SimulatorView } from '@/components/training';

interface ActiveTrainingSession {
    id: string;
    status: 'active' | 'stopped' | 'expired';
    started_at?: string;
    ended_at?: string;
}

export default function SimulatorTrainingPage() {
    const { activeTwin } = useTwin();
    const [loading, setLoading] = useState(true);
    const [sessionLoading, setSessionLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [activeSession, setActiveSession] = useState<ActiveTrainingSession | null>(null);

    const fetchActiveSession = useCallback(async () => {
        if (!activeTwin?.id) {
            setActiveSession(null);
            setLoading(false);
            return;
        }

        setLoading(true);
        setError(null);
        try {
            const supabase = getSupabaseClient();
            const { data: { session } } = await supabase.auth.getSession();
            if (!session?.access_token) {
                setError('Not authenticated.');
                setActiveSession(null);
                return;
            }

            const backendUrl = resolveApiBaseUrl();
            const res = await fetch(`${backendUrl}/twins/${activeTwin.id}/training-sessions/active`, {
                headers: { Authorization: `Bearer ${session.access_token}` },
            });

            if (!res.ok) {
                throw new Error(`Failed to load active training session (${res.status})`);
            }

            const payload = await res.json();
            setActiveSession(payload?.active ? (payload?.session || null) : null);
        } catch (err) {
            console.error(err);
            setError('Failed to load training session status.');
            setActiveSession(null);
        } finally {
            setLoading(false);
        }
    }, [activeTwin?.id]);

    useEffect(() => {
        fetchActiveSession();
    }, [fetchActiveSession]);

    const startTrainingSession = async () => {
        if (!activeTwin?.id) return;

        setSessionLoading(true);
        setError(null);
        try {
            const supabase = getSupabaseClient();
            const { data: { session } } = await supabase.auth.getSession();
            if (!session?.access_token) {
                setError('Not authenticated.');
                return;
            }

            const backendUrl = resolveApiBaseUrl();
            const res = await fetch(`${backendUrl}/twins/${activeTwin.id}/training-sessions/start`, {
                method: 'POST',
                headers: {
                    Authorization: `Bearer ${session.access_token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ metadata: { source: 'simulator_training_page' } }),
            });

            if (!res.ok) {
                throw new Error(`Failed to start training session (${res.status})`);
            }

            const payload = await res.json();
            setActiveSession(payload?.session || null);
        } catch (err) {
            console.error(err);
            setError('Failed to start training session.');
        } finally {
            setSessionLoading(false);
        }
    };

    const stopTrainingSession = async () => {
        if (!activeTwin?.id || !activeSession?.id) return;

        setSessionLoading(true);
        setError(null);
        try {
            const supabase = getSupabaseClient();
            const { data: { session } } = await supabase.auth.getSession();
            if (!session?.access_token) {
                setError('Not authenticated.');
                return;
            }

            const backendUrl = resolveApiBaseUrl();
            const res = await fetch(`${backendUrl}/twins/${activeTwin.id}/training-sessions/${activeSession.id}/stop`, {
                method: 'POST',
                headers: { Authorization: `Bearer ${session.access_token}` },
            });

            if (!res.ok) {
                throw new Error(`Failed to stop training session (${res.status})`);
            }

            setActiveSession(null);
        } catch (err) {
            console.error(err);
            setError('Failed to stop training session.');
        } finally {
            setSessionLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#0a0a0f] text-white p-6 md:p-10">
            <div className="max-w-6xl mx-auto space-y-4">
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <h1 className="text-2xl font-black tracking-tight">Training Simulator</h1>
                        <p className="text-sm text-slate-400 mt-1">
                            Isolated page for owner-training interactions and clarification flows.
                        </p>
                    </div>
                    <Link
                        href="/dashboard/simulator"
                        className="px-3 py-2 text-xs font-semibold rounded-lg border border-white/15 bg-white/5 hover:bg-white/10 transition-colors"
                    >
                        Back to Hub
                    </Link>
                </div>

                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 flex items-center justify-between gap-4">
                    <div>
                        <div className="text-xs uppercase tracking-wider text-slate-400">Training Session</div>
                        <div className="text-sm text-white mt-1">
                            {activeSession?.id ? `Active (${activeSession.id})` : 'Inactive'}
                        </div>
                        {!activeSession?.id && (
                            <div className="text-xs text-amber-300 mt-1">
                                No active session: chat falls back to owner mode until session starts.
                            </div>
                        )}
                        {error && <div className="text-xs text-rose-300 mt-1">{error}</div>}
                    </div>
                    <div className="flex items-center gap-2">
                        {activeSession?.id ? (
                            <button
                                onClick={stopTrainingSession}
                                disabled={sessionLoading}
                                className="px-3 py-2 text-xs font-semibold rounded-lg bg-rose-600 hover:bg-rose-500 text-white disabled:opacity-50"
                            >
                                {sessionLoading ? 'Stopping...' : 'Stop Session'}
                            </button>
                        ) : (
                            <button
                                onClick={startTrainingSession}
                                disabled={sessionLoading || loading}
                                className="px-3 py-2 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50"
                            >
                                {sessionLoading ? 'Starting...' : 'Start Session'}
                            </button>
                        )}
                    </div>
                </div>

                <SimulatorView
                    twinId={activeTwin?.id}
                    mode={activeSession?.id ? 'training' : 'owner'}
                    trainingSessionId={activeSession?.id || null}
                />
            </div>
        </div>
    );
}
