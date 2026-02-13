'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';

interface GraphNode {
    name: string;
    type: string;
    description: string;
}

interface GraphStats {
    node_count: number;
    has_graph: boolean;
    intent_count: number;
    profile_count: number;
    top_nodes: GraphNode[];
}

import { API_BASE_URL, API_ENDPOINTS } from '@/lib/constants';

interface GraphContextProps {
    twinId: string;
    compact?: boolean;
}

export default function GraphContext({ twinId, compact = false }: GraphContextProps) {
    const [stats, setStats] = useState<GraphStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [expanded, setExpanded] = useState(false);

    const fetchGraphStats = useCallback(async () => {
        try {
            setLoading(true);
            const supabase = getSupabaseClient();
            const { data: { session } } = await supabase.auth.getSession();

            if (!session) return;

            const response = await fetch(`${API_BASE_URL}${API_ENDPOINTS.TWIN_GRAPH_STATS(twinId)}`, {
                headers: {
                    'Authorization': `Bearer ${session.access_token}`
                }
            });

            if (response.ok) {
                const data = await response.json();
                setStats(data);
            }
        } catch (err) {
            console.error('Error fetching graph stats:', err);
        } finally {
            setLoading(false);
        }
    }, [twinId]);

    useEffect(() => {
        if (twinId) {
            fetchGraphStats();
        }
    }, [twinId, fetchGraphStats]);

    if (loading) {
        return (
            <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-xl p-4 mb-4 animate-pulse">
                <div className="h-5 bg-indigo-200 rounded w-1/3"></div>
            </div>
        );
    }

    if (!stats || !stats.has_graph) {
        return (
            <div className="bg-slate-50 rounded-xl p-4 mb-4 border border-slate-200">
                <div className="flex items-center gap-2 text-slate-500">
                    <span className="text-lg">🧠</span>
                    <span className="text-sm">No interview data yet. Complete the Right Brain interview to improve your twin responses.</span>
                </div>
            </div>
        );
    }

    if (compact) {
        return (
            <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-lg px-3 py-2 flex items-center gap-2">
                <span className="text-lg">🧠</span>
                <span className="text-sm font-medium text-indigo-700">
                    {stats.node_count} memories
                </span>
            </div>
        );
    }

    return (
        <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-xl p-4 mb-4 border border-indigo-100">
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full flex items-center justify-between text-left"
            >
                <div className="flex items-center gap-3">
                    <span className="text-2xl">🧠</span>
                    <div>
                        <h3 className="font-semibold text-indigo-900">
                            Twin&apos;s Memory
                        </h3>
                        <p className="text-sm text-indigo-600">
                            {stats.node_count} items from interview
                        </p>
                    </div>
                </div>
                <span className={`text-indigo-500 transition-transform ${expanded ? 'rotate-180' : ''}`}>
                    ▼
                </span>
            </button>

            {expanded && (
                <div className="mt-4 space-y-2">
                    {stats.top_nodes.map((node, index) => (
                        <div
                            key={index}
                            className="bg-white/70 rounded-lg px-3 py-2 border border-indigo-100"
                        >
                            <div className="flex items-start gap-2">
                                <span className="text-indigo-500 mt-0.5">✦</span>
                                <div>
                                    <span className="font-medium text-slate-800">{node.name}</span>
                                    <span className="text-xs text-slate-500 ml-2">({node.type})</span>
                                    <p className="text-sm text-slate-600 mt-0.5">{node.description}</p>
                                </div>
                            </div>
                        </div>
                    ))}

                    {stats.node_count > stats.top_nodes.length && (
                        <p className="text-xs text-indigo-500 text-center pt-2">
                            + {stats.node_count - stats.top_nodes.length} more items
                        </p>
                    )}
                </div>
            )}
        </div>
    );
}

// Badge component for individual messages
export function GraphUsedBadge({ graphUsed }: { graphUsed: boolean }) {
    if (!graphUsed) return null;

    return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-indigo-100 text-indigo-700 text-xs rounded-full">
            <span>💡</span>
            <span>From your interview</span>
        </span>
    );
}
