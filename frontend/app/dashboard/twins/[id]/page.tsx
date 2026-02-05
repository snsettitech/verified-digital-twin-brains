'use client';

import { useSearchParams, useRouter } from 'next/navigation';
import { useState, useEffect, Suspense } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';
import { ConsoleLayout } from '@/components/console/ConsoleLayout';
import { OverviewTab } from '@/components/console/tabs/OverviewTab';
import { KnowledgeTab } from '@/components/console/tabs/KnowledgeTab';
import { ChatTab } from '@/components/console/tabs/ChatTab';
import { EscalationsTab } from '@/components/console/tabs/EscalationsTab';
import { PublishTab } from '@/components/console/tabs/PublishTab';
import { ActionsTab } from '@/components/console/tabs/ActionsTab';
import { SettingsTab } from '@/components/console/tabs/SettingsTab';

interface Twin {
    id: string;
    name: string;
    system_instructions: string;
    is_public: boolean;
    share_token: string | null;
    specialization_id: string;
}

function TwinConsoleContent({ twinId }: { twinId: string }) {
    const searchParams = useSearchParams();
    const router = useRouter();
    const supabase = getSupabaseClient();

    const [twin, setTwin] = useState<Twin | null>(null);
    const [loading, setLoading] = useState(true);
    const [stats, setStats] = useState({
        sources: 0,
        conversations: 0,
        escalations: 0
    });

    const activeTab = searchParams.get('tab') || 'overview';

    useEffect(() => {
        const fetchTwin = async () => {
            try {
                const { data, error } = await supabase
                    .from('twins')
                    .select('*')
                    .eq('id', twinId)
                    .single();

                if (error) throw error;
                setTwin(data);

                // Fetch stats
                const { count: sourceCount } = await supabase
                    .from('sources')
                    .select('*', { count: 'exact', head: true })
                    .eq('twin_id', twinId);

                const { count: escalationCount } = await supabase
                    .from('escalations')
                    .select('*', { count: 'exact', head: true })
                    .eq('twin_id', twinId)
                    .eq('status', 'pending');

                setStats({
                    sources: sourceCount || 0,
                    conversations: 0, // Would need sessions table
                    escalations: escalationCount || 0
                });
            } catch (error) {
                console.error('Error fetching twin:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchTwin();
    }, [twinId, supabase]);

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

    const renderTab = () => {
        switch (activeTab) {
            case 'overview':
                return (
                    <OverviewTab
                        twinId={twinId}
                        stats={{
                            totalSources: stats.sources,
                            approvedSources: stats.sources,
                            pendingReview: 0,
                            totalConversations: stats.conversations,
                            totalMessages: 0,
                            avgResponseTime: '< 1s',
                            escalations: stats.escalations,
                            satisfaction: 0
                        }}
                    />
                );
            case 'knowledge':
                return <KnowledgeTab twinId={twinId} />;
            case 'chat':
                return <ChatTab twinId={twinId} twinName={twin.name} />;
            case 'escalations':
                return <EscalationsTab twinId={twinId} />;
            case 'publish':
                return (
                    <PublishTab
                        twinId={twinId}
                        twinName={twin.name}
                        isPublic={twin.is_public}
                        shareLink={twin.share_token ? `/share/${twinId}/${twin.share_token}` : undefined}
                    />
                );
            case 'actions':
                return <ActionsTab twinId={twinId} />;
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

export default function TwinConsolePage({ params }: { params: { id: string } }) {
    return (
        <Suspense fallback={
            <div className="flex items-center justify-center h-screen bg-[#0a0a0f]">
                <div className="w-12 h-12 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
            </div>
        }>
            <TwinConsoleContent twinId={params.id} />
        </Suspense>
    );
}
