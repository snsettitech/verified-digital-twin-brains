'use client';

import Link from 'next/link';
import React, { useEffect, useMemo, useState } from 'react';

import EmptyState from '@/components/ui/EmptyState';
import { resolveApiBaseUrl } from '@/lib/api';

type MarketplaceTopic = {
  slug: string;
  name: string;
  count: number;
};

type MarketplacePersona = {
  twin_id: string;
  display_name: string;
  headline: string;
  bio: string;
  avatar_url: string;
  organization: string;
  role: string;
  mind_label: string;
  answerability_score: number;
  verified_claims_count: number;
  public_topics: Array<{ slug: string; name: string; answerability_score: number }>;
  pinned_questions: string[];
  handle: string;
  public_url: string | null;
};

type MarketplaceResponse = {
  items: MarketplacePersona[];
  facets: { topics: MarketplaceTopic[] };
  next_cursor: string | null;
};

function PersonaCard({ persona }: { persona: MarketplacePersona }) {
  const initials = persona.display_name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');

  const badge = persona.answerability_score
    ? `${Math.round(persona.answerability_score)}% answerable`
    : persona.mind_label || 'Public persona';

  return (
    <Link
      href={persona.public_url || '#'}
      className="group flex h-full flex-col rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl transition-all duration-300 hover:-translate-y-1 hover:border-cyan-400/40 hover:bg-white/10 hover:shadow-2xl hover:shadow-cyan-500/10"
    >
      <div className="mb-5 flex items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          {persona.avatar_url ? (
            <img
              src={persona.avatar_url}
              alt={persona.display_name}
              className="h-14 w-14 rounded-2xl object-cover ring-1 ring-white/10"
            />
          ) : (
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-500/20 to-indigo-500/30 text-lg font-black text-white ring-1 ring-white/10">
              {initials || 'P'}
            </div>
          )}
          <div className="min-w-0">
            <p className="truncate text-lg font-bold text-white">{persona.display_name}</p>
            <p className="truncate text-sm text-slate-400">
              {[persona.role, persona.organization].filter(Boolean).join(' · ') || 'Public persona'}
            </p>
          </div>
        </div>
        <span className="rounded-full border border-emerald-400/30 bg-emerald-500/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.2em] text-emerald-300">
          {badge}
        </span>
      </div>

      <div className="space-y-3">
        {persona.headline && (
          <p className="text-sm font-semibold text-cyan-200">{persona.headline}</p>
        )}
        <p className="line-clamp-4 text-sm leading-6 text-slate-300">
          {persona.bio || 'This persona is ready for public conversations.'}
        </p>
      </div>

      {persona.public_topics.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-2">
          {persona.public_topics.slice(0, 4).map((topic) => (
            <span
              key={`${persona.twin_id}-${topic.slug}`}
              className="rounded-full border border-white/10 bg-slate-900/40 px-3 py-1 text-xs font-medium text-slate-200"
            >
              {topic.name}
            </span>
          ))}
        </div>
      )}

      {persona.pinned_questions.length > 0 && (
        <div className="mt-5 rounded-2xl border border-white/10 bg-slate-950/30 p-4">
          <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.2em] text-slate-500">
            Try asking
          </p>
          <p className="text-sm text-slate-300">&ldquo;{persona.pinned_questions[0]}&rdquo;</p>
        </div>
      )}

      <div className="mt-6 flex items-center justify-between text-sm text-slate-400">
        <span>{persona.verified_claims_count} verified claims</span>
        <span className="font-semibold text-white transition-colors group-hover:text-cyan-200">
          Chat now →
        </span>
      </div>
    </Link>
  );
}

