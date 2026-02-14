'use client';

import { useSearchParams, useRouter, useParams } from 'next/navigation';
import { useState, useEffect, useCallback, useRef, Suspense } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';
import { ConsoleLayout } from '@/components/console/ConsoleLayout';
import { OverviewTab } from '@/components/console/tabs/OverviewTab';
import { KnowledgeTab } from '@/components/console/tabs/KnowledgeTab';
import { ChatTab } from '@/components/console/tabs/ChatTab';
import { TrainingTab } from '@/components/console/tabs/TrainingTab';
// ActionsTab and EscalationsTab archived - out of scope for Clone-for-Experts
import { PublishTab } from '@/components/console/tabs/PublishTab';
import { PublicChatTab } from '@/components/console/tabs/PublicChatTab';
import { SettingsTab } from '@/components/console/tabs/SettingsTab';
import { resolveApiBaseUrl } from '@/lib/api';
import { ingestUrlWithFallback, uploadFileWithFallback } from '@/lib/ingestionApi';

interface Twin {
    id: string;
    name: string;
    system_instructions: string;
    is_public: boolean;
    share_token: string | null;
    specialization_id: string;
}

interface ShareLinkInfo {
    twin_id: string;
    share_token: string | null;
    share_url: string | null;
    public_share_enabled: boolean;
}

