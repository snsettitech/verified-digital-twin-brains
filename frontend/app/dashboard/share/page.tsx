'use client';

import Link from 'next/link';
import React, { useEffect, useMemo, useState } from 'react';

import { useTwin } from '@/lib/context/TwinContext';
import { API_ENDPOINTS } from '@/lib/constants';
import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';

type ShareLinkInfo = {
  share_token?: string | null;
  share_url?: string | null;
  public_share_enabled?: boolean;
};

type PersonaProfilePack = {
  name?: string;
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
  key_achievements?: string[];
  personality_traits?: string[];
  contributions?: string[];
  speaking_style?: string;
  social_links?: Record<string, string>;
  pinned_questions?: string[];
};

type ProfileInsightsResponse = {
  profile_pack?: PersonaProfilePack | null;
};

const PUBLIC_READY_STATUSES = new Set(['persona_built', 'active']);

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');
}

function normalizeSocialLinks(value: unknown): Record<string, string> {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).filter(([, url]) => typeof url === 'string' && url.trim()),
    ) as Record<string, string>;
  }
  if (!Array.isArray(value)) return {};
  const pairs = value
    .map((item) => (typeof item === 'string' ? item.trim() : ''))
    .filter(Boolean)
    .map((url, index) => [`link${index + 1}`, url] as const);
  return Object.fromEntries(pairs);
}

