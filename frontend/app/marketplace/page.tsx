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
  occupation: string;
  headline: string;
  bio: string;
  short_description: string;
  avatar_url: string;
  answerability_score: number;
  verified_claims_count: number;
  public_topics: Array<{ slug: string; name: string; answerability_score: number }>;
  areas_of_expertise: string[];
  pinned_questions: string[];
  public_url: string | null;
  verified_profile: boolean;
};

type MarketplaceResponse = {
  items: MarketplacePersona[];
  facets: { topics: MarketplaceTopic[] };
  next_cursor: string | null;
};

function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');
}

function PersonaCard({ persona }: { persona: MarketplacePersona }) {
  const href = persona.public_url || '/marketplace';
  const summary =
    persona.short_description ||
    persona.bio ||
    'This persona is ready for conversations grounded in its published profile.';
  const expertise = persona.areas_of_expertise?.length
    ? persona.areas_of_expertise
    : persona.public_topics.map((topic) => topic.name);

  return (
    <Link
      href={href}
      className="group flex h-full flex-col rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-slate-300 hover:shadow-xl"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          {persona.avatar_url ? (
            <img
              src={persona.avatar_url}
              alt={persona.display_name}
              className="h-16 w-16 rounded-2xl object-cover"
            />
          ) : (
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#f59e0b,#f97316)] text-lg font-semibold text-white">
              {getInitials(persona.display_name) || 'P'}
            </div>
          )}

          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="truncate text-xl font-semibold text-slate-950">{persona.display_name}</h2>
              {persona.verified_profile && (
                <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-emerald-700">
                  Verified
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-slate-600">
              {persona.occupation || persona.headline || 'Public digital persona'}
            </p>
          </div>
        </div>

        <div className="rounded-2xl bg-slate-50 px-3 py-2 text-right">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            Answerability
          </p>
          <p className="text-lg font-semibold text-slate-950">
            {Math.round(persona.answerability_score || 0)}%
          </p>
        </div>
      </div>

      <div className="mt-6 space-y-3">
        {persona.headline && (
          <p className="text-sm font-medium text-amber-700">{persona.headline}</p>
        )}
        <p className="line-clamp-4 text-sm leading-6 text-slate-600">{summary}</p>
      </div>

      {expertise.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-2">
          {expertise.slice(0, 4).map((item) => (
            <span
              key={`${persona.twin_id}-${item}`}
              className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700"
            >
              {item}
            </span>
          ))}
        </div>
      )}

      {persona.pinned_questions.length > 0 && (
        <div className="mt-5 rounded-2xl bg-[#f8f5ef] px-4 py-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            Ask first
          </p>
          <p className="mt-2 text-sm text-slate-700">&ldquo;{persona.pinned_questions[0]}&rdquo;</p>
        </div>
      )}

      <div className="mt-6 flex items-center justify-between border-t border-slate-100 pt-4 text-sm text-slate-500">
        <span>{persona.verified_claims_count} verified public claims</span>
        <span className="font-medium text-slate-950 transition-colors group-hover:text-amber-700">
          Open profile
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
    }, 200);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const fetchMarketplace = async (cursor?: string | null, append = false) => {
    const searchParams = new URLSearchParams();
    if (query) searchParams.set('q', query);
    if (selectedTopic) searchParams.set('topic', selectedTopic);
    if (cursor) searchParams.set('cursor', cursor);
    searchParams.set('limit', '24');

    setError(null);
    if (append) {
      setLoadingMore(true);
    } else {
      setLoading(true);
    }

    try {
      const response = await fetch(`${apiBaseUrl}/public/marketplace?${searchParams.toString()}`, {
        cache: 'no-store',
      });
      if (!response.ok) {
        throw new Error(`Failed to load marketplace (${response.status})`);
      }

      const data = (await response.json()) as MarketplaceResponse;
      setTopics(data.facets?.topics || []);
      setNextCursor(data.next_cursor || null);
      setItems((previous) => (append ? [...previous, ...(data.items || [])] : data.items || []));
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
    <div className="min-h-screen bg-[#f5f1e8] text-slate-950">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_top_left,rgba(251,191,36,0.18),transparent_28%),radial-gradient(circle_at_85%_15%,rgba(15,118,110,0.10),transparent_22%)]" />

      <header className="relative border-b border-slate-200/80 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 lg:px-12">
          <Link href="/" className="text-lg font-semibold tracking-tight text-slate-950">
            Verified Digital Brains
          </Link>
          <div className="flex items-center gap-4 text-sm text-slate-600">
            <Link href="/marketplace" className="font-medium text-slate-950">
              Marketplace
            </Link>
            <Link href="/auth/login" className="transition-colors hover:text-slate-950">
              Sign in
            </Link>
            <Link
              href="/auth/login?redirect=/onboarding"
              className="rounded-full bg-slate-950 px-4 py-2 font-medium text-white transition-colors hover:bg-slate-800"
            >
              Create persona
            </Link>
          </div>
        </div>
      </header>

      <main className="relative mx-auto max-w-7xl px-6 pb-20 pt-14 lg:px-12">
        <section className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr] lg:items-end">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-amber-700">
              Public Persona Marketplace
            </p>
            <h1 className="mt-4 max-w-4xl text-5xl font-semibold leading-tight text-slate-950 md:text-6xl">
              Browse polished persona profiles before you open a conversation.
            </h1>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-600">
              These cards surface the same profile signals that make the best demo personas feel
              clean, credible, and immediately useful: a clear role, concise summary, visible
              expertise, and grounded conversation starters.
            </p>
          </div>

          <div className="rounded-[32px] border border-slate-200 bg-white/90 p-6 shadow-sm">
            <p className="text-sm font-semibold text-slate-950">What shows up here</p>
            <div className="mt-4 grid gap-4 text-sm text-slate-600 sm:grid-cols-3">
              <div>
                <p className="font-medium text-slate-950">Clean identity</p>
                <p className="mt-1">Occupation, short bio, and verified status appear first.</p>
              </div>
              <div>
                <p className="font-medium text-slate-950">Visible expertise</p>
                <p className="mt-1">Topic tags and expertise areas make each persona scannable.</p>
              </div>
              <div>
                <p className="font-medium text-slate-950">Better chat starts</p>
                <p className="mt-1">Pinned questions give each conversation a strong opening angle.</p>
              </div>
            </div>
          </div>
        </section>

        <section className="mt-10 rounded-[32px] border border-slate-200 bg-white/90 p-5 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <label className="flex-1">
              <span className="sr-only">Search personas</span>
              <input
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="Search by name, occupation, expertise, company, or topic..."
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-5 py-4 text-slate-950 placeholder:text-slate-400 focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200"
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
                className="rounded-2xl border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
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
                className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                  selectedTopic === null
                    ? 'bg-slate-950 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                All topics
              </button>
              {topics.map((topic) => (
                <button
                  key={topic.slug}
                  type="button"
                  onClick={() => setSelectedTopic(topic.slug)}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                    selectedTopic === topic.slug
                      ? 'bg-amber-500 text-white'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
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
              <div className="mx-auto h-12 w-12 animate-spin rounded-full border-4 border-slate-300 border-t-slate-950" />
              <p className="mt-4 text-sm font-medium text-slate-500">Loading personas...</p>
            </div>
          </div>
        ) : error ? (
          <div className="mt-10 rounded-[28px] border border-rose-200 bg-rose-50 p-6 text-rose-700">
            {error}
          </div>
        ) : items.length === 0 ? (
          <div className="mt-10 rounded-[32px] border border-slate-200 bg-white/90 p-8 shadow-sm">
            <EmptyState
              illustration="chat-bubble"
              title={hasActiveFilters ? 'No personas matched those filters' : 'No public personas yet'}
              description={
                hasActiveFilters
                  ? 'Try a broader search or clear the selected topic to see more personas.'
                  : 'Personas with strong public profile data will appear here automatically once they are ready.'
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
              theme="light"
            />
          </div>
        ) : (
          <>
            <div className="mt-10 grid gap-6 md:grid-cols-2 xl:grid-cols-3">
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
                  className="rounded-full bg-slate-950 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-slate-800 disabled:opacity-60"
                >
                  {loadingMore ? 'Loading more...' : 'Load more personas'}
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
