'use client';

import Link from 'next/link';
import React, { useEffect, useMemo, useState } from 'react';

import { useTwin } from '@/lib/context/TwinContext';
import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';

type ShareLinkInfo = {
  share_token?: string | null;
  share_url?: string | null;
  public_share_enabled?: boolean;
};

const PUBLIC_READY_STATUSES = new Set(['persona_built', 'active']);

export default function SharePage() {
  const { activeTwin } = useTwin();
  const [copied, setCopied] = useState(false);
  const [qrVisible, setQrVisible] = useState(false);
  const [isLoadingLink, setIsLoadingLink] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);
  const [shareInfo, setShareInfo] = useState<ShareLinkInfo | null>(null);

  const settings = (activeTwin?.settings || {}) as Record<string, unknown>;
  const handle = typeof settings.handle === 'string' ? settings.handle : '';
  const publicProfile = (settings.public_profile || {}) as Record<string, unknown>;

  const isPublicReady = Boolean(
    activeTwin && (activeTwin.is_active || PUBLIC_READY_STATUSES.has(activeTwin.status))
  );

  const shareUrl = useMemo(() => shareInfo?.share_url || '', [shareInfo]);
  const profileSummary = useMemo(() => {
    const headline = typeof publicProfile.headline === 'string' ? publicProfile.headline : '';
    const bio = typeof publicProfile.bio === 'string' ? publicProfile.bio : '';
    return headline || bio || 'Add a headline, bio, and pinned questions to improve how your persona appears in the marketplace.';
  }, [publicProfile]);

  useEffect(() => {
    let cancelled = false;

    const loadShareInfo = async () => {
      if (!activeTwin?.id) {
        setShareInfo(null);
        setLinkError(null);
        return;
      }

      setIsLoadingLink(true);
      setLinkError(null);

      try {
        const response = await authFetchStandalone(`/twins/${activeTwin.id}/share-link`);
        if (!response.ok) {
          throw new Error(`Failed to load share link (${response.status})`);
        }

        const payload = (await response.json()) as ShareLinkInfo;
        if (!cancelled) {
          setShareInfo(payload);
        }
      } catch (error) {
        console.error('[SharePage] Failed to load share link:', error);
        if (!cancelled) {
          setShareInfo(null);
          setLinkError('Unable to load the public link right now. Try refreshing in a moment.');
        }
      } finally {
        if (!cancelled) {
          setIsLoadingLink(false);
        }
      }
    };

    void loadShareInfo();

    return () => {
      cancelled = true;
    };
  }, [activeTwin?.id]);

  const copyToClipboard = (text: string) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!activeTwin) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354l1.1 3.356h3.526l-2.853 2.073 1.1 3.356-2.853-2.073-2.853 2.073 1.1-3.356-2.853-2.073h3.526L12 4.354z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-slate-900">Select a Twin</h2>
          <p className="text-slate-500">Please select a twin from the sidebar to manage sharing.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-black tracking-tight text-slate-900">Public Presence</h1>
        <p className="text-slate-500 mt-1">
          Manage the public link, handle, and marketplace presentation for {activeTwin.name}.
        </p>
      </div>

      <div className={`rounded-3xl p-8 text-white transition-all duration-500 ${
        isPublicReady
          ? 'bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-600 shadow-xl shadow-indigo-500/20'
          : 'bg-slate-800'
      }`}>
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-2xl">
            <div className="flex items-center gap-2 mb-3">
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                isPublicReady ? 'bg-emerald-500 text-white' : 'bg-slate-600 text-slate-300'
              }`}>
                {isPublicReady ? 'Public to all users' : 'Not public yet'}
              </span>
              <h2 className="text-xl font-bold">Marketplace and direct link</h2>
            </div>
            <p className={`${isPublicReady ? 'text-indigo-100' : 'text-slate-400'} text-sm leading-6`}>
              {isPublicReady
                ? 'Public-ready personas are discoverable to everyone in the marketplace. This page gives you the direct chat link, your handle route, and the profile fields that shape how you appear.'
                : 'This persona is not public yet. Once it reaches persona built or active, it will appear in the marketplace automatically and get a direct public chat link.'}
            </p>
            <p className={`${isPublicReady ? 'text-indigo-200/90' : 'text-slate-500'} mt-4 text-sm leading-6`}>
              {profileSummary}
            </p>
          </div>

          <div className="rounded-3xl border border-white/15 bg-white/10 px-5 py-4 backdrop-blur-md">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-white/70">Current handle</p>
            <p className="mt-2 font-mono text-lg text-white">{handle ? `@${handle}` : 'No custom handle yet'}</p>
            <p className="mt-2 max-w-xs text-sm text-white/75">
              Add a handle in settings if you want a clean public URL instead of a tokenized link.
            </p>
          </div>
        </div>

        {isLoadingLink ? (
          <div className="mt-8 flex items-center gap-3 text-sm text-indigo-100">
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Preparing your public link…
          </div>
        ) : linkError ? (
          <div className="mt-8 rounded-2xl border border-rose-300/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
            {linkError}
          </div>
        ) : isPublicReady && shareUrl ? (
          <>
            <div className="mt-8 flex flex-col md:flex-row items-stretch md:items-center gap-3">
              <div className="flex-1 px-4 py-4 bg-white/10 backdrop-blur-md border border-white/20 rounded-2xl text-white font-mono text-sm break-all">
                {shareUrl}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => copyToClipboard(shareUrl)}
                  className={`flex-1 md:flex-none px-8 py-4 rounded-2xl font-bold text-sm transition-all ${
                    copied
                      ? 'bg-emerald-500 text-white'
                      : 'bg-white text-slate-900 hover:bg-slate-100 shadow-xl'
                  }`}
                >
                  {copied ? 'Copied!' : 'Copy Link'}
                </button>
                <a
                  href={shareUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="px-6 py-4 rounded-2xl bg-white/10 hover:bg-white/20 border border-white/20 text-sm font-bold text-white transition-colors"
                >
                  Open
                </a>
                <button
                  onClick={() => setQrVisible(!qrVisible)}
                  className="p-4 bg-white/10 hover:bg-white/20 rounded-2xl transition-colors border border-white/20"
                  aria-label="Toggle QR code"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
                  </svg>
                </button>
              </div>
            </div>

            {qrVisible && (
              <div className="mt-6 p-6 bg-white rounded-3xl flex flex-col items-center justify-center animate-in fade-in slide-in-from-top-4">
                <div className="w-48 h-48 bg-white rounded-2xl flex items-center justify-center mb-4 border-2 border-slate-200 p-2">
                  <img
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(shareUrl)}`}
                    alt="QR Code"
                    className="w-full h-full"
                  />
                </div>
                <p className="text-slate-500 font-medium">
                  Scan to open {activeTwin?.name || 'your persona'} in the public chat.
                </p>
              </div>
            )}
          </>
        ) : null}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="bg-white rounded-3xl border border-slate-200 p-6">
          <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-2xl flex items-center justify-center mb-4">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          </div>
          <h3 className="text-lg font-bold text-slate-900 mb-2">Marketplace visibility</h3>
          <p className="text-slate-500 text-sm leading-6">
            Every public-ready persona is discoverable in the shared marketplace. Ranking is quality-first, so stronger profiles with clearer public topics surface higher.
          </p>
          <Link
            href="/marketplace"
            className="mt-6 inline-flex items-center rounded-xl bg-slate-900 px-4 py-2 text-sm font-bold text-white hover:bg-slate-800 transition-colors"
          >
            Open marketplace
          </Link>
        </div>

        <div className="bg-white rounded-3xl border border-slate-200 p-6">
          <div className="w-12 h-12 bg-purple-50 text-purple-600 rounded-2xl flex items-center justify-center mb-4">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h3 className="text-lg font-bold text-slate-900 mb-2">Shape your listing</h3>
          <p className="text-slate-500 text-sm leading-6">
            Your display name, headline, bio, avatar, and pinned questions come from the profile editor. That is what people see before they start a conversation.
          </p>
          <Link
            href="/dashboard/profile"
            className="mt-6 inline-flex items-center rounded-xl bg-slate-100 px-4 py-2 text-sm font-bold text-slate-800 hover:bg-slate-200 transition-colors"
          >
            Edit public profile
          </Link>
        </div>

        <div className="bg-white rounded-3xl border border-slate-200 p-6">
          <div className="w-12 h-12 bg-emerald-50 text-emerald-600 rounded-2xl flex items-center justify-center mb-4">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
          </div>
          <h3 className="text-lg font-bold text-slate-900 mb-2">Custom handle and direct link</h3>
          <p className="text-slate-500 text-sm leading-6">
            Use a handle for a clean public URL. If you do not set one, the system falls back to a tokenized link automatically.
          </p>
          <Link
            href="/dashboard/settings"
            className="mt-6 inline-flex items-center rounded-xl bg-slate-100 px-4 py-2 text-sm font-bold text-slate-800 hover:bg-slate-200 transition-colors"
          >
            Manage handle
          </Link>
        </div>
      </div>
    </div>
  );
}