function lifeLine(profile: PersonaProfilePack | null): string {
  if (!profile) return '';
  const years =
    profile.birth_year || profile.death_year
      ? `${profile.birth_year || ''}${profile.birth_year || profile.death_year ? ' - ' : ''}${profile.death_year || 'Present'}`
      : '';
  if (profile.nationality && years) return `${profile.nationality} • ${years}`;
  return profile.nationality || years;
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

export default function SharePage() {
  const { activeTwin, user } = useTwin();
  const [copied, setCopied] = useState(false);
  const [qrVisible, setQrVisible] = useState(false);
  const [isLoadingLink, setIsLoadingLink] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);
  const [shareInfo, setShareInfo] = useState<ShareLinkInfo | null>(null);
  const [profilePack, setProfilePack] = useState<PersonaProfilePack | null>(null);

  const settings = (activeTwin?.settings || {}) as Record<string, unknown>;
  const handle = typeof settings.handle === 'string' ? settings.handle : '';
  const publicProfile =
    settings.public_profile && typeof settings.public_profile === 'object' && !Array.isArray(settings.public_profile)
      ? (settings.public_profile as Record<string, unknown>)
      : {};

  const isPublicReady = Boolean(activeTwin && (activeTwin.is_active || PUBLIC_READY_STATUSES.has(activeTwin.status)));
  const shareUrl = useMemo(() => shareInfo?.share_url || '', [shareInfo]);

  const fallbackProfile = useMemo<PersonaProfilePack>(() => {
    const displayName =
      (typeof publicProfile.display_name === 'string' && publicProfile.display_name.trim()) ||
      activeTwin?.name ||
      user?.full_name ||
      'Persona';
    const headline = typeof publicProfile.headline === 'string' ? publicProfile.headline.trim() : '';
    const bio =
      (typeof publicProfile.bio === 'string' && publicProfile.bio.trim()) ||
      (typeof settings.public_intro === 'string' ? settings.public_intro : '') ||
      'Add a public summary so visitors know what this persona can help with.';
    const role = typeof publicProfile.role === 'string' ? publicProfile.role.trim() : '';
    const organization = typeof publicProfile.organization === 'string' ? publicProfile.organization.trim() : '';
    const occupation = role && organization ? `${role} at ${organization}` : role || headline || 'Public persona';
    const avatarUrl =
      (typeof publicProfile.avatar_url === 'string' && publicProfile.avatar_url.trim()) ||
      user?.avatar_url ||
      '';

    return {
      name: displayName,
      occupation,
      headline,
      bio,
      short_description: bio,
      avatar_url: avatarUrl,
      verified_profile: typeof publicProfile.verified_profile === 'boolean' ? Boolean(publicProfile.verified_profile) : false,
      speaking_style: typeof publicProfile.speaking_style === 'string' ? publicProfile.speaking_style.trim() : '',
      areas_of_expertise: Array.isArray(publicProfile.areas_of_expertise)
        ? publicProfile.areas_of_expertise.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
        : [],
      key_achievements: Array.isArray(publicProfile.key_achievements)
        ? publicProfile.key_achievements.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
        : [],
      personality_traits: Array.isArray(publicProfile.personality_traits)
        ? publicProfile.personality_traits.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
        : [],
      contributions: Array.isArray(publicProfile.contributions)
        ? publicProfile.contributions.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
        : [],
      pinned_questions: Array.isArray(publicProfile.pinned_questions)
        ? publicProfile.pinned_questions.filter((item): item is string => typeof item === 'string' && item.trim().length > 0).slice(0, 4)
        : [],
      social_links: normalizeSocialLinks(publicProfile.social_links),
    };
  }, [activeTwin?.name, publicProfile, settings.public_intro, user?.avatar_url, user?.full_name]);

  const previewProfile = profilePack || fallbackProfile;
  const socialLinks = Object.entries(previewProfile.social_links || {});

  useEffect(() => {
    let cancelled = false;

    const loadData = async () => {
      if (!activeTwin?.id) {
        setShareInfo(null);
        setProfilePack(null);
        setLinkError(null);
        return;
      }

      setIsLoadingLink(true);
      setLinkError(null);

      try {
        const [shareResponse, insightsResponse] = await Promise.all([
          authFetchStandalone(`/twins/${activeTwin.id}/share-link`),
          authFetchStandalone(API_ENDPOINTS.TWIN_PROFILE_INSIGHTS(activeTwin.id)),
        ]);

        if (!shareResponse.ok) {
          throw new Error(`Failed to load share link (${shareResponse.status})`);
        }

        const sharePayload = (await shareResponse.json()) as ShareLinkInfo;
        const insightsPayload = insightsResponse.ok
          ? ((await insightsResponse.json()) as ProfileInsightsResponse)
          : null;

        if (!cancelled) {
          setShareInfo(sharePayload);
          setProfilePack(insightsPayload?.profile_pack || null);
        }
      } catch (error) {
        console.error('[SharePage] Failed to load public presence data:', error);
        if (!cancelled) {
          setShareInfo(null);
          setProfilePack(null);
          setLinkError('Unable to load the public link right now. Try refreshing in a moment.');
        }
      } finally {
        if (!cancelled) {
          setIsLoadingLink(false);
        }
      }
    };

    void loadData();

    return () => {
      cancelled = true;
    };
  }, [activeTwin?.id]);

  const copyToClipboard = (text: string) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  if (!activeTwin) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-slate-900">Select a Twin</h2>
          <p className="mt-2 text-slate-500">Please select a twin from the sidebar to manage public presence.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-black tracking-tight text-slate-900">Public Presence</h1>
        <p className="mt-1 text-slate-500">
          Preview how {activeTwin.name} appears in the marketplace and from the public link.
        </p>
      </div>

      <section className="rounded-[32px] border border-slate-200 bg-white p-8 shadow-sm">
        <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="flex gap-5">
            {previewProfile.avatar_url ? (
              <img src={previewProfile.avatar_url} alt={previewProfile.name || activeTwin.name} className="h-24 w-24 rounded-[28px] object-cover" />
            ) : (
              <div className="flex h-24 w-24 items-center justify-center rounded-[28px] bg-[linear-gradient(135deg,#f59e0b,#f97316)] text-2xl font-semibold text-white">
                {initials(previewProfile.name || activeTwin.name) || 'P'}
              </div>
            )}

            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="text-4xl font-semibold text-slate-950">{previewProfile.name || activeTwin.name}</h2>
                {previewProfile.verified_profile && (
                  <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">
                    Verified
                  </span>
                )}
                <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${
                  isPublicReady ? 'bg-slate-950 text-white' : 'bg-slate-100 text-slate-600'
                }`}>
                  {isPublicReady ? 'Marketplace ready' : 'Not public yet'}
                </span>
              </div>
              <p className="mt-2 text-lg text-slate-700">
                {previewProfile.occupation || previewProfile.headline || 'Public persona'}
              </p>
              {lifeLine(previewProfile) && <p className="mt-2 text-sm text-slate-500">{lifeLine(previewProfile)}</p>}
              <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
                {previewProfile.short_description || previewProfile.bio}
              </p>

              {socialLinks.length > 0 && (
                <div className="mt-5 flex flex-wrap gap-2">
                  {socialLinks.map(([label, url]) => (
                    <a
                      key={`${label}-${url}`}
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-full bg-slate-100 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-200"
                    >
                      {label}
                    </a>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
            <div className="rounded-[24px] bg-[#f8f5ef] p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Answerability</p>
              <p className="mt-2 text-3xl font-semibold text-slate-950">
                {Math.round(previewProfile.answerability_score || 0)}%
              </p>
            </div>
            <div className="rounded-[24px] bg-[#f8f5ef] p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Verified Claims</p>
              <p className="mt-2 text-3xl font-semibold text-slate-950">
                {previewProfile.verified_claims_count || 0}
              </p>
            </div>
            <div className="rounded-[24px] bg-[#f8f5ef] p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Speaking Style</p>
              <p className="mt-2 text-sm leading-6 text-slate-700">
                {previewProfile.speaking_style || 'Direct, clear, and grounded in the public profile.'}
              </p>
            </div>
          </div>
        </div>

        {isLoadingLink ? (
          <div className="mt-8 text-sm text-slate-500">Preparing your public link...</div>
        ) : linkError ? (
          <div className="mt-8 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {linkError}
          </div>
        ) : isPublicReady && shareUrl ? (
          <>
            <div className="mt-8 flex flex-col gap-3 md:flex-row md:items-center">
              <div className="flex-1 break-all rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 font-mono text-sm text-slate-700">
                {shareUrl}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => copyToClipboard(shareUrl)}
                  className={`rounded-2xl px-6 py-4 text-sm font-semibold transition-colors ${
                    copied ? 'bg-emerald-500 text-white' : 'bg-slate-950 text-white hover:bg-slate-800'
                  }`}
                >
                  {copied ? 'Copied!' : 'Copy Link'}
                </button>
                <a
                  href={shareUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-2xl border border-slate-200 bg-white px-6 py-4 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Open
                </a>
                <button
                  onClick={() => setQrVisible((value) => !value)}
                  className="rounded-2xl border border-slate-200 bg-white px-4 py-4 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                >
                  QR
                </button>
              </div>
            </div>

            {qrVisible && (
              <div className="mt-6 rounded-[28px] border border-slate-200 bg-slate-50 p-6">
                <div className="flex flex-col items-center justify-center">
                  <div className="rounded-2xl border border-slate-200 bg-white p-2">
                    <img
                      src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(shareUrl)}`}
                      alt="QR Code"
                      className="h-44 w-44"
                    />
                  </div>
                  <p className="mt-4 text-sm text-slate-500">Scan to open {activeTwin.name} in public chat.</p>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="mt-8 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600">
            This persona is not public yet. Once it reaches `persona_built` or `active`, the direct link will appear here automatically.
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Areas of Expertise" items={previewProfile.areas_of_expertise} />
        <Section title="Key Achievements" items={previewProfile.key_achievements} />
        <Section title="Personality Traits" items={previewProfile.personality_traits} />
        <Section title="Contributions" items={previewProfile.contributions} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">Pinned Questions</h3>
          <div className="mt-4 space-y-3">
            {(previewProfile.pinned_questions || []).slice(0, 4).map((question, index) => (
              <div key={`${question}-${index}`} className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
                {question}
              </div>
            ))}
            {(!previewProfile.pinned_questions || previewProfile.pinned_questions.length === 0) && (
              <p className="text-sm text-slate-500">Add pinned questions in the profile editor to make the chat start stronger.</p>
            )}
          </div>
        </div>

        <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">Shape the Listing</h3>
          <p className="mt-3 text-sm leading-6 text-slate-500">
            Your public profile fields, expertise tags, and starter questions are what make the marketplace card feel clean and credible.
          </p>
          <Link
            href="/dashboard/profile"
            className="mt-6 inline-flex items-center rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
          >
            Edit public profile
          </Link>
        </div>

        <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">Handle and Discovery</h3>
          <p className="mt-3 font-mono text-sm text-slate-700">{handle ? `@${handle}` : 'No custom handle yet'}</p>
          <p className="mt-3 text-sm leading-6 text-slate-500">
            Use a handle for a cleaner public URL. Without it, the system will fall back to a secure tokenized share link.
          </p>
          <div className="mt-6 flex gap-3">
            <Link
              href="/dashboard/settings"
              className="inline-flex items-center rounded-xl bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-200"
            >
              Manage handle
            </Link>
            <Link
              href="/marketplace"
              className="inline-flex items-center rounded-xl bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-200"
            >
              Open marketplace
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
