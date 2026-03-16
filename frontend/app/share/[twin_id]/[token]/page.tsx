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
  confidence_score?: number;
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
  answerability_score?: number;
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
  if (start && end) return `${start} - ${end}`;
  if (start) return `${start} - Present`;
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

function Section({ title, items }: { title: string; items?: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">{title}</h2>
      <div className="mt-4 flex flex-wrap gap-2">
        {items.map((item) => (
          <span key={`${title}-${item}`} className="rounded-full bg-slate-100 px-3 py-1.5 text-sm text-slate-700">
            {item}
          </span>
        ))}
      </div>
    </section>
  );
}

export default function PublicSharePage() {
  const params = useParams();
  const twinId = params?.twin_id as string;
  const shareToken = params?.token as string;
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
      localStorage.setItem(storageKey, JSON.stringify(messages));
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
        const response = await fetch(`${apiBaseUrl}/public/validate-share/${twinId}/${shareToken}`);
        if (!response.ok) {
          setIsValid(false);
          setError('This share link is invalid or has expired.');
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
            confidence_score: data.confidence_score,
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

  if (isValid === null) {
    return <div className="flex min-h-screen items-center justify-center bg-[#f6f2ea] text-sm text-slate-500">Loading...</div>;
  }

  if (!isValid) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f6f2ea] p-4">
        <div className="w-full max-w-md rounded-[28px] border border-slate-200 bg-white p-8 text-center shadow-sm">
          <h1 className="text-2xl font-semibold text-slate-950">Link not found</h1>
          <p className="mt-2 text-slate-500">{error}</p>
        </div>
      </div>
    );
  }

  const summary = profile?.short_description || profile?.bio || `${twinName} is available for public conversations grounded in published profile information.`;
  const expertise = profile?.areas_of_expertise || [];
  const socials = Object.entries(profile?.social_links || {});

  return (
    <div className="min-h-screen bg-[#f6f2ea] text-slate-950">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_top_left,rgba(251,191,36,0.18),transparent_28%),radial-gradient(circle_at_88%_12%,rgba(15,118,110,0.10),transparent_24%)]" />

      <header className="relative border-b border-slate-200/80 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 lg:px-10">
          <div className="flex items-center gap-4">
            <Link href="/marketplace" className="text-sm font-medium text-slate-600 hover:text-slate-950">Marketplace</Link>
            <span className="text-sm text-slate-300">/</span>
            <span className="text-sm font-medium text-slate-950">{twinName}</span>
          </div>
          <div className="text-sm text-slate-500">Public share profile</div>
        </div>
      </header>

      <main className="relative mx-auto max-w-7xl px-6 pb-16 pt-10 lg:px-10">
        <section className="rounded-[32px] border border-slate-200 bg-white p-8 shadow-sm">
          <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="flex gap-5">
              {profile?.avatar_url ? (
                <img src={profile.avatar_url} alt={twinName} className="h-24 w-24 rounded-[28px] object-cover" />
              ) : (
                <div className="flex h-24 w-24 items-center justify-center rounded-[28px] bg-[linear-gradient(135deg,#f59e0b,#f97316)] text-2xl font-semibold text-white">
                  {initials(twinName) || 'P'}
                </div>
              )}
              <div>
                <div className="flex flex-wrap items-center gap-3">
                  <h1 className="text-4xl font-semibold text-slate-950">{twinName}</h1>
                  {Boolean(profile?.verified_profile) && (
                    <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">Verified</span>
                  )}
                </div>
                <p className="mt-2 text-lg text-slate-700">{profile?.occupation || profile?.headline || 'Public digital persona'}</p>
                {lifeLine(profile) && <p className="mt-2 text-sm text-slate-500">{lifeLine(profile)}</p>}
                <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">{summary}</p>
                {socials.length > 0 && (
                  <div className="mt-5 flex flex-wrap gap-2">
                    {socials.map(([label, url]) => (
                      <a key={`${label}-${url}`} href={url} target="_blank" rel="noreferrer" className="rounded-full bg-slate-100 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-200">
                        {socialLabel(label)}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
              <div className="rounded-[24px] bg-[#f8f5ef] p-5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Answerability</p>
                <p className="mt-2 text-3xl font-semibold text-slate-950">{Math.round(profile?.answerability_score || 0)}%</p>
              </div>
              <div className="rounded-[24px] bg-[#f8f5ef] p-5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Verified Claims</p>
                <p className="mt-2 text-3xl font-semibold text-slate-950">{profile?.verified_claims_count || 0}</p>
              </div>
              <div className="rounded-[24px] bg-[#f8f5ef] p-5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Speaking Style</p>
                <p className="mt-2 text-sm leading-6 text-slate-700">{profile?.speaking_style || 'Direct, clear, and grounded in the public profile.'}</p>
              </div>
            </div>
          </div>
        </section>

        <section className="mt-8 grid gap-8 lg:grid-cols-[0.92fr_1.08fr]">
          <div className="space-y-6">
            <Section title="Key Achievements" items={profile?.key_achievements} />
            <Section title="Areas of Expertise" items={expertise} />
            <Section title="Personality Traits" items={profile?.personality_traits} />
            <Section title="Contributions" items={profile?.contributions} />

            {profile?.education && profile.education.length > 0 && (
              <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">Education</h2>
                <div className="mt-4 space-y-4">
                  {profile.education.map((entry, index) => (
                    <div key={`education-${index}`} className="rounded-2xl bg-slate-50 p-4">
                      <p className="font-medium text-slate-950">{entry.degree || entry.field || entry.institution || 'Education'}</p>
                      {entry.institution && <p className="mt-1 text-sm text-slate-600">{entry.institution}</p>}
                      {yearRange(entry.start_year, entry.end_year) && <p className="mt-1 text-sm text-slate-500">{yearRange(entry.start_year, entry.end_year)}</p>}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {profile?.work_experience && profile.work_experience.length > 0 && (
              <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">Work Experience</h2>
                <div className="mt-4 space-y-4">
                  {profile.work_experience.map((entry, index) => (
                    <div key={`work-${index}`} className="rounded-2xl bg-slate-50 p-4">
                      <p className="font-medium text-slate-950">{entry.role || entry.company || 'Experience'}</p>
                      {entry.company && <p className="mt-1 text-sm text-slate-600">{entry.company}</p>}
                      {yearRange(entry.start_year, entry.end_year) && <p className="mt-1 text-sm text-slate-500">{yearRange(entry.start_year, entry.end_year)}</p>}
                      {entry.description && <p className="mt-3 text-sm leading-6 text-slate-600">{entry.description}</p>}
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>

          <section className="lg:sticky lg:top-6">
            <div className="flex h-[72vh] min-h-[680px] flex-col overflow-hidden rounded-[32px] border border-slate-200 bg-white shadow-sm">
              <div className="border-b border-slate-200 px-6 py-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xl font-semibold text-slate-950">{twinName}</p>
                    <p className="mt-1 text-sm text-slate-600">{profile?.occupation || profile?.headline || 'Public persona chat'}</p>
                  </div>
                  {messages.length > 0 && (
                    <button onClick={clearHistory} className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-slate-950">
                      Clear
                    </button>
                  )}
                </div>
                <div className="mt-4 rounded-2xl bg-[#f8f5ef] px-4 py-3 text-sm text-slate-600">
                  Public share mode: responses are limited to published knowledge and profile facts.
                  {profile?.citations_enabled === false ? '' : ' Citations appear when available.'}
                </div>
              </div>

              <div className="flex-1 overflow-y-auto px-6 py-6">
                {messages.length === 0 ? (
                  <div className="flex h-full flex-col items-center justify-center text-center">
                    <div className="flex h-20 w-20 items-center justify-center rounded-[28px] bg-slate-100 text-slate-700">
                      <svg className="h-10 w-10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg>
                    </div>
                    <h3 className="mt-6 text-2xl font-semibold text-slate-950">Start a Conversation</h3>
                    <p className="mt-3 max-w-md text-sm leading-6 text-slate-500">Ask about background, work, expertise, and the public profile details shown on this page.</p>
                    <div className="mt-6 flex max-w-lg flex-wrap justify-center gap-2">
                      {suggestedQuestions.map((question) => (
                        <button key={question} onClick={() => { setInput(question); window.setTimeout(() => { void sendMessage(question); }, 100); }} className="rounded-full bg-slate-100 px-4 py-2 text-sm text-slate-700 hover:bg-slate-200">
                          {question}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {messages.map((message, index) => (
                      <div key={`${message.role}-${index}`} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[85%] rounded-[24px] px-4 py-3 ${message.role === 'user' ? 'bg-slate-950 text-white' : message.isError ? 'border border-rose-200 bg-rose-50 text-rose-700' : 'border border-slate-200 bg-slate-50 text-slate-800'}`}>
                          <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
                          {message.role === 'assistant' && !message.isError && (
                            <div className="mt-3 border-t border-slate-200 pt-3">
                              <div className="flex flex-wrap gap-2">
                                {message.confidence_score !== undefined && <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-700">{(message.confidence_score * 100).toFixed(0)}%</span>}
                                {message.citations?.map((source, citationIndex) => {
                                  const detail = message.citation_details?.[citationIndex];
                                  const label = detail?.filename || source || `Source ${citationIndex + 1}`;
                                  const href = detail?.citation_url || undefined;
                                  return (
                                    <span key={`${label}-${citationIndex}`} className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 ring-1 ring-slate-200">
                                      {href ? <a href={href} target="_blank" rel="noreferrer" className="hover:text-slate-950 hover:underline">{label}</a> : <span>{label}</span>}
                                    </span>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                    {isLoading && <div className="rounded-[24px] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">Generating response...</div>}
                    <div ref={messagesEndRef} />
                  </div>
                )}
              </div>

              {requestError && requestError.canRetry && !isLoading && (
                <div className="border-t border-rose-200 bg-rose-50 px-6 py-3">
                  <div className="flex items-center justify-between gap-4">
                    <p className="text-sm text-rose-700">{requestError.message}</p>
                    <button onClick={retryLastMessage} className="rounded-xl border border-rose-200 px-4 py-2 text-sm font-medium text-rose-700 hover:bg-rose-100">Retry</button>
                  </div>
                </div>
              )}

              <div className="border-t border-slate-200 p-4">
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) void sendMessage(); }}
                    placeholder="Type your message..."
                    disabled={isLoading}
                    className="flex-1 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-950 placeholder:text-slate-400 focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-200 disabled:opacity-60"
                  />
                  <button onClick={() => { void sendMessage(); }} disabled={isLoading || !input.trim()} className="rounded-2xl bg-slate-950 px-5 py-3 text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50">
                    Send
                  </button>
                </div>
              </div>
            </div>
          </section>
        </section>
      </main>
    </div>
  );
}
