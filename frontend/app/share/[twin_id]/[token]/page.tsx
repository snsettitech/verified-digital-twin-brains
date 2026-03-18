'use client';

import Link from 'next/link';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'next/navigation';

import { resolveApiBaseUrl } from '@/lib/api';

type Message = {
  role: 'user' | 'assistant';
  content: string;
  citations?: string[];
  citation_details?: Array<{ id: string; filename?: string | null; citation_url?: string | null }>;
  answerability_state?: string;
  source_tier?: string;
  review_required?: boolean;
  review_reason?: string | null;
  isError?: boolean;
};

type RequestError = {
  type: 'network' | 'auth' | 'validation' | 'server' | 'unknown';
  message: string;
  canRetry: boolean;
};

type PublicProfile = {
  name?: string;
  twin_name?: string;
  occupation?: string;
  headline?: string;
  bio?: string;
  short_description?: string;
  avatar_url?: string;
  image_url?: string;
  birth_year?: number | null;
  death_year?: number | null;
  nationality?: string;
  verified_profile?: boolean;
  verified_claims_count?: number;
  areas_of_expertise?: string[];
  personality_traits?: string[];
  key_achievements?: string[];
  contributions?: string[];
  speaking_style?: string;
  social_links?: Record<string, string>;
  education?: Array<{ institution?: string; degree?: string; field?: string; start_year?: number | null; end_year?: number | null }>;
  work_experience?: Array<{ company?: string; role?: string; description?: string; start_year?: number | null; end_year?: number | null }>;
  pinned_questions?: string[];
  citations_enabled?: boolean;
};

function getErrorFromResponse(status: number, body?: string): RequestError {
  if (status === 401 || status === 403) return { type: 'auth', message: 'This share link is invalid or has expired.', canRetry: false };
  if (status === 422) return { type: 'validation', message: "Your message couldn't be processed. Please try rephrasing.", canRetry: true };
  if (status === 429) return { type: 'server', message: 'Too many requests. Please wait a moment and try again.', canRetry: true };
  if ([500, 502, 503, 504].includes(status)) return { type: 'server', message: 'Server error. Please try again in a moment.', canRetry: true };
  return { type: 'unknown', message: body || 'An unexpected error occurred.', canRetry: true };
}

function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase() ?? '').join('');
}

function yearRange(start?: number | null, end?: number | null): string {
  if (!start && !end) return '';
  if (start && end) return `${start} – ${end}`;
  if (start) return `${start} – Present`;
  return `${end}`;
}

function lifeLine(profile: PublicProfile | null): string {
  if (!profile) return '';
  const years = yearRange(profile.birth_year, profile.death_year);
  if (profile.nationality && years) return `${profile.nationality} • ${years}`;
  return profile.nationality || years;
}

function socialLabel(label: string): string {
  return label.charAt(0).toUpperCase() + label.slice(1);
}

const SAFE_URL_PROTOCOLS = new Set(['http:', 'https:']);

function sanitizeHref(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  try {
    const parsed = new URL(url);
    return SAFE_URL_PROTOCOLS.has(parsed.protocol) ? url : undefined;
  } catch {
    return undefined;
  }
}

function Section({ title, items }: { title: string; items?: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <section className="rounded-[24px] border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">{title}</h2>
      <div className="mt-3 flex flex-wrap gap-2">
        {items.map((item) => (
          <span key={`${title}-${item}`} className="rounded-full bg-slate-100 px-3 py-1.5 text-sm text-slate-700">
            {item}
          </span>
        ))}
      </div>
    </section>
  );
}

/* ─── Conversion bar — acquisition surface ─── */
function ConversionBar({ name }: { name: string }) {
  return (
    <div className="fixed bottom-0 left-0 right-0 z-30 border-t border-slate-200/70 bg-white/92 backdrop-blur-sm px-4 py-2.5">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
        <p className="text-sm text-slate-500">
          <span className="font-semibold text-slate-800">{name}</span>{' '}
          is powered by <span className="font-semibold text-slate-800">PersonaOn AI</span>
        </p>
        <Link
          href="/auth/signup"
          className="shrink-0 rounded-full bg-[#F97316] px-4 py-1.5 text-sm font-semibold text-white shadow-[0_0_14px_rgba(249,115,22,0.35)] transition-shadow duration-200 hover:shadow-[0_0_20px_rgba(249,115,22,0.50)]"
        >
          Build yours free →
        </Link>
      </div>
    </div>
  );
}

