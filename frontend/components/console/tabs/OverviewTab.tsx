'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';

interface Conversation {
    id: string;
    preview: string;
    message_count: number;
    created_at: string;
    updated_at: string;
}

interface OverviewTabProps {
    twinId: string;
    stats?: {
        totalSources: number;
        indexedSources: number;
        processingSources: number;
        totalConversations: number;
        totalMessages: number;
        avgResponseTime: string;
        escalations: number;
        satisfaction: number;
    };
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function OverviewTab({ twinId, stats }: OverviewTabProps) {
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [conversationsLoading, setConversationsLoading] = useState(false);
    const [conversationsError, setConversationsError] = useState<string | null>(null);

    const defaultStats = {
        totalSources: stats?.totalSources ?? 0,
        indexedSources: stats?.indexedSources ?? 0,
        processingSources: stats?.processingSources ?? 0,
        totalConversations: stats?.totalConversations ?? 0,
        totalMessages: stats?.totalMessages ?? 0,
        avgResponseTime: stats?.avgResponseTime ?? '--',
        escalations: stats?.escalations ?? 0,
        satisfaction: stats?.satisfaction ?? 0,
    };

    // Fetch recent conversations on mount
    useEffect(() => {
        const fetchConversations = async () => {
            if (!twinId) return;
            setConversationsLoading(true);
            setConversationsError(null);
            try {
                const response = await fetch(`${API_URL}/twins/${twinId}/conversations?limit=5`, {
                    credentials: 'include'
                });
                if (response.ok) {
                    const data = await response.json();
                    setConversations(data.conversations || data || []);
                } else {
                    setConversationsError('Failed to load conversations');
                }
            } catch {
                setConversationsError('Failed to load conversations');
            } finally {
                setConversationsLoading(false);
            }
        };
        fetchConversations();
    }, [twinId]);

    const formatTimeAgo = (dateString: string) => {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
    };

    const statCards = [
        {
            label: 'Knowledge Sources',
            value: defaultStats.totalSources,
            subtext: `${defaultStats.indexedSources} indexed`,
            icon: '📚',
            color: 'from-blue-500 to-indigo-500'
        },
        {
            label: 'Conversations',
            value: defaultStats.totalConversations,
            subtext: `${defaultStats.totalMessages} messages`,
            icon: '💬',
            color: 'from-emerald-500 to-teal-500'
        },
        {
            label: 'Response Time',
            value: defaultStats.avgResponseTime,
            subtext: 'average',
            icon: '⚡',
            color: 'from-amber-500 to-orange-500'
        },
        {
            label: 'Escalations',
            value: defaultStats.escalations,
            subtext: 'pending review',
            icon: '🚨',
            color: defaultStats.escalations > 0 ? 'from-red-500 to-rose-500' : 'from-slate-500 to-slate-600'
        }
    ];

    const quickActions = [
        { label: 'Add Knowledge', icon: '➕', href: `?tab=knowledge` },
        { label: 'Test Chat', icon: '💬', href: `?tab=chat` },
        { label: 'Share Twin', icon: '🔗', href: `?tab=publish` },
        { label: 'View Settings', icon: '⚙️', href: `?tab=settings` }
    ];

    return (
        <div className="p-6 space-y-6">
            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {statCards.map((card, index) => (
                    <div
                        key={index}
                        className="relative overflow-hidden bg-white/5 border border-white/10 rounded-2xl p-5 hover:bg-white/[0.07] transition-colors"
                    >
                        <div className="flex items-start justify-between">
                            <div>
                                <p className="text-slate-400 text-sm font-medium">{card.label}</p>
                                <p className="text-3xl font-bold text-white mt-1">{card.value}</p>
                                <p className="text-slate-500 text-xs mt-1">{card.subtext}</p>
                            </div>
                            <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${card.color} flex items-center justify-center text-lg`}>
                                {card.icon}
                            </div>
                        </div>
                        <div className={`absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r ${card.color} opacity-50`} />
                    </div>
                ))}
            </div>

            {/* Quick Actions */}
            <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Quick Actions</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {quickActions.map((action, index) => (
                        <Link
                            key={index}
                            href={action.href}
                            className="flex flex-col items-center gap-2 p-4 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl transition-all hover:scale-[1.02]"
                        >
                            <span className="text-2xl">{action.icon}</span>
                            <span className="text-sm font-medium text-slate-300">{action.label}</span>
                        </Link>
                    ))}
                </div>
            </div>

            {/* Recent Activity */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Recent Conversations */}
                <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-semibold text-white">Recent Conversations</h3>
                        <Link href="?tab=chat" className="text-sm text-indigo-400 hover:text-indigo-300">View all</Link>
                    </div>

                    <div className="space-y-3">
                        {conversationsLoading ? (
                            <div className="flex items-center justify-center py-8">
                                <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                                <span className="ml-3 text-slate-400 text-sm">Loading conversations...</span>
                            </div>
                        ) : conversationsError ? (
                            <div className="text-center py-8">
                                <p className="text-red-400 text-sm">{conversationsError}</p>
                                <button 
                                    onClick={() => window.location.reload()}
                                    className="text-indigo-400 text-sm mt-2 hover:underline"
                                >
                                    Retry
                                </button>
                            </div>
                        ) : conversations.length === 0 ? (
                            <div className="text-center py-8">
                                <div className="w-16 h-16 mx-auto mb-4 bg-white/5 rounded-2xl flex items-center justify-center">
                                    <span className="text-3xl">💬</span>
                                </div>
                                <p className="text-slate-500 text-sm">No conversations yet</p>
                                <Link href="?tab=chat" className="text-indigo-400 text-sm mt-2 inline-block hover:underline">Start your first chat →</Link>
                            </div>
                        ) : (
                            conversations.slice(0, 5).map((conv) => (
                                <Link
                                    key={conv.id}
                                    href={`?tab=chat&conversation=${conv.id}`}
                                    className="block p-3 bg-white/5 hover:bg-white/10 rounded-xl transition-colors"
                                >
                                    <div className="flex items-start justify-between">
                                        <div className="flex-1 min-w-0">
                                            <p className="text-white text-sm truncate">{conv.preview || 'New conversation'}</p>
                                            <p className="text-slate-500 text-xs mt-1">{conv.message_count} messages</p>
                                        </div>
                                        <span className="text-slate-600 text-xs shrink-0 ml-2">
                                            {formatTimeAgo(conv.updated_at || conv.created_at)}
                                        </span>
                                    </div>
                                </Link>
                            ))
                        )}
                    </div>
                </div>

                {/* Knowledge Health */}
                <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-semibold text-white">Knowledge Health</h3>
                        <Link href="?tab=knowledge" className="text-sm text-indigo-400 hover:text-indigo-300">Manage</Link>
                    </div>

                    {/* Progress Ring */}
                    <div className="flex items-center gap-6">
                        <div className="relative w-24 h-24">
                            <svg className="w-24 h-24 transform -rotate-90">
                                <circle
                                    cx="48"
                                    cy="48"
                                    r="40"
                                    stroke="currentColor"
                                    strokeWidth="8"
                                    fill="none"
                                    className="text-white/10"
                                />
                                <circle
                                    cx="48"
                                    cy="48"
                                    r="40"
                                    stroke="url(#gradient)"
                                    strokeWidth="8"
                                    fill="none"
                                    strokeDasharray={`${(defaultStats.indexedSources / Math.max(defaultStats.totalSources, 1)) * 251} 251`}
                                    strokeLinecap="round"
                                />
                                <defs>
                                    <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                                        <stop offset="0%" stopColor="#6366f1" />
                                        <stop offset="100%" stopColor="#a855f7" />
                                    </linearGradient>
                                </defs>
                            </svg>
                            <div className="absolute inset-0 flex items-center justify-center">
                                <span className="text-lg font-bold text-white">
                                    {defaultStats.totalSources > 0
                                        ? Math.round((defaultStats.indexedSources / defaultStats.totalSources) * 100)
                                        : 0}%
                                </span>
                            </div>
                        </div>

                        <div className="space-y-2">
                            <div className="flex items-center gap-2">
                                <span className="w-3 h-3 rounded-full bg-emerald-500" />
                                <span className="text-sm text-slate-300">{defaultStats.indexedSources} Indexed</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="w-3 h-3 rounded-full bg-amber-500" />
                                <span className="text-sm text-slate-300">{defaultStats.processingSources} Processing</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="w-3 h-3 rounded-full bg-slate-500" />
                                <span className="text-sm text-slate-300">{defaultStats.totalSources - defaultStats.indexedSources - defaultStats.processingSources} Other</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default OverviewTab;
