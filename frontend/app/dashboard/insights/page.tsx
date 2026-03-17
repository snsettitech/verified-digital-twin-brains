'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';

import { useTwin } from '@/lib/context/TwinContext';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';

interface AnswerMix {
  direct: number;
  derivable: number;
  insufficient: number;
}

interface DashboardStats {
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

interface DailyMetric {
  date: string;
  conversations: number;
  messages: number;
}

interface TopQuestion {
  question: string;
  count: number;
  top_answerability_state: string;
  review_rate: number;
  citation_rate: number;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', { weekday: 'short' });
}

function toneForState(state: string): string {
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

export default function InsightsPage(): React.JSX.Element {
  const { activeTwin, isLoading: twinLoading } = useTwin();
  const { get } = useAuthFetch();

  const twinId = activeTwin?.id;
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d'>('30d');
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats>({
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
  const [dailyData, setDailyData] = useState<DailyMetric[]>([]);
  const [topQuestions, setTopQuestions] = useState<TopQuestion[]>([]);

  const getDays = useCallback(() => {
    switch (timeRange) {
      case '7d':
        return 7;
      case '30d':
        return 30;
      case '90d':
        return 90;
      default:
        return 30;
    }
  }, [timeRange]);

  const fetchData = useCallback(async () => {
    if (!twinId) return;

    setLoading(true);
    const days = getDays();

    try {
      const [statsResponse, dailyResponse, questionsResponse] = await Promise.all([
        get(`/metrics/dashboard/${twinId}?days=${days}`),
        get(`/metrics/daily/${twinId}?days=${Math.min(days, 30)}`),
        get(`/metrics/top-questions/${twinId}?limit=5`),
      ]);

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

      if (dailyResponse.ok) {
        setDailyData(await dailyResponse.json());
      }

      if (questionsResponse.ok) {
        setTopQuestions(await questionsResponse.json());
      }
    } catch (error) {
      console.error('Failed to fetch insights data:', error);
    } finally {
      setLoading(false);
    }
  }, [get, getDays, twinId]);

  useEffect(() => {
    if (twinId) {
      void fetchData();
    } else if (!twinLoading) {
      setLoading(false);
    }
  }, [fetchData, twinId, twinLoading]);

  const maxConversations = useMemo(
    () => Math.max(...dailyData.map((item) => item.conversations), 1),
    [dailyData]
  );

  if (twinLoading || loading) {
    return (
      <div className="space-y-8">
        <div className="animate-pulse">
          <div className="mb-4 h-8 w-48 rounded bg-slate-200" />
          <div className="grid grid-cols-3 gap-4">
            <div className="h-32 rounded-2xl bg-slate-200" />
            <div className="h-32 rounded-2xl bg-slate-200" />
            <div className="h-32 rounded-2xl bg-slate-200" />
          </div>
        </div>
      </div>
    );
  }

  if (!twinId) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="max-w-md p-8 text-center">
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-100 text-blue-600">
            <span className="text-xl font-bold">i</span>
          </div>
          <h2 className="mb-3 text-2xl font-bold text-slate-900">No Twin Found</h2>
          <p className="mb-6 text-slate-500">Create your persona first to view insights.</p>
          <a
            href="/dashboard/studio"
            className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white transition-colors hover:bg-blue-700"
          >
            Create Your Persona
          </a>
        </div>
      </div>
    );
  }

  const answerMixTotal = stats.answerMix.direct + stats.answerMix.derivable + stats.answerMix.insufficient;

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-slate-900">Insights</h1>
          <p className="mt-1 text-slate-500">See what the persona answers cleanly, cites often, and still struggles with.</p>
        </div>
        <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-1">
          {(['7d', '30d', '90d'] as const).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-all ${
                timeRange === range ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              {range === '7d' ? '7 Days' : range === '30d' ? '30 Days' : '90 Days'}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          { label: 'Conversations', value: stats.conversations.toLocaleString(), description: 'Unique chat sessions' },
          { label: 'Messages', value: stats.messages.toLocaleString(), description: `${stats.userMessages} user / ${stats.assistantMessages} assistant` },
          { label: 'Citation Rate', value: `${stats.citationRate.toFixed(1)}%`, description: 'Responses with support links' },
          { label: 'Review Rate', value: `${stats.reviewRate.toFixed(1)}%`, description: 'Responses flagged for follow-up' },
        ].map((metric) => (
          <div key={metric.label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-2xl font-black text-slate-900">{metric.value}</p>
            <p className="mt-1 text-sm text-slate-500">{metric.label}</p>
            <p className="mt-2 text-xs text-slate-400">{metric.description}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.4fr,1fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-bold text-slate-900">Conversation Volume</h2>
          <div className="mt-6 flex items-end gap-3">
            {dailyData.map((item) => (
              <div key={item.date} className="flex flex-1 flex-col items-center gap-2">
                <div className="flex h-48 w-full items-end rounded-xl bg-slate-50 px-2 pb-2">
                  <div
                    className="w-full rounded-lg bg-blue-500"
                    style={{ height: `${(item.conversations / maxConversations) * 100}%` }}
                  />
                </div>
                <span className="text-xs text-slate-500">{formatDate(item.date)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-bold text-slate-900">Answer Mix</h2>
          <div className="mt-5 space-y-4">
            {[
              { label: 'Direct', value: stats.answerMix.direct, tone: 'bg-emerald-500' },
              { label: 'Derivable', value: stats.answerMix.derivable, tone: 'bg-amber-500' },
              { label: 'Insufficient', value: stats.answerMix.insufficient, tone: 'bg-rose-500' },
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
          </div>
          <div className="mt-6 grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="text-sm font-medium text-slate-600">Response Rate</div>
              <div className="mt-1 text-2xl font-black text-slate-900">{stats.responseRate.toFixed(1)}%</div>
            </div>
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="text-sm font-medium text-slate-600">Unsupported Rate</div>
              <div className="mt-1 text-2xl font-black text-slate-900">{stats.unsupportedRate.toFixed(1)}%</div>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-900">Top Questions</h2>
          <span className="text-sm text-slate-400">Most repeated prompts in this range</span>
        </div>

        <div className="space-y-4">
          {topQuestions.length === 0 ? (
            <div className="rounded-xl bg-slate-50 p-6 text-sm text-slate-500">
              No questions recorded yet for this time range.
            </div>
          ) : (
            topQuestions.map((question, index) => (
              <div key={`${question.question}-${index}`} className="rounded-xl border border-slate-100 bg-slate-50 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-slate-900">{question.question}</p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${toneForState(question.top_answerability_state)}`}>
                        {question.top_answerability_state}
                      </span>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                        {question.citation_rate.toFixed(0)}% cited
                      </span>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                        {question.review_rate.toFixed(0)}% review
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xl font-black text-slate-900">{question.count}</div>
                    <div className="text-xs text-slate-400">times asked</div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