export default function MarketplacePage() {
  const apiBaseUrl = useMemo(() => resolveApiBaseUrl(), []);
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [items, setItems] = useState<MarketplacePersona[]>([]);
  const [topics, setTopics] = useState<MarketplaceTopic[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(searchInput.trim());
    }, 250);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const fetchMarketplace = async (cursor?: string | null, append = false) => {
    const searchParams = new URLSearchParams();
    if (query) searchParams.set('q', query);
    if (selectedTopic) searchParams.set('topic', selectedTopic);
    if (cursor) searchParams.set('cursor', cursor);
    searchParams.set('limit', '24');

    const url = `${apiBaseUrl}/public/marketplace?${searchParams.toString()}`;
    setError(null);
    if (append) {
      setLoadingMore(true);
    } else {
      setLoading(true);
    }

    try {
      const response = await fetch(url, { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`Failed to load marketplace (${response.status})`);
      }

      const data = (await response.json()) as MarketplaceResponse;
      setTopics(data.facets?.topics || []);
      setNextCursor(data.next_cursor || null);
      setItems((previous) => (append ? [...previous, ...(data.items || [])] : (data.items || [])));
    } catch (err) {
      console.error('[Marketplace] Failed to load personas:', err);
      setError('Unable to load the marketplace right now. Please try again in a moment.');
      if (!append) {
        setItems([]);
        setNextCursor(null);
      }
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    void fetchMarketplace(null, false);
  }, [apiBaseUrl, query, selectedTopic]);

  const hasActiveFilters = Boolean(query || selectedTopic);

  return (
    <div className="min-h-screen bg-[#08111f] text-white">
      <div className="fixed inset-0 pointer-events-none bg-[radial-gradient(circle_at_top,_rgba(34,211,238,0.12),_transparent_32%),radial-gradient(circle_at_80%_20%,_rgba(99,102,241,0.18),_transparent_26%)]" />

      <header className="border-b border-white/10 bg-slate-950/60 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 lg:px-12">
          <Link href="/" className="text-lg font-black tracking-tight text-white">
            PersonaOn AI
          </Link>
          <div className="flex items-center gap-4 text-sm text-slate-400">
            <Link href="/marketplace" className="text-white">Marketplace</Link>
            <Link href="/auth/login" className="hover:text-white transition-colors">Sign in</Link>
            <Link
              href="/auth/login?redirect=/onboarding"
              className="rounded-full bg-gradient-to-r from-cyan-500 to-indigo-500 px-4 py-2 font-semibold text-white shadow-lg shadow-cyan-500/20"
            >
              Create persona
            </Link>
          </div>
        </div>
      </header>

      <main className="relative mx-auto max-w-7xl px-6 pb-20 pt-14 lg:px-12">
        <section className="mb-12 grid gap-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
          <div>
            <p className="mb-4 text-sm font-bold uppercase tracking-[0.35em] text-cyan-300">
              Public persona marketplace
            </p>
            <h1 className="max-w-3xl text-5xl font-black leading-tight text-white md:text-6xl">
              Browse verified digital twins that anyone can talk to.
            </h1>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-300">
              Discover experts, advisors, recruiters, consultants, operators, and domain specialists.
              Every public-ready persona here can be opened directly into chat.
            </p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl">
            <p className="text-sm font-semibold text-slate-200">How this works</p>
            <div className="mt-4 space-y-4 text-sm text-slate-300">
              <p><span className="font-semibold text-white">Quality-first ranking.</span> Stronger public profiles surface first based on answerability and verified public evidence.</p>
              <p><span className="font-semibold text-white">Search and topics.</span> Use keywords or public topics to narrow in on the right persona quickly.</p>
              <p><span className="font-semibold text-white">Direct entry to chat.</span> Clicking a card opens the existing public conversation flow immediately.</p>
            </div>
          </div>
        </section>

        <section className="mb-8 rounded-[2rem] border border-white/10 bg-white/5 p-5 backdrop-blur-xl">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <label className="flex-1">
              <span className="sr-only">Search personas</span>
              <input
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="Search by name, topic, role, company, or what they know..."
                className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-5 py-4 text-white placeholder:text-slate-500 focus:border-cyan-400/40 focus:outline-none focus:ring-2 focus:ring-cyan-500/20"
              />
            </label>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={() => {
                  setSearchInput('');
                  setQuery('');
                  setSelectedTopic(null);
                }}
                className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-200 transition-colors hover:border-white/20 hover:text-white"
              >
                Clear filters
              </button>
            )}
          </div>

          {topics.length > 0 && (
            <div className="mt-5 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setSelectedTopic(null)}
                className={`rounded-full px-4 py-2 text-sm font-semibold transition-all ${
                  selectedTopic === null
                    ? 'bg-white text-slate-950'
                    : 'border border-white/10 bg-slate-950/40 text-slate-300 hover:text-white'
                }`}
              >
                All topics
              </button>
              {topics.map((topic) => (
                <button
                  key={topic.slug}
                  type="button"
                  onClick={() => setSelectedTopic(topic.slug)}
                  className={`rounded-full px-4 py-2 text-sm font-semibold transition-all ${
                    selectedTopic === topic.slug
                      ? 'bg-cyan-400 text-slate-950'
                      : 'border border-white/10 bg-slate-950/40 text-slate-300 hover:text-white'
                  }`}
                >
                  {topic.name} <span className="text-xs opacity-70">({topic.count})</span>
                </button>
              ))}
            </div>
          )}
        </section>

        {loading ? (
          <div className="flex min-h-[320px] items-center justify-center">
            <div className="text-center">
              <div className="mx-auto h-12 w-12 animate-spin rounded-full border-4 border-cyan-300/20 border-t-cyan-400" />
              <p className="mt-4 text-sm font-medium text-slate-400">Loading personas…</p>
            </div>
          </div>
        ) : error ? (
          <div className="rounded-3xl border border-rose-400/20 bg-rose-500/10 p-6 text-rose-100">
            {error}
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-[2rem] border border-white/10 bg-white/5 p-8 backdrop-blur-xl">
            <EmptyState
              illustration="chat-bubble"
              title={hasActiveFilters ? 'No personas matched those filters' : 'No public personas yet'}
              description={
                hasActiveFilters
                  ? 'Try a broader search or clear the topic filter to see more public personas.'
                  : 'Public-ready personas will appear here automatically once they have enough profile data to be surfaced.'
              }
              primaryAction={
                hasActiveFilters
                  ? {
                      label: 'Clear filters',
                      onClick: () => {
                        setSearchInput('');
                        setQuery('');
                        setSelectedTopic(null);
                      },
                    }
                  : {
                      label: 'Create a persona',
                      href: '/auth/login?redirect=/onboarding',
                  }
              }
              theme="dark"
            />
          </div>
        ) : (
          <>
            <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
              {items.map((persona) => (
                <PersonaCard key={persona.twin_id} persona={persona} />
              ))}
            </div>

            {nextCursor && (
              <div className="mt-10 flex justify-center">
                <button
                  type="button"
                  onClick={() => void fetchMarketplace(nextCursor, true)}
                  disabled={loadingMore}
                  className="rounded-full border border-white/10 bg-white/5 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/10 disabled:opacity-60"
                >
                  {loadingMore ? 'Loading more…' : 'Load more personas'}
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
