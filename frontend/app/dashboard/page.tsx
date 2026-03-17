'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';

import { EmptyState, EmptyTwinNoActivity } from '@/components/ui/EmptyState';
import { API_BASE_URL, API_ENDPOINTS } from '@/lib/constants';
import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';
import { getOnboardingResumeUrl, useTwin } from '@/lib/context/TwinContext';

interface AnswerMix {
  direct: number;
  derivable: number;
  insufficient: number;
}

interface Stats {
  conversations: number;
  messages: number;
  userMessages: number;
  assistantMessages: number;
  responseRate: number;
  reviewRate: number;
  citationRate: number;
  unsupportedRate: number;
  answerMix: AnswerMix;
}

interface Conversation {
  id: string;
  created_at: string;
  message_count: number;
  last_message: string | null;
  last_answerability_state: string | null;
  last_source_tier: string | null;
  review_required: boolean;
  citation_rate: number;
}

interface ActivityItem {
  id: string;
  type: string;
  title: string;
  description: string;
  time: string;
}

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffInSeconds < 60) return 'Just now';
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
  return `${Math.floor(diffInSeconds / 86400)}d ago`;
}

function stateTone(state?: string | null): string {
  switch (state) {
    case 'direct':
      return 'bg-emerald-100 text-emerald-700';
    case 'derivable':
      return 'bg-amber-100 text-amber-700';
    case 'insufficient':
      return 'bg-rose-100 text-rose-700';
    default:
      return 'bg-slate-100 text-slate-700';
  }
}