export default function PublicSharePage() {
  const params = useParams();
  const twinId = Array.isArray(params?.twin_id) ? params.twin_id[0] : (params?.twin_id ?? '');
  const shareToken = Array.isArray(params?.token) ? params.token[0] : (params?.token ?? '');
  const apiBaseUrl = useMemo(() => resolveApiBaseUrl(), []);
  const storageKey = useMemo(() => (twinId && shareToken ? `public_chat_${twinId}_${shareToken.slice(0, 8)}` : null), [shareToken, twinId]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isValid, setIsValid] = useState<boolean | null>(null);
  const [twinName, setTwinName] = useState('AI Assistant');
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUserMessage, setLastUserMessage] = useState<string | null>(null);
  const [requestError, setRequestError] = useState<RequestError | null>(null);
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>([
    'Tell me about yourself',
    'What are you best at?',
    'What work are you known for?',
    'What should I ask you about?',
  ]);

  useEffect(() => {
    if (!storageKey) return;
    try {
      const stored = localStorage.getItem(storageKey);
      if (!stored) return;
      const parsed = JSON.parse(stored) as Message[];
      if (Array.isArray(parsed)) setMessages(parsed.filter((item) => !item.isError));
    } catch {
      // Ignore invalid local state.
    }
  }, [storageKey]);

  useEffect(() => {
    if (!storageKey || messages.length === 0) return;
    try {
      const payload = JSON.stringify(messages.slice(-50));
      if (payload.length < 200_000) localStorage.setItem(storageKey, payload);
    } catch {
      // Ignore storage errors.
    }
  }, [messages, storageKey]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    const validate = async () => {
      if (!twinId || !shareToken) return;
      try {
        const response = await fetch(`${apiBaseUrl}/share/${twinId}/${shareToken}/profile`);
        if (!response.ok) {
          setIsValid(false);
          const body = await response.text().catch(() => '');
          setError(getErrorFromResponse(response.status, body).message);
          return;
        }
        const data = (await response.json()) as PublicProfile;
        const resolvedName = data.name || data.twin_name || 'AI Assistant';
        setTwinName(resolvedName);
        setProfile({ ...data, name: resolvedName, avatar_url: data.avatar_url || data.image_url || '' });
        setSuggestedQuestions(
          Array.isArray(data.pinned_questions) && data.pinned_questions.length > 0
            ? data.pinned_questions.slice(0, 4)
            : [`What should I know about ${resolvedName}?`, `What topics can ${resolvedName} help with?`, 'Tell me about yourself', 'What is your background?'],
        );
        setIsValid(true);
      } catch {
        setIsValid(false);
        setError('Unable to connect to the server. Please check your connection.');
      }
    };

    void validate();
  }, [apiBaseUrl, shareToken, twinId]);

  const sendMessage = async (overrideText?: string, options?: { retry?: boolean }) => {
    const text = (overrideText ?? input).trim();
    if (!text || isLoading || !isValid) return;

    setRequestError(null);
    if (!options?.retry) {
      setMessages((previous) => [...previous, { role: 'user', content: text }]);
      setInput('');
    }
    setLastUserMessage(text);
    setIsLoading(true);

    try {
      const response = await fetch(`${apiBaseUrl}/public/chat/${twinId}/${shareToken}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          conversation_history: messages.filter((message) => !message.isError).map((message) => ({ role: message.role, content: message.content })),
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setMessages((previous) => [
          ...previous,
          {
            role: 'assistant',
            content: data.status === 'queued'
              ? 'This question has been queued for the owner to review. Please check back shortly.'
              : data.response || 'No response',
            citations: data.citations || [],
            citation_details: data.citation_details || [],
            answerability_state: data.answerability_state,
            source_tier: data.source_tier,
            review_required: data.review_required,
            review_reason: data.review_reason,
            isError: false,
          },
        ]);
      } else {
        const nextError = getErrorFromResponse(response.status, await response.text().catch(() => ''));
        setRequestError(nextError);
        setMessages((previous) => [...previous, { role: 'assistant', content: nextError.message, isError: true }]);
      }
    } catch {
      const nextError: RequestError = { type: 'network', message: 'Unable to connect. Please check your internet connection.', canRetry: true };
      setRequestError(nextError);
      setMessages((previous) => [...previous, { role: 'assistant', content: nextError.message, isError: true }]);
    } finally {
      setIsLoading(false);
    }
  };

  const retryLastMessage = () => {
    if (!lastUserMessage || isLoading) return;
    setMessages((previous) => (previous[previous.length - 1]?.isError ? previous.slice(0, -1) : previous));
    setRequestError(null);
    void sendMessage(lastUserMessage, { retry: true });
  };

  const clearHistory = () => {
    if (!window.confirm('Clear this conversation?')) return;
    setMessages([]);
    setLastUserMessage(null);
    setRequestError(null);
    if (!storageKey) return;
    try {
      localStorage.removeItem(storageKey);
    } catch {
      // Ignore storage errors.
    }
  };

  /* ─── Loading state ─── */
  if (isValid === null) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f6f2ea]">
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
          Loading persona…
        </div>
      </div>
    );
  }

  /* ─── Invalid link ─── */
  if (!isValid) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f6f2ea] p-4">
        <div className="w-full max-w-md rounded-[24px] border border-slate-200 bg-white p-8 text-center shadow-sm">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-slate-100">
            <svg className="h-6 w-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
            </svg>
          </div>
          <h1 className="text-xl font-semibold text-slate-900">Link not found</h1>
          <p className="mt-2 text-sm text-slate-500">{error}</p>
          <Link href="/marketplace" className="mt-6 inline-block rounded-full bg-slate-900 px-5 py-2 text-sm font-medium text-white hover:bg-slate-700">
            Browse personas
          </Link>
        </div>
      </div>
    );
  }

  const summary = profile?.short_description || profile?.bio || `${twinName} is available for public conversations grounded in published profile information.`;
  const expertise = profile?.areas_of_expertise || [];
  const socials = Object.entries(profile?.social_links || {});

  return (
    /* Extra bottom padding = ConversionBar height (~52px) */
    <div className="min-h-screen bg-[#f6f2ea] text-slate-950 pb-14">

      {/* Subtle radial warm accent — kept from original */}
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_top_left,rgba(251,191,36,0.12),transparent_28%),radial-gradient(circle_at_88%_12%,rgba(15,118,110,0.07),transparent_24%)]" />

      {/* ─── Nav bar ─── */}
      <header className="relative border-b border-slate-200/80 bg-white/80 backdrop-blur-sm sticky top-0 z-20">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3 lg:px-10">
          <div className="flex items-center gap-3 text-sm">
            <Link href="/marketplace" className="font-medium text-slate-500 hover:text-slate-900 transition-colors">
              Marketplace
            </Link>
            <span className="text-slate-300">/</span>
            <span className="font-medium text-slate-900">{twinName}</span>
          </div>
          {/* Always On indicator */}
          <div className="flex items-center gap-1.5 text-xs font-medium text-emerald-600">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            Always On
          </div>
        </div>
      </header>

      <main className="relative mx-auto max-w-7xl px-4 pb-6 pt-8 lg:px-10 lg:pt-10">

        {/* ─── Profile hero ─── */}
        <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <div className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">

            {/* Left: identity */}
            <div className="flex gap-5">
              {profile?.avatar_url ? (
                <img
                  src={profile.avatar_url}
                  alt={twinName}
                  className="h-20 w-20 shrink-0 rounded-[20px] object-cover shadow-sm sm:h-24 sm:w-24"
                />
              ) : (
                <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-[20px] bg-[linear-gradient(135deg,#f59e0b,#f97316)] text-2xl font-semibold text-white shadow-sm sm:h-24 sm:w-24">
                  {initials(twinName) || 'P'}
                </div>
              )}

              <div className="min-w-0">
                {/* Name row */}
                <div className="flex flex-wrap items-center gap-2.5">
                  <h1 className="text-3xl font-semibold text-slate-950 sm:text-4xl">{twinName}</h1>
                  {Boolean(profile?.verified_profile) && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200/60 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-700">
                      <svg className="h-3 w-3" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                        <path fillRule="evenodd" d="M8.603 3.799A4.49 4.49 0 0112 2.25c1.357 0 2.573.6 3.397 1.549a4.49 4.49 0 013.498 1.307 4.491 4.491 0 011.307 3.497A4.49 4.49 0 0121.75 12a4.49 4.49 0 01-1.549 3.397 4.491 4.491 0 01-1.307 3.497 4.491 4.491 0 01-3.497 1.307A4.49 4.49 0 0112 21.75a4.49 4.49 0 01-3.397-1.549 4.49 4.49 0 01-3.498-1.306 4.491 4.491 0 01-1.307-3.498A4.49 4.49 0 012.25 12c0-1.357.6-2.573 1.549-3.397a4.49 4.49 0 011.307-3.497 4.49 4.49 0 013.497-1.307zm7.007 6.387a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clipRule="evenodd" />
                      </svg>
                      Verified
                    </span>
                  )}
                </div>

                {/* Headline */}
                <p className="mt-1.5 text-base text-slate-600 sm:text-lg">
                  {profile?.headline || profile?.occupation || 'Public digital persona'}
                </p>
                {lifeLine(profile) && (
                  <p className="mt-1 text-sm text-slate-400">{lifeLine(profile)}</p>
                )}

                {/* Bio */}
                <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600 sm:text-base">{summary}</p>

                {/* Social links */}
                {socials.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {socials.map(([label, url]) => (
                      <a
                        key={`${label}-${url}`}
                        href={sanitizeHref(url)}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 hover:border-slate-300 hover:text-slate-900 transition-colors"
                      >
                        {socialLabel(label)}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Right: stats */}
            <div className="grid grid-cols-3 gap-3 sm:gap-4 lg:grid-cols-1">
              <div className="rounded-[18px] bg-[#f8f5ef] p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Profile</p>
                <p className="mt-1.5 text-base font-semibold text-slate-900">
                  {profile?.verified_profile ? 'Verified public persona' : 'Public digital persona'}
                </p>
              </div>
              <div className="rounded-[18px] bg-[#f8f5ef] p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Verified Claims</p>
                <p className="mt-1.5 text-2xl font-semibold text-slate-900">{profile?.verified_claims_count || 0}</p>
              </div>
              <div className="rounded-[18px] bg-[#f8f5ef] p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Speaking Style</p>
                <p className="mt-1.5 text-sm leading-6 text-slate-700">{profile?.speaking_style || 'Direct and grounded.'}</p>
              </div>
            </div>
          </div>
        </section>

        {/* ─── Chat + Profile details ─────────────────────────────
            DOM order: chat first → visible above fold on mobile.
            On desktop: CSS order flips — details left, chat right.
        ─────────────────────────────────────────────────────────── */}
        <section className="mt-6 grid gap-6 lg:grid-cols-[0.92fr_1.08fr] lg:gap-8">

          {/* Chat — first in DOM = first on mobile */}
          <section className="order-first lg:order-last lg:sticky lg:top-20">
            <div className="flex h-[76vh] min-h-[560px] flex-col overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm">

              {/* Chat header */}
              <div className="border-b border-slate-100 px-5 py-4">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2.5">
                    {profile?.avatar_url ? (
                      <img src={profile.avatar_url} alt={twinName} className="h-8 w-8 rounded-full object-cover" />
                    ) : (
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[linear-gradient(135deg,#f59e0b,#f97316)] text-xs font-semibold text-white">
                        {initials(twinName) || 'P'}
                      </div>
                    )}
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{twinName}</p>
                      <div className="flex items-center gap-1 text-[11px] text-emerald-600">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                        Always on
                      </div>
                    </div>
                  </div>
                  {messages.length > 0 && (
                    <button
                      onClick={clearHistory}
                      className="cursor-pointer rounded-xl border border-slate-200 px-3 py-1.5 text-xs text-slate-500 hover:border-slate-300 hover:text-slate-800 transition-colors"
                    >
                      Clear
                    </button>
                  )}
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto px-5 py-5" aria-live="polite" aria-atomic="false" aria-label="Conversation">
                {messages.length === 0 ? (
                  <div className="flex h-full flex-col items-center justify-center text-center px-4">
                    <div className="flex h-16 w-16 items-center justify-center rounded-[20px] bg-slate-50 shadow-sm">
                      <svg className="h-8 w-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                      </svg>
                    </div>
                    <h3 className="mt-4 text-lg font-semibold text-slate-900">Ask {twinName} anything</h3>
                    <p className="mt-2 max-w-xs text-sm leading-6 text-slate-400">
                      Answers are grounded in their published knowledge and profile.
                    </p>
                    {/* Pinned question chips — above fold */}
                    <div className="mt-5 flex max-w-sm flex-wrap justify-center gap-2">
                      {suggestedQuestions.map((question) => (
                        <button
                          key={question}
                          onClick={() => void sendMessage(question)}
                          className="cursor-pointer rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 hover:border-slate-300 hover:bg-slate-50 transition-colors"
                        >
                          {question}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {messages.map((message, index) => (
                      <div key={`${message.role}-${index}`} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[85%] rounded-[20px] px-4 py-3 text-sm leading-6 ${
                          message.role === 'user'
                            ? 'bg-slate-900 text-white'
                            : message.isError
                              ? 'border border-rose-200 bg-rose-50 text-rose-700'
                              : 'border border-slate-200 bg-slate-50 text-slate-800'
                        }`}>
                          <p className="whitespace-pre-wrap">{message.content}</p>
                          {message.role === 'assistant' && !message.isError && message.citations && message.citations.length > 0 && (
                            <div className="mt-2.5 flex flex-wrap gap-1.5 border-t border-slate-200/60 pt-2.5">
                              {message.citations?.map((source, citationIndex) => {
                                const detail = message.citation_details?.[citationIndex];
                                const label = detail?.filename || source || `Source ${citationIndex + 1}`;
                                const href = sanitizeHref(detail?.citation_url);
                                return (
                                  <span key={`${label}-${citationIndex}`} className="rounded-full bg-white px-2.5 py-0.5 text-[11px] font-medium text-slate-500 ring-1 ring-slate-200">
                                    {href ? (
                                      <a href={href} target="_blank" rel="noreferrer" className="hover:text-slate-800 hover:underline">{label}</a>
                                    ) : (
                                      <span>{label}</span>
                                    )}
                                  </span>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                    {isLoading && (
                      <div className="flex items-center gap-2 rounded-[20px] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-400">
                        <div className="h-3 w-3 animate-spin rounded-full border-2 border-slate-300 border-t-slate-500" />
                        Thinking…
                      </div>
                    )}
                    <div ref={messagesEndRef} />
                  </div>
                )}
              </div>

              {/* Retry banner */}
              {requestError && requestError.canRetry && !isLoading && (
                <div className="border-t border-rose-100 bg-rose-50 px-5 py-2.5">
                  <div className="flex items-center justify-between gap-4">
                    <p className="text-sm text-rose-600">{requestError.message}</p>
                    <button onClick={retryLastMessage} className="cursor-pointer rounded-xl border border-rose-200 px-3 py-1.5 text-xs font-medium text-rose-600 hover:bg-rose-100 transition-colors">
                      Retry
                    </button>
                  </div>
                </div>
              )}

              {/* Input row */}
              <div className="border-t border-slate-100 p-4">
                <div className="flex gap-2.5">
                  <input
                    type="text"
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) void sendMessage(); }}
                    placeholder={`Ask ${twinName} anything…`}
                    disabled={isLoading}
                    aria-label={`Message ${twinName}`}
                    className="flex-1 rounded-[14px] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200/60 disabled:opacity-60 transition-colors"
                  />
                  <button
                    onClick={() => { void sendMessage(); }}
                    disabled={isLoading || !input.trim()}
                    aria-label="Send message"
                    className="cursor-pointer shrink-0 rounded-[14px] bg-[#2563EB] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#1D4ED8] disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Send
                  </button>
                </div>
              </div>
            </div>
          </section>

          {/* Profile details — second in DOM = below chat on mobile, left column on desktop */}
          <div className="order-last lg:order-first space-y-4">
            <Section title="Key Achievements" items={profile?.key_achievements} />
            <Section title="Areas of Expertise" items={expertise} />
            <Section title="Personality Traits" items={profile?.personality_traits} />
            <Section title="Contributions" items={profile?.contributions} />

            {profile?.education && profile.education.length > 0 && (
              <section className="rounded-[24px] border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Education</h2>
                <div className="mt-4 space-y-3">
                  {profile.education.map((entry, index) => (
                    <div key={`education-${index}`} className="rounded-[16px] bg-slate-50 p-4">
                      <p className="font-medium text-slate-900">{entry.degree || entry.field || entry.institution || 'Education'}</p>
                      {entry.institution && <p className="mt-1 text-sm text-slate-600">{entry.institution}</p>}
                      {yearRange(entry.start_year, entry.end_year) && <p className="mt-1 text-xs text-slate-400">{yearRange(entry.start_year, entry.end_year)}</p>}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {profile?.work_experience && profile.work_experience.length > 0 && (
              <section className="rounded-[24px] border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Work Experience</h2>
                <div className="mt-4 space-y-3">
                  {profile.work_experience.map((entry, index) => (
                    <div key={`work-${index}`} className="rounded-[16px] bg-slate-50 p-4">
                      <p className="font-medium text-slate-900">{entry.role || entry.company || 'Experience'}</p>
                      {entry.company && <p className="mt-1 text-sm text-slate-600">{entry.company}</p>}
                      {yearRange(entry.start_year, entry.end_year) && <p className="mt-1 text-xs text-slate-400">{yearRange(entry.start_year, entry.end_year)}</p>}
                      {entry.description && <p className="mt-3 text-sm leading-6 text-slate-600">{entry.description}</p>}
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        </section>
      </main>

      {/* ─── Conversion bar — acquisition surface ─── */}
      <ConversionBar name={twinName} />
    </div>
  );
}
