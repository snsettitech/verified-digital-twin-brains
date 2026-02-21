'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useTwin, Twin, getOnboardingResumeUrl } from '@/lib/context/TwinContext';
import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';
import { EmptyState, EmptyTwinNoActivity } from '@/components/ui/EmptyState';
import { API_BASE_URL, API_ENDPOINTS } from '@/lib/constants';

interface Stats {
  conversations: number;
  messages: number;
  userMessages: number;
  assistantMessages: number;
  responseRate: number;
  avgConfidence: number;
  escalationRate: number;
}

interface Conversation {
  id: string;
  created_at: string;
  message_count: number;
  last_message: string | null;
  avg_confidence: number;
}

interface ActivityItem {
  id: string;
  type: string;
  title: string;
  description: string;
  time: string;
}

export default function DashboardPage() {
  const [systemStatus, setSystemStatus] = useState<'checking' | 'online' | 'offline' | 'degraded'>('checking');
  const [twinId, setTwinId] = useState<string | null>(null);
  const [stats, setStats] = useState<Stats>({
    conversations: 0,
    messages: 0,
    userMessages: 0,
    assistantMessages: 0,
    responseRate: 0,
    avgConfidence: 0,
    escalationRate: 0
  });
  const [recentActivity, setRecentActivity] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Use TwinContext as single source of truth for active twin
  const { activeTwin, twins, isLoading: twinsLoading } = useTwin();

  // Filter non-active twins for "Continue Setup" section
  const nonActiveTwins = twins.filter(t => t.status && t.status !== 'active');

  // Modal states
  const [showConversationsModal, setShowConversationsModal] = useState(false);
  const [showMessagesModal, setShowMessagesModal] = useState(false);
  const [showAnalysisModal, setShowAnalysisModal] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loadingConversations, setLoadingConversations] = useState(false);

  // Check system health on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}${API_ENDPOINTS.HEALTH}`);
        if (response.ok) {
          const data = await response.json();
          setSystemStatus(data.status === 'online' ? 'online' : 'degraded');
        } else {
          setSystemStatus('offline');
        }
      } catch {
        setSystemStatus('offline');
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  // Format time ago - moved here to fix hoisting issue
  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diffInSeconds < 60) return 'Just now';
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
    return `${Math.floor(diffInSeconds / 86400)}d ago`;
  };

  // Get twin ID and fetch real stats
  // REFACTORED: Now uses activeTwin from TwinContext instead of redundant fetch
  useEffect(() => {
    const fetchData = async () => {
      // Wait for TwinContext to hydrate
      if (twinsLoading) return;

      setLoading(true);
      const currentTwinId = activeTwin?.id || null;
      setTwinId(currentTwinId);

      if (currentTwinId) {
        // Fetch real dashboard stats
        try {
          const statsResponse = await authFetchStandalone(`${API_ENDPOINTS.METRICS_DASHBOARD(currentTwinId)}?days=30`);
          if (statsResponse.ok) {
            const data = await statsResponse.json();
            setStats({
              conversations: data.conversations,
              messages: data.messages,
              userMessages: data.user_messages,
              assistantMessages: data.assistant_messages,
              responseRate: data.response_rate,
              avgConfidence: data.avg_confidence,
              escalationRate: data.escalation_rate
            });
          }
        } catch (error) {
          console.error('Failed to fetch stats:', error);
        }

        // Fetch real activity feed
        try {
          const activityResponse = await authFetchStandalone(`${API_ENDPOINTS.METRICS_ACTIVITY(currentTwinId)}?limit=5`);
          if (activityResponse.ok) {
            const data: ActivityItem[] = await activityResponse.json();
            setRecentActivity(data.map((item) => ({
              id: item.id,
              type: item.type,
              title: item.title,
              description: item.description,
              time: formatTimeAgo(item.time)
            })));
          }
        } catch (error) {
          console.error('Failed to fetch activity:', error);
        }
      }

      setLoading(false);
    };

    fetchData();
  }, [activeTwin?.id, twinsLoading]);



  // Fetch conversations when modal opens
  const handleConversationsClick = async () => {
    setShowConversationsModal(true);
    if (!twinId) return;

    setLoadingConversations(true);
    try {
      const response = await authFetchStandalone(`${API_ENDPOINTS.METRICS_CONVERSATIONS(twinId)}?limit=20`);
      if (response.ok) {
        const data = await response.json();
        setConversations(data);
      }
    } catch (error) {
      console.error('Failed to fetch conversations:', error);
    }
    setLoadingConversations(false);
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-slate-900">Dashboard</h1>
          <p className="text-slate-500 mt-1">Welcome back! Here&apos;s how your twin is performing.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-4 py-2 rounded-full border bg-white shadow-sm">
            <span className={`w-2.5 h-2.5 rounded-full ${systemStatus === 'online' ? 'bg-emerald-500 animate-pulse' :
              systemStatus === 'degraded' ? 'bg-yellow-500' :
                systemStatus === 'offline' ? 'bg-red-500' : 'bg-slate-300 animate-pulse'
              }`} />
            <span className="text-sm font-semibold text-slate-700 capitalize">
              {systemStatus}
            </span>
          </div>
        </div>
      </div>

      {/* Non-Active Twins - Continue Setup */}
      {nonActiveTwins.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-6">
          <h2 className="text-lg font-bold text-amber-900 mb-4 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            Continue Setup ({nonActiveTwins.length})
          </h2>
          <div className="space-y-3">
            {nonActiveTwins.map((twin) => (
              <div 
                key={twin.id}
                className="flex items-center justify-between bg-white rounded-xl p-4 border border-amber-100"
              >
                <div>
                  <p className="font-semibold text-slate-900">{twin.name}</p>
                  <p className="text-sm text-slate-500 capitalize">
                    Status: {twin.status?.replace('_', ' ') || 'Draft'}
                  </p>
                </div>
                <Link 
                  href={getOnboardingResumeUrl(twin.id)}
                  className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  Continue Setup →
                </Link>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stats Cards - CLICKABLE */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Conversations Card */}
        <button
          onClick={handleConversationsClick}
          className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm hover:shadow-md hover:border-indigo-300 transition-all text-left"
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-2xl">💬</span>
            <span className="px-2 py-1 text-[10px] font-bold text-white rounded-full bg-gradient-to-r from-blue-500 to-cyan-500">
              {stats.conversations > 0 ? 'LIVE' : 'NEW'}
            </span>
          </div>
          <p className="text-2xl font-black text-slate-900">{stats.conversations.toLocaleString()}</p>
          <p className="text-sm text-slate-500 mt-1">Conversations</p>
          <p className="text-xs text-indigo-500 mt-2">Click to view →</p>
        </button>

        {/* Messages Card */}
        <button
          onClick={() => setShowMessagesModal(true)}
          className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm hover:shadow-md hover:border-purple-300 transition-all text-left"
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-2xl">📨</span>
            <span className="px-2 py-1 text-[10px] font-bold text-white rounded-full bg-gradient-to-r from-purple-500 to-pink-500">
              TOTAL
            </span>
          </div>
          <p className="text-2xl font-black text-slate-900">{stats.messages.toLocaleString()}</p>
          <p className="text-sm text-slate-500 mt-1">Messages</p>
          <p className="text-xs text-purple-500 mt-2">Click for breakdown →</p>
        </button>

        {/* Response Rate Card */}
        <button
          onClick={() => setShowAnalysisModal(true)}
          className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm hover:shadow-md hover:border-emerald-300 transition-all text-left"
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-2xl">⚡</span>
            <span className={`px-2 py-1 text-[10px] font-bold text-white rounded-full bg-gradient-to-r ${stats.responseRate >= 90 ? 'from-emerald-500 to-teal-500' :
              stats.responseRate >= 70 ? 'from-yellow-500 to-orange-500' :
                'from-red-500 to-pink-500'
              }`}>
              {stats.responseRate >= 90 ? 'GREAT' : stats.responseRate >= 70 ? 'GOOD' : 'LOW'}
            </span>
          </div>
          <p className="text-2xl font-black text-slate-900">{stats.responseRate.toFixed(1)}%</p>
          <p className="text-sm text-slate-500 mt-1">Response Rate</p>
          <p className="text-xs text-emerald-500 mt-2">Click for analysis →</p>
        </button>

        {/* Avg Confidence Card */}
        <button
          onClick={() => setShowAnalysisModal(true)}
          className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm hover:shadow-md hover:border-orange-300 transition-all text-left"
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-2xl">🎯</span>
            <span className={`px-2 py-1 text-[10px] font-bold text-white rounded-full bg-gradient-to-r ${stats.avgConfidence >= 85 ? 'from-emerald-500 to-teal-500' :
              stats.avgConfidence >= 70 ? 'from-yellow-500 to-orange-500' :
                'from-red-500 to-pink-500'
              }`}>
              {stats.avgConfidence >= 85 ? 'HIGH' : stats.avgConfidence >= 70 ? 'MED' : 'LOW'}
            </span>
          </div>
          <p className="text-2xl font-black text-slate-900">{stats.avgConfidence.toFixed(1)}%</p>
          <p className="text-sm text-slate-500 mt-1">Avg Confidence</p>
          <p className="text-xs text-orange-500 mt-2">Click for analysis →</p>
        </button>
      </div>

      {/* Quick Actions */}
      <div className="grid md:grid-cols-3 gap-6">
        {/* Interview Twin - ISSUE-001: Changed from "Train" to "Interview" for clarity */}
        <Link href="/dashboard/interview" className="group">
          <div className="bg-gradient-to-br from-indigo-600 to-purple-700 p-6 rounded-2xl text-white shadow-xl shadow-indigo-200 hover:shadow-2xl transition-all duration-300 h-full relative overflow-hidden">
            <div className="absolute top-0 right-0 p-6 opacity-10">
              <svg className="w-24 h-24" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <h3 className="text-xl font-bold mb-1">Interview Your Twin</h3>
            <p className="text-indigo-100 text-sm opacity-90">Capture your voice and decisions</p>
            <div className="mt-4 inline-block px-3 py-1 bg-white/20 rounded-full text-xs font-bold uppercase tracking-wider">
              Recommended
            </div>
          </div>
        </Link>

        {/* Add Knowledge */}
        <Link href="/dashboard/studio" className="group">
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:shadow-xl transition-all duration-300 h-full">
            <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            <h3 className="text-lg font-bold text-slate-900 mb-1">Add Knowledge</h3>
            <p className="text-slate-500 text-sm">Upload files & URLs</p>
          </div>
        </Link>

        {/* Test Twin */}
        <Link href="/dashboard/simulator" className="group">
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:shadow-xl transition-all duration-300 h-full">
            <div className="w-12 h-12 bg-emerald-50 text-emerald-600 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
            </div>
            <h3 className="text-lg font-bold text-slate-900 mb-1">Test Your Twin</h3>
            <p className="text-slate-500 text-sm">Chat in simulator</p>
          </div>
        </Link>
      </div>

      {/* Activity & Quick Links Row */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Recent Activity - REAL DATA */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-bold text-slate-900">Recent Activity</h2>
            <Link href="/dashboard/insights" className="text-sm text-indigo-600 hover:text-indigo-700 font-medium">
              View All →
            </Link>
          </div>
          <div className="space-y-4">
            {loading ? (
              <div className="text-center py-8 text-slate-400">Loading activity...</div>
            ) : recentActivity.length === 0 ? (
              activeTwin?.name ? (
                <EmptyTwinNoActivity twinName={activeTwin.name} />
              ) : (
                <EmptyState
                  illustration="chat-bubble"
                  title="No activity yet"
                  description="Start a conversation to see activity here."
                  primaryAction={{
                    label: 'Start Chatting',
                    href: '/dashboard/simulator',
                  }}
                />
              )
            ) : (
              recentActivity.map((activity) => (
                <div key={activity.id} className="flex items-start gap-3 pb-4 border-b border-slate-100 last:border-0 last:pb-0">
                  <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm ${activity.type === 'conversation' ? 'bg-blue-100 text-blue-600' :
                    activity.type === 'escalation' ? 'bg-amber-100 text-amber-600' :
                      'bg-emerald-100 text-emerald-600'
                    }`}>
                    {activity.type === 'conversation' ? '💬' : activity.type === 'escalation' ? '⚠️' : '📄'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-900 font-medium truncate">{activity.title}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{activity.description} • {activity.time}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Quick Links */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
          <h2 className="text-lg font-bold text-slate-900 mb-5">Quick Links</h2>
          <div className="grid grid-cols-2 gap-3">
            {[
              { name: 'Share Link', href: '/dashboard/share', icon: '🔗' },
              { name: 'Embed Widget', href: '/dashboard/widget', icon: '📱' },
              { name: 'Escalations', href: '/dashboard/escalations', icon: '📬', badge: stats.escalationRate > 0 ? Math.ceil(stats.escalationRate) : undefined },
              { name: 'Verified Q&A', href: '/dashboard/verified-qna', icon: '✅' },
              { name: 'Access Groups', href: '/dashboard/access-groups', icon: '👥' },
              { name: 'Settings', href: '/dashboard/settings', icon: '⚙️' },
            ].map((link) => (
              <Link
                key={link.name}
                href={link.href}
                className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 hover:bg-slate-100 transition-colors"
              >
                <span className="text-lg">{link.icon}</span>
                <span className="text-sm font-medium text-slate-700">{link.name}</span>
                {link.badge && (
                  <span className="ml-auto px-2 py-0.5 text-xs font-bold text-white bg-red-500 rounded-full">
                    {link.badge}
                  </span>
                )}
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* Conversations Modal */}
      {showConversationsModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] overflow-hidden">
            <div className="p-6 border-b border-slate-100 flex items-center justify-between">
              <h2 className="text-xl font-bold text-slate-900">Conversations ({stats.conversations})</h2>
              <button
                onClick={() => setShowConversationsModal(false)}
                className="p-2 hover:bg-slate-100 rounded-lg"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 overflow-y-auto max-h-[60vh]">
              {loadingConversations ? (
                <div className="text-center py-8 text-slate-400">Loading conversations...</div>
              ) : conversations.length === 0 ? (
                <div className="text-center py-8 text-slate-400">
                  <p className="text-4xl mb-3">💬</p>
                  <p>No conversations yet</p>
                  <p className="text-sm mt-1">Start chatting with your twin to see conversations here</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {conversations.map((conv) => (
                    <div key={conv.id} className="p-4 bg-slate-50 rounded-xl hover:bg-slate-100 transition-colors">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-slate-900">
                          {conv.message_count} messages
                        </span>
                        <span className="text-xs text-slate-400">
                          {formatTimeAgo(conv.created_at)}
                        </span>
                      </div>
                      {conv.last_message && (
                        <p className="text-sm text-slate-600 truncate">{conv.last_message}</p>
                      )}
                      <div className="flex items-center gap-2 mt-2">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${conv.avg_confidence >= 85 ? 'bg-emerald-100 text-emerald-700' :
                          conv.avg_confidence >= 70 ? 'bg-amber-100 text-amber-700' :
                            'bg-red-100 text-red-700'
                          }`}>
                          {conv.avg_confidence.toFixed(0)}% confidence
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Messages Modal */}
      {showMessagesModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
            <div className="p-6 border-b border-slate-100 flex items-center justify-between">
              <h2 className="text-xl font-bold text-slate-900">Message Breakdown</h2>
              <button
                onClick={() => setShowMessagesModal(false)}
                className="p-2 hover:bg-slate-100 rounded-lg"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div className="p-4 bg-blue-50 rounded-xl">
                <p className="text-2xl font-black text-blue-600">{stats.userMessages}</p>
                <p className="text-sm text-blue-600">User Messages (Questions)</p>
              </div>
              <div className="p-4 bg-purple-50 rounded-xl">
                <p className="text-2xl font-black text-purple-600">{stats.assistantMessages}</p>
                <p className="text-sm text-purple-600">Twin Responses</p>
              </div>
              <div className="p-4 bg-slate-50 rounded-xl">
                <p className="text-2xl font-black text-slate-900">{stats.messages}</p>
                <p className="text-sm text-slate-500">Total Messages</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Analysis Modal */}
      {showAnalysisModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
            <div className="p-6 border-b border-slate-100 flex items-center justify-between">
              <h2 className="text-xl font-bold text-slate-900">Performance Analysis</h2>
              <button
                onClick={() => setShowAnalysisModal(false)}
                className="p-2 hover:bg-slate-100 rounded-lg"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div className="p-4 bg-emerald-50 rounded-xl">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-emerald-600 font-medium">Response Rate</p>
                  <p className="text-2xl font-black text-emerald-600">{stats.responseRate.toFixed(1)}%</p>
                </div>
                <p className="text-xs text-emerald-500 mt-2">
                  {stats.responseRate >= 90 ? '✅ Excellent! Your twin responds to most questions.' :
                    stats.responseRate >= 70 ? '⚠️ Good, but some questions may need more verified knowledge.' :
                      '❌ Low response rate. Consider adding more knowledge.'}
                </p>
              </div>
              <div className="p-4 bg-orange-50 rounded-xl">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-orange-600 font-medium">Average Confidence</p>
                  <p className="text-2xl font-black text-orange-600">{stats.avgConfidence.toFixed(1)}%</p>
                </div>
                <p className="text-xs text-orange-500 mt-2">
                  {stats.avgConfidence >= 85 ? '✅ High confidence in responses.' :
                    stats.avgConfidence >= 70 ? '⚠️ Moderate confidence. Review escalations.' :
                      '❌ Low confidence. Add more verified Q&As.'}
                </p>
              </div>
              <div className="p-4 bg-red-50 rounded-xl">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-red-600 font-medium">Escalation Rate</p>
                  <p className="text-2xl font-black text-red-600">{stats.escalationRate.toFixed(1)}%</p>
                </div>
                <p className="text-xs text-red-500 mt-2">
                  {stats.escalationRate <= 5 ? '✅ Very few questions escalated.' :
                    stats.escalationRate <= 15 ? '⚠️ Some questions need owner review.' :
                      '❌ High escalation rate. Add more verified knowledge.'}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
