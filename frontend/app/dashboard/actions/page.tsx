'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { Card, CardHeader, CardContent, Badge, useToast } from '@/components/ui';
import { useTwin } from '@/lib/context/TwinContext';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';

interface ActionStats {
    pending_drafts: number;
    active_triggers: number;
    total_executions: number;
    success_rate: number;
    connectors_count: number;
}

interface RecentExecution {
    id: string;
    action_type: string;
    status: string;
    executed_at: string;
}

interface PendingDraft {
    id: string;
    proposed_action: {
        action_type: string;
    };
    context: {
        trigger_name: string;
        user_message?: string;
    };
    created_at: string;
}

export default function ActionsPage() {
    const { showToast } = useToast();
    const { activeTwin, isLoading: twinLoading } = useTwin();
    const { get } = useAuthFetch();
    const [stats, setStats] = useState<ActionStats>({
        pending_drafts: 0,
        active_triggers: 0,
        total_executions: 0,
        success_rate: 0,
        connectors_count: 0
    });
    const [recentExecutions, setRecentExecutions] = useState<RecentExecution[]>([]);
    const [pendingDrafts, setPendingDrafts] = useState<PendingDraft[]>([]);
    const [loading, setLoading] = useState(true);

    const twinId = activeTwin?.id;

    const fetchData = useCallback(async () => {
        if (!twinId) return;
        try {
            const [triggersRes, execsRes, draftsRes, connectorsRes] = await Promise.all([
                get(`/twins/${twinId}/triggers`),
                get(`/twins/${twinId}/executions?limit=5`),
                get(`/twins/${twinId}/action-drafts`),
                get(`/twins/${twinId}/connectors`)
            ]);

            const triggers = triggersRes.ok ? await triggersRes.json() : [];
            const executions = execsRes.ok ? await execsRes.json() : [];
            const drafts = draftsRes.ok ? await draftsRes.json() : [];
            const connectors = connectorsRes.ok ? await connectorsRes.json() : [];

            const successCount = executions.filter((e: any) => e.status === 'success').length;

            setStats({
                pending_drafts: drafts.length,
                active_triggers: triggers.filter((t: any) => t.is_active).length,
                total_executions: executions.length,
                success_rate: executions.length > 0 ? Math.round((successCount / executions.length) * 100) : 100,
                connectors_count: connectors.length
            });

            setRecentExecutions(executions.slice(0, 5));
            setPendingDrafts(drafts.slice(0, 3));
        } catch (err) {
            console.error('Fetch error:', err);
        } finally {
            setLoading(false);
        }
    }, [twinId, get]);

    useEffect(() => {
        if (twinId) {
            fetchData();
        } else if (!twinLoading) {
            setLoading(false);
        }
    }, [twinId, twinLoading, fetchData]);

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'success': return 'bg-emerald-500';
            case 'failed': return 'bg-rose-500';
            case 'pending': return 'bg-amber-500';
            default: return 'bg-slate-500';
        }
    };

    const getActionIcon = (type: string) => {
        switch (type) {
            case 'draft_email': return '📧';
            case 'draft_calendar_event': return '📅';
            case 'notify_owner': return '🔔';
            case 'escalate': return '⚠️';
            case 'webhook': return '🔗';
            default: return '⚡';
        }
    };

    if (twinLoading) {
        return (
            <div className="flex justify-center p-20">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600"></div>
            </div>
        );
    }

    if (!twinId) {
        return (
            <div className="flex items-center justify-center h-96">
                <div className="text-center max-w-md p-8">
                    <div className="w-16 h-16 bg-indigo-900/50 rounded-2xl flex items-center justify-center mx-auto mb-6">
                        <svg className="w-8 h-8 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                    </div>
                    <h2 className="text-2xl font-bold text-white mb-3">No Twin Found</h2>
                    <p className="text-slate-400 mb-6">Create a digital twin first to access the Actions Hub.</p>
                    <a href="/dashboard/right-brain" className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition-colors">
                        Create Your Twin
                    </a>
                </div>
            </div>
        );
    }

    return (
        <div className="max-w-6xl mx-auto space-y-8 pb-20">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-4xl font-black tracking-tight text-white mb-2">Actions Hub</h1>
                    <p className="text-slate-400 font-medium">Automate workflows with intelligent triggers and approval-based execution.</p>
                </div>
                <div className="flex gap-3">
                    <Link
                        href="/dashboard/actions/connectors"
                        className="px-5 py-2.5 bg-white/5 hover:bg-white/10 text-white rounded-xl text-sm font-bold transition-all border border-white/10"
                    >
                        🔌 Connectors
                    </Link>
                    <Link
                        href="/dashboard/actions/triggers"
                        className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-black transition-all shadow-lg shadow-indigo-500/20"
                    >
                        + New Trigger
                    </Link>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                <Card glass className="p-5">
                    <div className="text-3xl font-black text-white">{stats.pending_drafts}</div>
                    <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mt-1">Pending Approvals</div>
                    {stats.pending_drafts > 0 && (
                        <div className="mt-2">
                            <span className="px-2 py-0.5 bg-amber-500/20 text-amber-400 text-[10px] font-black rounded-lg">
                                Action Required
                            </span>
                        </div>
                    )}
                </Card>
                <Card glass className="p-5">
                    <div className="text-3xl font-black text-white">{stats.active_triggers}</div>
                    <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mt-1">Active Triggers</div>
                </Card>
                <Card glass className="p-5">
                    <div className="text-3xl font-black text-white">{stats.total_executions}</div>
                    <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mt-1">Total Executions</div>
                </Card>
                <Card glass className="p-5">
                    <div className="text-3xl font-black text-emerald-400">{stats.success_rate}%</div>
                    <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mt-1">Success Rate</div>
                </Card>
                <Card glass className="p-5">
                    <div className="text-3xl font-black text-white">{stats.connectors_count}</div>
                    <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mt-1">Connectors</div>
                </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Pending Approvals */}
                <Card glass>
                    <CardHeader className="flex flex-row items-center justify-between border-b border-white/5">
                        <div className="flex items-center gap-3">
                            <h3 className="text-lg font-black text-white">Pending Approvals</h3>
                            {stats.pending_drafts > 0 && (
                                <span className="px-2 py-0.5 bg-amber-500/20 text-amber-400 text-[10px] font-black rounded-lg animate-pulse">
                                    {stats.pending_drafts}
                                </span>
                            )}
                        </div>
                        <Link href="/dashboard/actions/inbox" className="text-sm font-bold text-indigo-400 hover:text-indigo-300 transition-colors">
                            View All →
                        </Link>
                    </CardHeader>
                    <CardContent className="p-0">
                        {pendingDrafts.length === 0 ? (
                            <div className="p-10 text-center">
                                <div className="text-4xl mb-3">✅</div>
                                <p className="text-slate-500 text-sm font-medium">No pending approvals</p>
                                <p className="text-slate-600 text-xs mt-1">Actions will appear here when triggers match</p>
                            </div>
                        ) : (
                            <div className="divide-y divide-white/5">
                                {pendingDrafts.map((draft) => (
                                    <div key={draft.id} className="p-4 hover:bg-white/5 transition-colors">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-3">
                                                <span className="text-xl">{getActionIcon(draft.proposed_action.action_type)}</span>
                                                <div>
                                                    <div className="text-sm font-bold text-white">{draft.context.trigger_name || 'Triggered Action'}</div>
                                                    <div className="text-xs text-slate-500 mt-0.5 truncate max-w-[200px]">
                                                        {draft.context.user_message || draft.proposed_action.action_type}
                                                    </div>
                                                </div>
                                            </div>
                                            <Link
                                                href={`/dashboard/actions/inbox`}
                                                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-black transition-all"
                                            >
                                                Review
                                            </Link>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Recent Activity */}
                <Card glass>
                    <CardHeader className="flex flex-row items-center justify-between border-b border-white/5">
                        <h3 className="text-lg font-black text-white">Recent Executions</h3>
                        <Link href="/dashboard/actions/history" className="text-sm font-bold text-indigo-400 hover:text-indigo-300 transition-colors">
                            View All →
                        </Link>
                    </CardHeader>
                    <CardContent className="p-0">
                        {recentExecutions.length === 0 ? (
                            <div className="p-10 text-center">
                                <div className="text-4xl mb-3">📊</div>
                                <p className="text-slate-500 text-sm font-medium">No executions yet</p>
                                <p className="text-slate-600 text-xs mt-1">Executed actions will appear here</p>
                            </div>
                        ) : (
                            <div className="divide-y divide-white/5">
                                {recentExecutions.map((exec) => (
                                    <div key={exec.id} className="p-4 hover:bg-white/5 transition-colors">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-3">
                                                <span className="text-xl">{getActionIcon(exec.action_type)}</span>
                                                <div>
                                                    <div className="text-sm font-bold text-white capitalize">
                                                        {exec.action_type.replace(/_/g, ' ')}
                                                    </div>
                                                    <div className="text-xs text-slate-500 mt-0.5">
                                                        {new Date(exec.executed_at).toLocaleString()}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className={`w-2 h-2 rounded-full ${getStatusColor(exec.status)}`}></div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Quick Actions */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
                <Link href="/dashboard/actions/triggers" className="group">
                    <Card glass className="p-5 hover:border-indigo-500/30 transition-all cursor-pointer">
                        <div className="flex items-center gap-4">
                            <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 flex items-center justify-center text-2xl group-hover:scale-110 transition-transform">
                                ⚡
                            </div>
                            <div>
                                <div className="font-bold text-white">Manage Triggers</div>
                                <div className="text-xs text-slate-500">Create automation rules</div>
                            </div>
                        </div>
                    </Card>
                </Link>
                <Link href="/dashboard/actions/inbox" className="group">
                    <Card glass className="p-5 hover:border-amber-500/30 transition-all cursor-pointer">
                        <div className="flex items-center gap-4">
                            <div className="w-12 h-12 rounded-2xl bg-amber-500/10 flex items-center justify-center text-2xl group-hover:scale-110 transition-transform">
                                📥
                            </div>
                            <div>
                                <div className="font-bold text-white">Approval Inbox</div>
                                <div className="text-xs text-slate-500">Review pending actions</div>
                            </div>
                        </div>
                    </Card>
                </Link>
                <Link href="/dashboard/actions/history" className="group">
                    <Card glass className="p-5 hover:border-emerald-500/30 transition-all cursor-pointer">
                        <div className="flex items-center gap-4">
                            <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 flex items-center justify-center text-2xl group-hover:scale-110 transition-transform">
                                📜
                            </div>
                            <div>
                                <div className="font-bold text-white">Execution History</div>
                                <div className="text-xs text-slate-500">View completed actions</div>
                            </div>
                        </div>
                    </Card>
                </Link>
                <Link href="/dashboard/actions/connectors" className="group">
                    <Card glass className="p-5 hover:border-purple-500/30 transition-all cursor-pointer">
                        <div className="flex items-center gap-4">
                            <div className="w-12 h-12 rounded-2xl bg-purple-500/10 flex items-center justify-center text-2xl group-hover:scale-110 transition-transform">
                                🔌
                            </div>
                            <div>
                                <div className="font-bold text-white">Connectors</div>
                                <div className="text-xs text-slate-500">Connect external tools</div>
                            </div>
                        </div>
                    </Card>
                </Link>
            </div>
        </div>
    );
}
