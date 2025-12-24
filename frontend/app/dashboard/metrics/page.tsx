'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTwin } from '@/lib/context/TwinContext';
import { getSupabaseClient } from '@/lib/supabase/client';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface MetricsSummary {
    total_requests: number;
    total_tokens: number;
    avg_latency_ms: number;
    error_count: number;
    error_rate: number;
    period_days: number;
}

interface ServiceHealth {
    status: string;
    response_ms?: number;
    error?: string;
    vector_count?: number;
    note?: string;
}

interface HealthStatus {
    status: string;
    timestamp: string;
    services: {
        supabase?: ServiceHealth;
        pinecone?: ServiceHealth;
        openai?: ServiceHealth;
    };
}

interface QuotaInfo {
    quota_type: string;
    limit: number;
    current_usage: number;
    remaining: number;
    percent_used: number;
}

export default function MetricsDashboard() {
    const { activeTwin, user } = useTwin();
    const [loading, setLoading] = useState(true);
    const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
    const [health, setHealth] = useState<HealthStatus | null>(null);
    const [quotas, setQuotas] = useState<QuotaInfo[]>([]);
    const [error, setError] = useState<string | null>(null);

    const supabase = getSupabaseClient();

    const getAuthToken = useCallback(async (): Promise<string | null> => {
        const { data: { session } } = await supabase.auth.getSession();
        return session?.access_token || null;
    }, [supabase]);

    const fetchData = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);

            const token = await getAuthToken();
            if (!token) {
                setError('Not authenticated');
                return;
            }

            const headers = {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            };

            // Fetch metrics summary
            if (activeTwin?.id) {
                const metricsRes = await fetch(`${API_BASE_URL}/metrics/usage/${activeTwin.id}?days=7`, { headers });
                if (metricsRes.ok) {
                    setMetrics(await metricsRes.json());
                }
            }

            // Fetch health status
            const healthRes = await fetch(`${API_BASE_URL}/metrics/health`, { headers });
            if (healthRes.ok) {
                setHealth(await healthRes.json());
            }

            // Fetch quotas (if user has tenant)
            if (user?.tenant_id) {
                const quotaRes = await fetch(`${API_BASE_URL}/metrics/quota/${user.tenant_id}`, { headers });
                if (quotaRes.ok) {
                    const data = await quotaRes.json();
                    setQuotas(data.quotas || []);
                }
            }

        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    }, [activeTwin, user, getAuthToken]);

    useEffect(() => {
        fetchData();
        // Refresh every 30 seconds
        const interval = setInterval(fetchData, 30000);
        return () => clearInterval(interval);
    }, [fetchData]);

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'healthy':
            case 'configured':
                return 'bg-green-500';
            case 'degraded':
                return 'bg-yellow-500';
            case 'unhealthy':
            case 'unconfigured':
                return 'bg-red-500';
            default:
                return 'bg-gray-400';
        }
    };

    const getStatusBadge = (status: string) => {
        const color = getStatusColor(status);
        return (
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${color} text-white`}>
                {status}
            </span>
        );
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-8">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <div className="mb-8">
                    <h1 className="text-3xl font-bold text-gray-900">System Metrics</h1>
                    <p className="text-gray-500 mt-1">Monitor performance, usage, and system health</p>
                </div>

                {error && (
                    <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                        {error}
                    </div>
                )}

                {/* Service Health Status */}
                <div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-semibold text-gray-800">Service Health</h2>
                        {health && (
                            <div className="flex items-center gap-2">
                                <div className={`w-3 h-3 rounded-full ${getStatusColor(health.status)} animate-pulse`}></div>
                                <span className="text-sm font-medium text-gray-600 capitalize">{health.status}</span>
                            </div>
                        )}
                    </div>

                    {loading && !health ? (
                        <div className="animate-pulse space-y-3">
                            {[1, 2, 3].map(i => (
                                <div key={i} className="h-16 bg-gray-200 rounded-lg"></div>
                            ))}
                        </div>
                    ) : health ? (
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {/* Supabase */}
                            <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="font-medium text-gray-700">Supabase</span>
                                    {getStatusBadge(health.services.supabase?.status || 'unknown')}
                                </div>
                                {health.services.supabase?.response_ms && (
                                    <p className="text-sm text-gray-500">
                                        Response: {health.services.supabase.response_ms.toFixed(0)}ms
                                    </p>
                                )}
                            </div>

                            {/* Pinecone */}
                            <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="font-medium text-gray-700">Pinecone</span>
                                    {getStatusBadge(health.services.pinecone?.status || 'unknown')}
                                </div>
                                {health.services.pinecone?.vector_count !== undefined && (
                                    <p className="text-sm text-gray-500">
                                        Vectors: {health.services.pinecone.vector_count.toLocaleString()}
                                    </p>
                                )}
                            </div>

                            {/* OpenAI */}
                            <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="font-medium text-gray-700">OpenAI</span>
                                    {getStatusBadge(health.services.openai?.status || 'unknown')}
                                </div>
                                {health.services.openai?.note && (
                                    <p className="text-sm text-gray-500 truncate" title={health.services.openai.note}>
                                        {health.services.openai.note}
                                    </p>
                                )}
                            </div>
                        </div>
                    ) : (
                        <p className="text-gray-500">Unable to fetch health status</p>
                    )}
                </div>

                {/* Usage Metrics */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
                    <div className="bg-white rounded-2xl shadow-lg p-6">
                        <div className="text-sm font-medium text-gray-500 mb-1">Total Requests</div>
                        <div className="text-3xl font-bold text-gray-900">
                            {loading ? '...' : (metrics?.total_requests || 0).toLocaleString()}
                        </div>
                        <div className="text-xs text-gray-400 mt-1">Last 7 days</div>
                    </div>

                    <div className="bg-white rounded-2xl shadow-lg p-6">
                        <div className="text-sm font-medium text-gray-500 mb-1">Total Tokens</div>
                        <div className="text-3xl font-bold text-indigo-600">
                            {loading ? '...' : (metrics?.total_tokens || 0).toLocaleString()}
                        </div>
                        <div className="text-xs text-gray-400 mt-1">Last 7 days</div>
                    </div>

                    <div className="bg-white rounded-2xl shadow-lg p-6">
                        <div className="text-sm font-medium text-gray-500 mb-1">Avg Latency</div>
                        <div className="text-3xl font-bold text-cyan-600">
                            {loading ? '...' : `${(metrics?.avg_latency_ms || 0).toFixed(0)}ms`}
                        </div>
                        <div className="text-xs text-gray-400 mt-1">Response time</div>
                    </div>

                    <div className="bg-white rounded-2xl shadow-lg p-6">
                        <div className="text-sm font-medium text-gray-500 mb-1">Error Rate</div>
                        <div className={`text-3xl font-bold ${(metrics?.error_rate || 0) > 5 ? 'text-red-600' : 'text-green-600'}`}>
                            {loading ? '...' : `${(metrics?.error_rate || 0).toFixed(1)}%`}
                        </div>
                        <div className="text-xs text-gray-400 mt-1">{metrics?.error_count || 0} errors</div>
                    </div>
                </div>

                {/* Usage Quotas */}
                <div className="bg-white rounded-2xl shadow-lg p-6">
                    <h2 className="text-lg font-semibold text-gray-800 mb-4">Usage Quotas</h2>

                    {quotas.length === 0 ? (
                        <div className="text-gray-500 text-center py-8">
                            <p>No quotas configured for this tenant</p>
                            <p className="text-sm mt-1">Default limits apply (100,000 tokens/day)</p>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {quotas.map((quota, idx) => (
                                <div key={idx} className="bg-gray-50 rounded-xl p-4">
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="font-medium text-gray-700 capitalize">
                                            {quota.quota_type.replace(/_/g, ' ')}
                                        </span>
                                        <span className="text-sm text-gray-500">
                                            {quota.current_usage.toLocaleString()} / {quota.limit.toLocaleString()}
                                        </span>
                                    </div>
                                    <div className="w-full bg-gray-200 rounded-full h-2.5">
                                        <div
                                            className={`h-2.5 rounded-full ${quota.percent_used > 90 ? 'bg-red-500' :
                                                quota.percent_used > 70 ? 'bg-yellow-500' :
                                                    'bg-green-500'
                                                }`}
                                            style={{ width: `${Math.min(quota.percent_used, 100)}%` }}
                                        ></div>
                                    </div>
                                    <div className="flex justify-between mt-1 text-xs text-gray-400">
                                        <span>{quota.percent_used.toFixed(1)}% used</span>
                                        <span>{quota.remaining.toLocaleString()} remaining</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Refresh Button */}
                <div className="mt-6 text-center">
                    <button
                        onClick={fetchData}
                        disabled={loading}
                        className="px-6 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 transition-all"
                    >
                        {loading ? 'Refreshing...' : 'Refresh Data'}
                    </button>
                    <p className="text-xs text-gray-400 mt-2">Auto-refreshes every 30 seconds</p>
                </div>
            </div>
        </div>
    );
}
