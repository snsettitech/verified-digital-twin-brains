'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';

interface MemoryEvent {
    id: string;
    event_type: string;
    payload: {
        nodes_created?: string[];
        edges_created?: string[];
        confidence?: number;
        raw_nodes?: Array<{ name: string; type: string; description: string }>;
    };
    status: string;
    created_at: string;
    summary?: string;
    confidence_display?: string;
}

interface TILFeedProps {
    twinId: string;
}

export default function TILFeed({ twinId }: TILFeedProps) {
    const { get, post, del } = useAuthFetch();
    const [events, setEvents] = useState<MemoryEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchTILFeed = useCallback(async () => {
        if (!twinId) return;

        setLoading(true);
        try {
            const response = await get(`/twins/${twinId}/til`);

            if (!response.ok) throw new Error('Failed to fetch TIL feed');

            const data = await response.json();
            setEvents(data.events || []);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load');
        } finally {
            setLoading(false);
        }
    }, [twinId, get]);

    useEffect(() => {
        fetchTILFeed();
    }, [fetchTILFeed]);

    const handleConfirm = async (nodeId: string) => {
        try {
            const response = await post(`/twins/${twinId}/til/${nodeId}/confirm`, {});

            if (!response.ok) throw new Error('Failed to confirm');

            // Refresh feed
            fetchTILFeed();
        } catch (err) {
            console.error('Confirm error:', err);
        }
    };

    const handleDelete = async (nodeId: string) => {
        if (!confirm('Are you sure you want to delete this memory?')) return;

        try {
            const response = await del(`/twins/${twinId}/til/${nodeId}`);

            if (!response.ok) throw new Error('Failed to delete');

            // Refresh feed
            fetchTILFeed();
        } catch (err) {
            console.error('Delete error:', err);
        }
    };

    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const getEventIcon = (eventType: string) => {
        switch (eventType) {
            case 'auto_extract': return '🧠';
            case 'confirm': return '✓';
            case 'manual_edit': return '✎';
            case 'delete': return '🗑';
            default: return '📝';
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400">
                {error}
            </div>
        );
    }

    if (events.length === 0) {
        return (
            <div className="p-8 text-center text-gray-400">
                <p className="text-xl mb-2">🧠</p>
                <p>No memories learned yet.</p>
                <p className="text-sm mt-1">Start a conversation to build your digital twin&apos;s knowledge!</p>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-white">Today I Learned</h2>
                <button
                    onClick={fetchTILFeed}
                    className="text-sm text-blue-400 hover:text-blue-300"
                >
                    Refresh
                </button>
            </div>

            {events.map((event) => {
                const nodes = event.payload?.raw_nodes || [];
                const confidence = event.payload?.confidence || 0;

                return (
                    <div
                        key={event.id}
                        className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 hover:border-gray-600 transition-colors"
                    >
                        <div className="flex items-start justify-between">
                            <div className="flex items-start gap-3">
                                <span className="text-xl">{getEventIcon(event.event_type)}</span>
                                <div>
                                    <div className="text-sm text-gray-400 mb-1">
                                        {formatDate(event.created_at)}
                                    </div>
                                    <div className="text-white">
                                        {event.summary || `Learned ${nodes.length} new concept(s)`}
                                    </div>

                                    {nodes.length > 0 && (
                                        <div className="mt-2 space-y-1">
                                            {nodes.slice(0, 3).map((node, idx) => (
                                                <div key={idx} className="text-sm text-gray-300">
                                                    <span className="text-blue-400">{node.name}</span>
                                                    <span className="text-gray-500"> ({node.type})</span>
                                                    {node.description && (
                                                        <span className="text-gray-400">: {node.description.slice(0, 50)}...</span>
                                                    )}
                                                </div>
                                            ))}
                                            {nodes.length > 3 && (
                                                <div className="text-xs text-gray-500">
                                                    +{nodes.length - 3} more
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {confidence > 0 && (
                                        <div className="mt-2 text-xs text-gray-500">
                                            Confidence: {Math.round(confidence * 100)}%
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div className="flex gap-2">
                                {event.event_type === 'auto_extract' && nodes[0] && (
                                    <>
                                        <button
                                            onClick={() => handleConfirm(nodes[0].name)}
                                            className="p-1.5 text-green-400 hover:bg-green-500/10 rounded"
                                            title="Confirm"
                                        >
                                            ✓
                                        </button>
                                        <button
                                            onClick={() => handleDelete(nodes[0].name)}
                                            className="p-1.5 text-red-400 hover:bg-red-500/10 rounded"
                                            title="Delete"
                                        >
                                            🗑
                                        </button>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
