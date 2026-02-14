'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';
import { resolveApiBaseUrl } from '@/lib/api';
import { useTwin } from '@/lib/context/TwinContext';
import { SimulatorView } from '@/components/training';

export default function SimulatorPublicPage() {
    const { activeTwin } = useTwin();
    const [shareUrl, setShareUrl] = useState<string>('');
    const [loadingShare, setLoadingShare] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchShareLink = useCallback(async () => {
        if (!activeTwin?.id) {
            setShareUrl('');
            return;
        }

        setLoadingShare(true);
        setError(null);
        try {
            const supabase = getSupabaseClient();
            const { data: { session } } = await supabase.auth.getSession();
            if (!session?.access_token) {
                setError('Not authenticated.');
                return;
            }

            const backendUrl = resolveApiBaseUrl();
            const res = await fetch(`${backendUrl}/twins/${activeTwin.id}/share-link`, {
                headers: { Authorization: `Bearer ${session.access_token}` },
            });

            if (!res.ok) {
                throw new Error(`Failed to load share link (${res.status})`);
            }

            const payload = await res.json();
            setShareUrl(payload?.share_url || '');
        } catch (err) {
            console.error(err);
            setError('Failed to load public share link.');
            setShareUrl('');
        } finally {
            setLoadingShare(false);
        }
    }, [activeTwin?.id]);

    useEffect(() => {
        fetchShareLink();
    }, [fetchShareLink]);

    return (
        <div className="min-h-screen bg-[#0a0a0f] text-white p-6 md:p-10">
            <div className="max-w-6xl mx-auto space-y-4">
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <h1 className="text-2xl font-black tracking-tight">Public Simulator</h1>
                        <p className="text-sm text-slate-400 mt-1">
                            Separate page to validate public-facing behavior and share-link chat.
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
                    <div className="text-xs uppercase tracking-wider text-slate-400">Public Route</div>
                    {loadingShare ? (
                        <div className="text-sm text-slate-300">Loading share link...</div>
                    ) : shareUrl ? (
                        <div className="flex flex-wrap items-center gap-3">
                            <a
                                href={shareUrl}
                                target="_blank"
                                rel="noreferrer"
                                className="px-3 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white"
                            >
                                Open Real Public Chat
                            </a>
                            <span className="text-xs text-slate-400 break-all">{shareUrl}</span>
                        </div>
                    ) : (
                        <div className="text-sm text-amber-300">
                            No share link resolved. Enable sharing in `Share` first.
                        </div>
                    )}
                    {error && <div className="text-xs text-rose-300">{error}</div>}
                    <div className="text-xs text-slate-400">
                        Note: The embedded simulator below is a quick public-mode test. Use the share link above for exact public endpoint behavior.
                    </div>
                </div>

                <SimulatorView twinId={activeTwin?.id} mode="public" />
            </div>
        </div>
    );
}
