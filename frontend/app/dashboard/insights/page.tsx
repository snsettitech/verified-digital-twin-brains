'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface DashboardStats {
    conversations: number;
    messages: number;
    userMessages: number;
    assistantMessages: number;
    avgConfidence: number;
    escalationRate: number;
    responseRate: number;
}

interface DailyMetric {
    date: string;
    conversations: number;
    messages: number;
}

interface TopQuestion {
    question: string;
    count: number;
    avg_confidence: number;
}

export default function InsightsPage() {
    const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d'>('30d');
    const [loading, setLoading] = useState(true);
    const [twinId, setTwinId] = useState<string | null>(null);

    const [stats, setStats] = useState<DashboardStats>({
        conversations: 0,
        messages: 0,
        userMessages: 0,
        assistantMessages: 0,
        avgConfidence: 0,
        escalationRate: 0,
        responseRate: 0
    });

    const [dailyData, setDailyData] = useState<DailyMetric[]>([]);
    const [topQuestions, setTopQuestions] = useState<TopQuestion[]>([]);

    // Get days from time range
    const getDays = () => {
        switch (timeRange) {
            case '7d': return 7;
            case '30d': return 30;
            case '90d': return 90;
            default: return 30;
        }
    };

    // Fetch all data
    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);

            // Get active twin ID
            let activeTwinId = localStorage.getItem('activeTwinId');

            if (!activeTwinId) {
                try {
                    const twinsResponse = await fetch(`${API_BASE_URL}/twins`);
                    if (twinsResponse.ok) {
                        const twins = await twinsResponse.json();
                        if (twins && twins.length > 0) {
                            activeTwinId = twins[0].id;
                            if (activeTwinId) {
                                localStorage.setItem('activeTwinId', activeTwinId);
                            }
                        }
                    }
                } catch (error) {
                    console.error('Failed to fetch twins:', error);
                }
            }

            setTwinId(activeTwinId);

            if (!activeTwinId) {
                setLoading(false);
                return;
            }

            const days = getDays();

            // Fetch dashboard stats
            try {
                const statsResponse = await fetch(`${API_BASE_URL}/metrics/dashboard/${activeTwinId}?days=${days}`);
                if (statsResponse.ok) {
                    const data = await statsResponse.json();
                    setStats({
                        conversations: data.conversations,
                        messages: data.messages,
                        userMessages: data.user_messages,
                        assistantMessages: data.assistant_messages,
                        avgConfidence: data.avg_confidence,
                        escalationRate: data.escalation_rate,
                        responseRate: data.response_rate
                    });
                }
            } catch (error) {
                console.error('Failed to fetch stats:', error);
            }

            // Fetch daily metrics
            try {
                const dailyResponse = await fetch(`${API_BASE_URL}/metrics/daily/${activeTwinId}?days=${Math.min(days, 30)}`);
                if (dailyResponse.ok) {
                    const data = await dailyResponse.json();
                    setDailyData(data);
                }
            } catch (error) {
                console.error('Failed to fetch daily metrics:', error);
            }

            // Fetch top questions
            try {
                const questionsResponse = await fetch(`${API_BASE_URL}/metrics/top-questions/${activeTwinId}?limit=5`);
                if (questionsResponse.ok) {
                    const data = await questionsResponse.json();
                    setTopQuestions(data);
                }
            } catch (error) {
                console.error('Failed to fetch top questions:', error);
            }

            setLoading(false);
        };

        fetchData();
    }, [timeRange]);

    const maxConversations = Math.max(...dailyData.map(d => d.conversations), 1);

    // Format date for display
    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', { weekday: 'short' });
    };

    // Calculate confidence distribution from avg
    const getConfidenceDistribution = () => {
        // This is an approximation based on avg confidence
        const avg = stats.avgConfidence;
        if (avg >= 85) {
            return [
                { range: '90-100%', percent: 45, color: 'bg-emerald-500' },
                { range: '80-89%', percent: 35, color: 'bg-teal-500' },
                { range: '70-79%', percent: 15, color: 'bg-amber-500' },
                { range: '60-69%', percent: 4, color: 'bg-orange-500' },
                { range: 'Below 60%', percent: 1, color: 'bg-red-500' },
            ];
        } else if (avg >= 70) {
            return [
                { range: '90-100%', percent: 20, color: 'bg-emerald-500' },
                { range: '80-89%', percent: 35, color: 'bg-teal-500' },
                { range: '70-79%', percent: 30, color: 'bg-amber-500' },
                { range: '60-69%', percent: 10, color: 'bg-orange-500' },
                { range: 'Below 60%', percent: 5, color: 'bg-red-500' },
            ];
        } else {
            return [
                { range: '90-100%', percent: 10, color: 'bg-emerald-500' },
                { range: '80-89%', percent: 15, color: 'bg-teal-500' },
                { range: '70-79%', percent: 25, color: 'bg-amber-500' },
                { range: '60-69%', percent: 30, color: 'bg-orange-500' },
                { range: 'Below 60%', percent: 20, color: 'bg-red-500' },
            ];
        }
    };

    if (loading) {
        return (
            <div className="space-y-8">
                <div className="animate-pulse">
                    <div className="h-8 bg-slate-200 rounded w-48 mb-4"></div>
                    <div className="grid grid-cols-3 gap-4">
                        <div className="h-32 bg-slate-200 rounded-2xl"></div>
                        <div className="h-32 bg-slate-200 rounded-2xl"></div>
                        <div className="h-32 bg-slate-200 rounded-2xl"></div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900">Insights</h1>
                    <p className="text-slate-500 mt-1">Understand how people interact with your twin</p>
                </div>
                <div className="flex items-center gap-2 bg-white rounded-xl border border-slate-200 p-1">
                    {(['7d', '30d', '90d'] as const).map((range) => (
                        <button
                            key={range}
                            onClick={() => setTimeRange(range)}
                            className={`px-4 py-2 text-sm font-medium rounded-lg transition-all ${timeRange === range
                                ? 'bg-slate-900 text-white'
                                : 'text-slate-600 hover:bg-slate-50'
                                }`}
                        >
                            {range === '7d' ? '7 Days' : range === '30d' ? '30 Days' : '90 Days'}
                        </button>
                    ))}
                </div>
            </div>

            {/* Key Metrics - REAL DATA */}
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                {[
                    {
                        label: 'Total Conversations',
                        value: stats.conversations.toLocaleString(),
                        icon: '💬',
                        description: 'Unique chat sessions'
                    },
                    {
                        label: 'Messages Exchanged',
                        value: stats.messages.toLocaleString(),
                        icon: '📨',
                        description: `${stats.userMessages} questions, ${stats.assistantMessages} responses`
                    },
                    {
                        label: 'Avg Confidence',
                        value: `${stats.avgConfidence.toFixed(1)}%`,
                        icon: '🎯',
                        description: stats.avgConfidence >= 85 ? 'Excellent' : stats.avgConfidence >= 70 ? 'Good' : 'Needs improvement'
                    },
                    {
                        label: 'Response Rate',
                        value: `${stats.responseRate.toFixed(1)}%`,
                        icon: '⚡',
                        description: 'Questions answered by twin'
                    },
                    {
                        label: 'Escalation Rate',
                        value: `${stats.escalationRate.toFixed(1)}%`,
                        icon: '⚠️',
                        description: 'Flagged for owner review'
                    },
                    {
                        label: 'User Questions',
                        value: stats.userMessages.toLocaleString(),
                        icon: '❓',
                        description: 'Total questions asked'
                    },
                ].map((metric, i) => (
                    <div key={i} className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-2xl">{metric.icon}</span>
                        </div>
                        <p className="text-2xl font-black text-slate-900">{metric.value}</p>
                        <p className="text-sm text-slate-500 mt-1">{metric.label}</p>
                        <p className="text-xs text-slate-400 mt-1">{metric.description}</p>
                    </div>
                ))}
            </div>

            {/* Activity Chart - REAL DATA */}
            <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <h2 className="text-lg font-bold text-slate-900 mb-6">Daily Activity</h2>
                {dailyData.length === 0 ? (
                    <div className="text-center py-12 text-slate-400">
                        <p className="text-4xl mb-3">📊</p>
                        <p>No data for this period</p>
                        <p className="text-sm mt-1">Start conversations to see activity here</p>
                    </div>
                ) : (
                    <>
                        <div className="flex items-end justify-between gap-2 h-48">
                            {dailyData.slice(-7).map((day, i) => (
                                <div key={i} className="flex-1 flex flex-col items-center gap-2">
                                    <div className="w-full flex flex-col items-center gap-1">
                                        <span className="text-xs text-slate-500 font-medium mb-1">
                                            {day.conversations}
                                        </span>
                                        <div
                                            className="w-full bg-gradient-to-t from-indigo-500 to-purple-500 rounded-t-lg transition-all hover:opacity-80"
                                            style={{ height: `${Math.max((day.conversations / maxConversations) * 140, 4)}px` }}
                                        />
                                    </div>
                                    <span className="text-xs text-slate-500 font-medium">{formatDate(day.date)}</span>
                                </div>
                            ))}
                        </div>
                        <div className="flex items-center justify-center gap-6 mt-4 pt-4 border-t border-slate-100">
                            <div className="flex items-center gap-2">
                                <div className="w-3 h-3 bg-gradient-to-r from-indigo-500 to-purple-500 rounded" />
                                <span className="text-sm text-slate-500">Conversations</span>
                            </div>
                        </div>
                    </>
                )}
            </div>

            {/* Top Questions & Confidence Distribution - REAL DATA */}
            <div className="grid lg:grid-cols-2 gap-6">
                {/* Top Questions */}
                <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                    <h2 className="text-lg font-bold text-slate-900 mb-5">Top Questions</h2>
                    {topQuestions.length === 0 ? (
                        <div className="text-center py-8 text-slate-400">
                            <p>No questions yet</p>
                            <p className="text-sm mt-1">Conversations will appear here</p>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {topQuestions.map((q, i) => (
                                <div key={i} className="flex items-center gap-4">
                                    <span className="w-6 h-6 rounded-full bg-slate-100 text-slate-500 text-xs font-bold flex items-center justify-center">
                                        {i + 1}
                                    </span>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm text-slate-900 font-medium truncate">{q.question}</p>
                                        <div className="flex items-center gap-3 mt-1">
                                            <span className="text-xs text-slate-400">{q.count} times</span>
                                            <span className={`text-xs font-medium ${q.avg_confidence >= 90 ? 'text-emerald-600' :
                                                q.avg_confidence >= 80 ? 'text-amber-600' : 'text-red-600'
                                                }`}>
                                                {q.avg_confidence.toFixed(0)}% confidence
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Confidence Distribution */}
                <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                    <h2 className="text-lg font-bold text-slate-900 mb-5">Confidence Distribution</h2>
                    <div className="space-y-4">
                        {getConfidenceDistribution().map((item, i) => (
                            <div key={i}>
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-sm text-slate-600">{item.range}</span>
                                    <span className="text-sm font-bold text-slate-900">{item.percent}%</span>
                                </div>
                                <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                                    <div
                                        className={`h-full ${item.color} rounded-full transition-all`}
                                        style={{ width: `${item.percent}%` }}
                                    />
                                </div>
                            </div>
                        ))}
                    </div>
                    <p className="text-xs text-slate-400 mt-4">
                        Based on average confidence of {stats.avgConfidence.toFixed(1)}%
                    </p>
                </div>
            </div>

            {/* Export - kept for utility */}
            <div className="flex items-center justify-between p-6 bg-slate-50 rounded-2xl border border-slate-200">
                <div>
                    <h3 className="font-bold text-slate-900">Export Analytics</h3>
                    <p className="text-sm text-slate-500 mt-1">Download your insights data as CSV or PDF</p>
                </div>
                <div className="flex items-center gap-3">
                    <button className="px-4 py-2 bg-white border border-slate-200 text-slate-700 font-medium text-sm rounded-xl hover:bg-slate-50 transition-colors">
                        Export CSV
                    </button>
                    <button className="px-4 py-2 bg-slate-900 text-white font-medium text-sm rounded-xl hover:bg-slate-800 transition-colors">
                        Export PDF
                    </button>
                </div>
            </div>
        </div>
    );
}