export default function DashboardPage(): React.JSX.Element {
  const { activeTwin, twins, isLoading: twinsLoading } = useTwin();

  const [systemStatus, setSystemStatus] = useState<'checking' | 'online' | 'offline' | 'degraded'>('checking');
  const [stats, setStats] = useState<Stats>({
    conversations: 0,
    messages: 0,
    userMessages: 0,
    assistantMessages: 0,
    responseRate: 0,
    reviewRate: 0,
    citationRate: 0,
    unsupportedRate: 0,
    answerMix: { direct: 0, derivable: 0, insufficient: 0 },
  });
  const [recentActivity, setRecentActivity] = useState<ActivityItem[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingConversations, setLoadingConversations] = useState(false);
  const [showConversationsModal, setShowConversationsModal] = useState(false);
  const [showMessagesModal, setShowMessagesModal] = useState(false);
  const [showAnalysisModal, setShowAnalysisModal] = useState(false);

  const nonActiveTwins = useMemo(
    () => twins.filter((twin) => twin.status && twin.status !== 'active'),
    [twins]
  );

  useEffect(() => {
    const checkHealth = async (): Promise<void> => {
      try {
        const response = await fetch(`${API_BASE_URL}${API_ENDPOINTS.HEALTH}`);
        if (!response.ok) {
          setSystemStatus('offline');
          return;
        }
        const payload = await response.json();
        setSystemStatus(payload.status === 'online' ? 'online' : 'degraded');
      } catch {
        setSystemStatus('offline');
      }
    };

    void checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const fetchData = async (): Promise<void> => {
      if (twinsLoading) return;
      setLoading(true);

      const twinId = activeTwin?.id;
      if (!twinId) {
        setLoading(false);
        return;
      }

      try {
        const statsResponse = await authFetchStandalone(`${API_ENDPOINTS.METRICS_DASHBOARD(twinId)}?days=30`);
        if (statsResponse.ok) {
          const data = await statsResponse.json();
          setStats({
            conversations: data.conversations ?? 0,
            messages: data.messages ?? 0,
            userMessages: data.user_messages ?? 0,
            assistantMessages: data.assistant_messages ?? 0,
            responseRate: data.response_rate ?? 0,
            reviewRate: data.review_rate ?? 0,
            citationRate: data.citation_rate ?? 0,
            unsupportedRate: data.unsupported_rate ?? 0,
            answerMix: {
              direct: data.answer_mix?.direct ?? 0,
              derivable: data.answer_mix?.derivable ?? 0,
              insufficient: data.answer_mix?.insufficient ?? 0,
            },
          });
        }
      } catch (error) {
        console.error('Failed to fetch dashboard stats:', error);
      }

      try {
        const activityResponse = await authFetchStandalone(`${API_ENDPOINTS.METRICS_ACTIVITY(twinId)}?limit=5`);
        if (activityResponse.ok) {
          const data: ActivityItem[] = await activityResponse.json();
          setRecentActivity(
            data.map((item) => ({
              ...item,
              time: formatTimeAgo(item.time),
            }))
          );
        }
      } catch (error) {
        console.error('Failed to fetch activity feed:', error);
      }

      setLoading(false);
    };

    void fetchData();
  }, [activeTwin?.id, twinsLoading]);

  const handleConversationsClick = async (): Promise<void> => {
    setShowConversationsModal(true);
    if (!activeTwin?.id) return;

    setLoadingConversations(true);
    try {
      const response = await authFetchStandalone(`${API_ENDPOINTS.METRICS_CONVERSATIONS(activeTwin.id)}?limit=20`);
      if (response.ok) {
        const data = await response.json();
        setConversations(data);
      }
    } catch (error) {
      console.error('Failed to fetch conversation summaries:', error);
    } finally {
      setLoadingConversations(false);
    }
  };

  const answerMixTotal =
    stats.answerMix.direct + stats.answerMix.derivable + stats.answerMix.insufficient;

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-slate-900">Dashboard</h1>
          <p className="mt-1 text-slate-500">Track how your persona is responding, citing, and getting reviewed.</p>
        </div>
        <div className="flex items-center gap-2 rounded-full border bg-white px-4 py-2 shadow-sm">
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              systemStatus === 'online'
                ? 'bg-emerald-500 animate-pulse'
                : systemStatus === 'degraded'
                  ? 'bg-amber-500'
                  : systemStatus === 'offline'
                    ? 'bg-rose-500'
                    : 'bg-slate-300 animate-pulse'
            }`}
          />
          <span className="text-sm font-semibold capitalize text-slate-700">{systemStatus}</span>
        </div>
      </div>

      {nonActiveTwins.length > 0 && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-amber-900">
            <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
            Continue Setup ({nonActiveTwins.length})
          </h2>
          <div className="space-y-3">
            {nonActiveTwins.map((twin) => (
              <div
                key={twin.id}
                className="flex items-center justify-between rounded-xl border border-amber-100 bg-white p-4"
              >
                <div>
                  <p className="font-semibold text-slate-900">{twin.name}</p>
                  <p className="text-sm capitalize text-slate-500">
                    Status: {twin.status?.replace('_', ' ') || 'Draft'}
                  </p>
                </div>
                <Link
                  href={getOnboardingResumeUrl(twin.id)}
                  className="rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-amber-600"
                >
                  Continue Setup
                </Link>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          {
            title: 'Conversations',
            value: stats.conversations.toLocaleString(),
            subtitle: 'Recent sessions',
            tone: 'bg-blue-500',
            onClick: handleConversationsClick,
          },
          {
            title: 'Messages',
            value: stats.messages.toLocaleString(),
            subtitle: `${stats.userMessages} user / ${stats.assistantMessages} assistant`,
            tone: 'bg-slate-900',
            onClick: () => setShowMessagesModal(true),
          },
          {
            title: 'Citation Rate',
            value: `${stats.citationRate.toFixed(1)}%`,
            subtitle: 'Answers with citations',
            tone: 'bg-emerald-500',
            onClick: () => setShowAnalysisModal(true),
          },
          {
            title: 'Review Rate',
            value: `${stats.reviewRate.toFixed(1)}%`,
            subtitle: 'Answers flagged for review',
            tone: 'bg-amber-500',
            onClick: () => setShowAnalysisModal(true),
          },
        ].map((card) => (
          <button
            key={card.title}
            onClick={() => void card.onClick()}
            className="rounded-2xl border border-slate-200 bg-white p-5 text-left shadow-sm transition-all hover:border-blue-300 hover:shadow-md"
          >
            <div className="mb-3 flex items-center justify-between">
              <span className={`rounded-full px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-white ${card.tone}`}>
                {card.title}
              </span>
            </div>
            <p className="text-2xl font-black text-slate-900">{card.value}</p>
            <p className="mt-1 text-sm text-slate-500">{card.subtitle}</p>
          </button>
        ))}
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Link href="/dashboard/simulator" className="group">
          <div className="relative h-full overflow-hidden rounded-2xl bg-blue-700 p-6 text-white shadow-xl shadow-blue-200 transition-all duration-300 hover:shadow-2xl">
            <div className="mb-4 inline-block rounded-full bg-white/20 px-3 py-1 text-xs font-bold uppercase tracking-wider">
              Recommended
            </div>
            <h3 className="text-xl font-bold">Interview Your Persona</h3>
            <p className="mt-1 text-sm text-blue-100">Capture voice, decision patterns, and better conversation coverage.</p>
          </div>
        </Link>

        <Link href="/dashboard/studio" className="group">
          <div className="h-full rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition-all duration-300 hover:shadow-xl">
            <h3 className="text-lg font-bold text-slate-900">Add Knowledge</h3>
            <p className="mt-1 text-sm text-slate-500">Upload files, URLs, and structured material.</p>
          </div>
        </Link>

        <Link href="/dashboard/simulator" className="group">
          <div className="h-full rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition-all duration-300 hover:shadow-xl">
            <h3 className="text-lg font-bold text-slate-900">Test Conversations</h3>
            <p className="mt-1 text-sm text-slate-500">See how the persona sounds before sharing it publicly.</p>
          </div>
        </Link>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-5 flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-900">Recent Activity</h2>
            <Link href="/dashboard/insights" className="text-sm font-medium text-blue-600 hover:text-blue-700">
              View All
            </Link>
          </div>

          <div className="space-y-4">
            {loading ? (
              <div className="py-8 text-center text-slate-400">Loading activity...</div>
            ) : recentActivity.length === 0 ? (
              activeTwin?.name ? (
                <EmptyTwinNoActivity twinName={activeTwin.name} />
              ) : (
                <EmptyState
                  illustration="chat-bubble"
                  title="No activity yet"
                  description="Start a conversation to see activity here."
                  primaryAction={{ label: 'Start Chatting', href: '/dashboard/simulator' }}
                />
              )
            ) : (
              recentActivity.map((activity) => (
                <div key={activity.id} className="flex items-start gap-3 border-b border-slate-100 pb-4 last:border-0 last:pb-0">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold uppercase text-slate-600">
                    {activity.type.slice(0, 1)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-slate-900">{activity.title}</p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {activity.description} · {activity.time}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-5 text-lg font-bold text-slate-900">Conversation Quality</h2>

          <div className="space-y-4">
            {[
              {
                label: 'Direct answers',
                value: stats.answerMix.direct,
                tone: 'bg-emerald-500',
              },
              {
                label: 'Derivable answers',
                value: stats.answerMix.derivable,
                tone: 'bg-amber-500',
              },
              {
                label: 'Insufficient turns',
                value: stats.answerMix.insufficient,
                tone: 'bg-rose-500',
              },
            ].map((item) => {
              const percent = answerMixTotal > 0 ? (item.value / answerMixTotal) * 100 : 0;
              return (
                <div key={item.label}>
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="font-medium text-slate-700">{item.label}</span>
                    <span className="text-slate-500">{item.value}</span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-100">
                    <div className={`h-2 rounded-full ${item.tone}`} style={{ width: `${percent}%` }} />
                  </div>
                </div>
              );
            })}

            <div className="grid grid-cols-2 gap-3 pt-4">
              <div className="rounded-xl bg-slate-50 p-4">
                <div className="text-sm font-medium text-slate-600">Unsupported Rate</div>
                <div className="mt-1 text-2xl font-black text-slate-900">{stats.unsupportedRate.toFixed(1)}%</div>
              </div>
              <div className="rounded-xl bg-slate-50 p-4">
                <div className="text-sm font-medium text-slate-600">Response Rate</div>
                <div className="mt-1 text-2xl font-black text-slate-900">{stats.responseRate.toFixed(1)}%</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {showConversationsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="max-h-[80vh] w-full max-w-2xl overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-100 p-6">
              <h2 className="text-xl font-bold text-slate-900">Conversations ({stats.conversations})</h2>
              <button onClick={() => setShowConversationsModal(false)} className="rounded-lg p-2 hover:bg-slate-100">
                <span className="sr-only">Close</span>
                ×
              </button>
            </div>
            <div className="max-h-[60vh] overflow-y-auto p-6">
              {loadingConversations ? (
                <div className="py-8 text-center text-slate-400">Loading conversations...</div>
              ) : conversations.length === 0 ? (
                <div className="py-8 text-center text-slate-400">
                  <p>No conversations yet.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {conversations.map((conversation) => (
                    <div key={conversation.id} className="rounded-xl bg-slate-50 p-4">
                      <div className="mb-2 flex items-center justify-between">
                        <span className="text-sm font-medium text-slate-900">{conversation.message_count} messages</span>
                        <span className="text-xs text-slate-400">{formatTimeAgo(conversation.created_at)}</span>
                      </div>
                      {conversation.last_message && (
                        <p className="truncate text-sm text-slate-600">{conversation.last_message}</p>
                      )}
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${stateTone(conversation.last_answerability_state)}`}>
                          {conversation.last_answerability_state || 'direct'}
                        </span>
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                          {conversation.last_source_tier || 'mixed'}
                        </span>
                        {conversation.review_required && (
                          <span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-700">
                            review
                          </span>
                        )}
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                          {conversation.citation_rate.toFixed(0)}% cited
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

      {showMessagesModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-100 p-6">
              <h2 className="text-xl font-bold text-slate-900">Message Breakdown</h2>
              <button onClick={() => setShowMessagesModal(false)} className="rounded-lg p-2 hover:bg-slate-100">
                <span className="sr-only">Close</span>
                ×
              </button>
            </div>
            <div className="space-y-4 p-6">
              <div className="rounded-xl bg-blue-50 p-4">
                <p className="text-2xl font-black text-blue-600">{stats.userMessages}</p>
                <p className="text-sm text-blue-600">User messages</p>
              </div>
              <div className="rounded-xl bg-emerald-50 p-4">
                <p className="text-2xl font-black text-emerald-600">{stats.assistantMessages}</p>
                <p className="text-sm text-emerald-600">Assistant responses</p>
              </div>
              <div className="rounded-xl bg-slate-50 p-4">
                <p className="text-2xl font-black text-slate-900">{stats.messages}</p>
                <p className="text-sm text-slate-500">Total messages</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {showAnalysisModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-100 p-6">
              <h2 className="text-xl font-bold text-slate-900">Conversation Analysis</h2>
              <button onClick={() => setShowAnalysisModal(false)} className="rounded-lg p-2 hover:bg-slate-100">
                <span className="sr-only">Close</span>
                ×
              </button>
            </div>
            <div className="space-y-4 p-6">
              <div className="rounded-xl bg-emerald-50 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-emerald-700">Citation Rate</p>
                  <p className="text-2xl font-black text-emerald-700">{stats.citationRate.toFixed(1)}%</p>
                </div>
                <p className="mt-2 text-xs text-emerald-600">How often responses include supporting citations.</p>
              </div>
              <div className="rounded-xl bg-amber-50 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-amber-700">Review Rate</p>
                  <p className="text-2xl font-black text-amber-700">{stats.reviewRate.toFixed(1)}%</p>
                </div>
                <p className="mt-2 text-xs text-amber-600">Turns flagged for owner review or follow-up.</p>
              </div>
              <div className="rounded-xl bg-rose-50 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-rose-700">Unsupported Rate</p>
                  <p className="text-2xl font-black text-rose-700">{stats.unsupportedRate.toFixed(1)}%</p>
                </div>
                <p className="mt-2 text-xs text-rose-600">Turns that ended in an insufficient answer state.</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