function TwinConsoleContent({ twinId }: { twinId: string }) {
    const searchParams = useSearchParams();
    const router = useRouter();
    const supabase = getSupabaseClient();
    const isE2EBypass =
        process.env.NODE_ENV !== 'production' &&
        process.env.NEXT_PUBLIC_E2E_BYPASS_AUTH === '1';

    const [twin, setTwin] = useState<Twin | null>(null);
    const [shareInfo, setShareInfo] = useState<ShareLinkInfo | null>(null);
    const [loading, setLoading] = useState(true);
    const [stats, setStats] = useState({
        sources: 0,
        indexedSources: 0,
        processingSources: 0,
        conversations: 0,
        escalations: 0
    });

    const activeTab = searchParams.get('tab') || 'overview';

    const retryRef = useRef(0);
    const fetchTwin = useCallback(async () => {
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) {
                if (retryRef.current < 5) {
                    retryRef.current += 1;
                    setTimeout(fetchTwin, 600);
                } else {
                    throw new Error('Not authenticated');
                }
                return;
            }
            const backendUrl = resolveApiBaseUrl();
            const response = await fetch(`${backendUrl}/twins/${twinId}`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(errText || 'Failed to fetch twin');
            }
            const data = await response.json();
            setTwin(data);

            // Fetch share link info (canonical)
            try {
                const shareRes = await fetch(`${backendUrl}/twins/${twinId}/share-link`, {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });
                if (shareRes.ok) {
                    const shareData = await shareRes.json();
                    setShareInfo(shareData);
                }
            } catch (shareErr) {
                console.warn('Failed to fetch share link info:', shareErr);
            }

            // Fetch stats
            const [sourceCountRes, indexedCountRes, processingCountRes] = await Promise.all([
                supabase
                    .from('sources')
                    .select('*', { count: 'exact', head: true })
                    .eq('twin_id', twinId),
                supabase
                    .from('sources')
                    .select('*', { count: 'exact', head: true })
                    .eq('twin_id', twinId)
                    .in('status', ['live', 'processed', 'indexed']),
                supabase
                    .from('sources')
                    .select('*', { count: 'exact', head: true })
                    .eq('twin_id', twinId)
                    .in('status', ['processing', 'pending'])
            ]);

            const sourceCount = sourceCountRes.count || 0;
            const indexedCount = indexedCountRes.count || 0;
            const processingCount = processingCountRes.count || 0;

            const { count: escalationCount } = await supabase
                .from('escalations')
                .select('*', { count: 'exact', head: true })
                .eq('twin_id', twinId)
                .eq('status', 'pending');

            setStats({
                sources: sourceCount,
                indexedSources: indexedCount,
                processingSources: processingCount,
                conversations: 0, // Would need sessions table
                escalations: escalationCount || 0
            });
        } catch (error) {
            console.error('Error fetching twin:', error);
        } finally {
            setLoading(false);
        }
    }, [supabase, twinId]);

    useEffect(() => {
        fetchTwin();
        const { data } = supabase.auth.onAuthStateChange((_event: string, session: { access_token?: string } | null) => {
            if (session?.access_token) {
                retryRef.current = 0;
                fetchTwin();
            }
        });
        return () => {
            data?.subscription?.unsubscribe();
        };
    }, [fetchTwin, supabase]);

    const handleTogglePublic = async (isPublic: boolean) => {
        try {
            const backendUrl = resolveApiBaseUrl();
            // Use authenticated fetch (assuming Supabase session is handled by the fetch wrapper or direct useAuthFetch)
            const { data: { session } } = await supabase.auth.getSession();

            const res = await fetch(`${backendUrl}/twins/${twinId}/sharing`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${session?.access_token}`
                },
                body: JSON.stringify({ is_public: isPublic })
            });

            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.detail?.message || 'Failed to update twin');
            }

            // Update local share state
            setShareInfo(prev => prev ? { ...prev, public_share_enabled: isPublic } : prev);

            // If enabling and no token exists, regenerate
            if (isPublic && !shareInfo?.share_token) {
                await handleRegenerateLink();
            }
        } catch (error: any) {
            console.error('Error toggling public status:', error);
            alert(error.message || 'Failed to update public status');
        }
    };

    const handleRegenerateLink = async () => {
        try {
            const backendUrl = resolveApiBaseUrl();
            const { data: { session } } = await supabase.auth.getSession();
            const res = await fetch(`${backendUrl}/twins/${twinId}/share-link`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${session?.access_token}`
                }
            });
            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.detail?.message || 'Failed to regenerate share link');
            }
            const data = await res.json();
            setShareInfo(data);
        } catch (error: any) {
            console.error('Error regenerating share link:', error);
            alert(error.message || 'Failed to regenerate share link');
        }
    };

    const handleKnowledgeUrlSubmit = useCallback(async (url: string) => {
        const backendUrl = resolveApiBaseUrl();
        const headers: Record<string, string> = {};

        if (!isE2EBypass) {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) throw new Error('Not authenticated');
            headers['Authorization'] = `Bearer ${token}`;
        }

        await ingestUrlWithFallback({ backendUrl, twinId, url, headers });
    }, [isE2EBypass, supabase, twinId]);

    const handleKnowledgeUpload = useCallback(async (files: File[]) => {
        const backendUrl = resolveApiBaseUrl();
        const headers: Record<string, string> = {};

        if (!isE2EBypass) {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) throw new Error('Not authenticated');
            headers['Authorization'] = `Bearer ${token}`;
        }

        for (const file of files) {
            await uploadFileWithFallback({ backendUrl, twinId, file, headers });
        }
    }, [isE2EBypass, supabase, twinId]);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-screen bg-[#0a0a0f]">
                <div className="flex flex-col items-center gap-4">
                    <div className="w-12 h-12 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                    <p className="text-slate-400">Loading twin...</p>
                </div>
            </div>
        );
    }

    if (!twin) {
        return (
            <div className="flex items-center justify-center h-screen bg-[#0a0a0f]">
                <div className="text-center">
                    <h1 className="text-2xl font-bold text-white mb-2">Twin not found</h1>
                    <p className="text-slate-400 mb-4">The requested twin doesn't exist or you don't have access.</p>
                    <button
                        onClick={() => router.push('/dashboard')}
                        className="px-4 py-2 text-sm font-medium text-indigo-400 hover:text-indigo-300"
                    >
                        ← Back to Dashboard
                    </button>
                </div>
            </div>
        );
    }

    const isArchived = (twin as any)?.settings?.deleted_at;
    if (isArchived) {
        return (
            <div className="flex items-center justify-center h-screen bg-[#0a0a0f]">
                <div className="text-center max-w-md">
                    <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-red-500/20 flex items-center justify-center">
                        <svg className="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                    </div>
                    <h2 className="text-xl font-bold text-white mb-2">This twin is archived</h2>
                    <p className="text-slate-400">Chat, publish, and verification are disabled for archived twins.</p>
                </div>
            </div>
        );
    }

    const effectiveIsPublic = shareInfo?.public_share_enabled ?? twin?.is_public ?? false;
    const effectiveShareLink = shareInfo?.share_url || undefined;
    const effectiveShareToken = shareInfo?.share_token || null;

    const renderTab = () => {
        switch (activeTab) {
            case 'overview':
                return (
                    <OverviewTab
                        twinId={twinId}
                        stats={{
                            totalSources: stats.sources,
                            indexedSources: stats.indexedSources,
                            processingSources: stats.processingSources,
                            totalConversations: stats.conversations,
                            totalMessages: 0,
                            avgResponseTime: '< 1s',
                            escalations: stats.escalations,
                            satisfaction: 0
                        }}
                    />
                );
            case 'knowledge':
                return (
                    <KnowledgeTab
                        twinId={twinId}
                        onUrlSubmit={handleKnowledgeUrlSubmit}
                        onUpload={handleKnowledgeUpload}
                    />
                );
            case 'chat':
                return <ChatTab twinId={twinId} twinName={twin.name} />;
            case 'training':
                return <TrainingTab twinId={twinId} />;
            // escalations archived - out of scope
            case 'publish':
                return (
                    <PublishTab
                        twinId={twinId}
                        twinName={twin.name}
                        isPublic={effectiveIsPublic}
                        shareLink={effectiveShareLink}
                        onTogglePublic={handleTogglePublic}
                        onRegenerateLink={handleRegenerateLink}
                    />
                );
            case 'public-chat':
                return (
                    <PublicChatTab
                        twinId={twinId}
                        shareToken={effectiveShareToken}
                        isPublic={effectiveIsPublic}
                    />
                );
            // actions archived - out of scope
            case 'settings':
                return (
                    <SettingsTab
                        twinId={twinId}
                        settings={{
                            name: twin.name,
                            systemInstructions: twin.system_instructions
                        }}
                    />
                );
            default:
                return <OverviewTab twinId={twinId} />;
        }
    };

    return (
        <ConsoleLayout
            twinId={twinId}
            twinName={twin.name}
            activeTab={activeTab}
            stats={stats}
        >
            {renderTab()}
        </ConsoleLayout>
    );
}

export default function TwinConsolePage() {
    const params = useParams();
    const twinId = (params?.id as string) || '';

    return (
        <Suspense fallback={
            <div className="flex items-center justify-center h-screen bg-[#0a0a0f]">
                <div className="w-12 h-12 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
            </div>
        }>
            <TwinConsoleContent twinId={twinId} />
        </Suspense>
    );
}
