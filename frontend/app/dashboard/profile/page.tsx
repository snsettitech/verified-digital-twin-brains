'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTwin } from '@/lib/context/TwinContext';
import { API_ENDPOINTS } from '@/lib/constants';
import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';
import { useToast } from '@/components/ui';

type ProfileDraft = {
  displayName: string;
  organization: string;
  role: string;
  headline: string;
  bio: string;
  pinnedQuestions: string[];
  socialLinks: string[];
  profileVideoEnabled: boolean;
  avatarUrl: string;
  mindLabel: string;
};

const DEFAULT_PINNED_QUESTIONS = [
  'What inspired you to start this project?',
  'What should people know about your style and approach?',
  'What are the best ways to connect with you?',
];

const DEFAULT_SOCIAL_LINKS = ['instagram.com/', 'linkedin.com/in/', 'youtube.com/@', 'tiktok.com/@'];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function normalizeStringArray(
  value: unknown,
  fallback: string[] = [],
  max = Number.POSITIVE_INFINITY
): string[] {
  if (!Array.isArray(value)) return [...fallback];
  const cleaned = value
    .map((item) => (typeof item === 'string' ? item.trim() : ''))
    .filter((item) => item.length > 0);
  const next = cleaned.slice(0, max);
  return next.length > 0 ? next : [...fallback];
}

function firstName(fullName: string): string {
  const parts = fullName.trim().split(/\s+/);
  return parts[0] || 'Creator';
}

function initials(fullName: string): string {
  const letters = fullName
    .trim()
    .split(/\s+/)
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2);
  return letters.join('').toUpperCase() || 'DT';
}

function IconUser() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5.121 17.804A9.002 9.002 0 1112 21a8.96 8.96 0 01-6.879-3.196z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0zM6.7 18.2a6 6 0 0110.6 0" />
    </svg>
  );
}

function IconShare() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.684 13.342A3 3 0 119 12m-.316 1.342L15.316 16.658m-6.632-6 6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684m0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
    </svg>
  );
}

function IconPlus() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
    </svg>
  );
}

function IconClose() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function IconChevronUp() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="m18 15-6-6-6 6" />
    </svg>
  );
}

function IconLock() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm3-10V7a3 3 0 016 0v4H9z" />
    </svg>
  );
}

function IconChat() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
    </svg>
  );
}

export default function ProfilePage() {
  const { activeTwin, user, refreshTwins, isLoading } = useTwin();
  const { showToast } = useToast();
  const router = useRouter();

  const derivedProfile = useMemo<ProfileDraft>(() => {
    const settings = isRecord(activeTwin?.settings) ? activeTwin.settings : {};
    const profile = isRecord(settings.public_profile) ? settings.public_profile : {};
    const tagline = typeof settings.tagline === 'string' ? settings.tagline : '';
    const publicIntro = typeof settings.public_intro === 'string' ? settings.public_intro : '';
    const displayName =
      (typeof profile.display_name === 'string' && profile.display_name.trim()) ||
      activeTwin?.name ||
      user?.full_name ||
      'Digital Twin';

    const organization =
      (typeof profile.organization === 'string' && profile.organization.trim()) || '';
    const role = (typeof profile.role === 'string' && profile.role.trim()) || '';
    const headline =
      (typeof profile.headline === 'string' && profile.headline.trim()) || tagline || '';
    const bio =
      (typeof profile.bio === 'string' && profile.bio.trim()) ||
      publicIntro ||
      'Add a short bio so visitors know what this twin can help with.';
    const pinnedQuestions = normalizeStringArray(profile.pinned_questions, DEFAULT_PINNED_QUESTIONS, 5);
    const socialLinks = normalizeStringArray(profile.social_links, DEFAULT_SOCIAL_LINKS, 8);
    const profileVideoEnabled =
      typeof profile.profile_video_enabled === 'boolean' ? profile.profile_video_enabled : true;
    const avatarUrl =
      (typeof profile.avatar_url === 'string' && profile.avatar_url.trim()) ||
      user?.avatar_url ||
      '';
    const mindLabel =
      (typeof profile.mind_label === 'string' && profile.mind_label.trim()) ||
      '16.5K Mind';

    return {
      displayName,
      organization,
      role,
      headline,
      bio,
      pinnedQuestions,
      socialLinks,
      profileVideoEnabled,
      avatarUrl,
      mindLabel,
    };
  }, [activeTwin?.name, activeTwin?.settings, user?.avatar_url, user?.full_name]);

  const [draft, setDraft] = useState<ProfileDraft>(derivedProfile);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setDraft(derivedProfile);
    setIsEditing(false);
  }, [derivedProfile]);

  const handleAddQuestion = () => {
    setDraft((prev) => {
      if (prev.pinnedQuestions.length >= 5) return prev;
      return { ...prev, pinnedQuestions: [...prev.pinnedQuestions, ''] };
    });
  };

  const handleUpdateQuestion = (idx: number, value: string) => {
    setDraft((prev) => ({
      ...prev,
      pinnedQuestions: prev.pinnedQuestions.map((item, itemIdx) => (itemIdx === idx ? value : item)),
    }));
  };

  const handleRemoveQuestion = (idx: number) => {
    setDraft((prev) => ({
      ...prev,
      pinnedQuestions: prev.pinnedQuestions.filter((_, itemIdx) => itemIdx !== idx),
    }));
  };

  const handleAddLink = () => {
    setDraft((prev) => ({ ...prev, socialLinks: [...prev.socialLinks, ''] }));
  };

  const handleUpdateLink = (idx: number, value: string) => {
    setDraft((prev) => ({
      ...prev,
      socialLinks: prev.socialLinks.map((item, itemIdx) => (itemIdx === idx ? value : item)),
    }));
  };

  const handleRemoveLink = (idx: number) => {
    setDraft((prev) => ({
      ...prev,
      socialLinks: prev.socialLinks.filter((_, itemIdx) => itemIdx !== idx),
    }));
  };

  const handleOpenShare = () => {
    router.push('/dashboard/share');
  };

  const handleOpenChat = () => {
    router.push('/dashboard/chat');
  };

  const handleBioAssist = (mode: 'highlight' | 'generate') => {
    if (mode === 'highlight') {
      showToast('Highlighting support is coming soon.', 'info');
      return;
    }
    showToast('Bio generation support is coming soon.', 'info');
  };

  const handleSave = async () => {
    if (!activeTwin) return;

    const cleanedPinned = draft.pinnedQuestions
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
      .slice(0, 5);

    const cleanedSocial = draft.socialLinks
      .map((item) => item.trim())
      .filter((item) => item.length > 0);

    const currentSettings = isRecord(activeTwin.settings) ? activeTwin.settings : {};
    const currentProfile = isRecord(currentSettings.public_profile) ? currentSettings.public_profile : {};

    const nextSettings = {
      ...currentSettings,
      public_profile: {
        ...currentProfile,
        display_name: draft.displayName.trim(),
        organization: draft.organization.trim(),
        role: draft.role.trim(),
        headline: draft.headline.trim(),
        bio: draft.bio.trim(),
        pinned_questions: cleanedPinned,
        social_links: cleanedSocial,
        profile_video_enabled: draft.profileVideoEnabled,
        avatar_url: draft.avatarUrl.trim(),
        mind_label: draft.mindLabel.trim() || '16.5K Mind',
      },
    };

    setIsSaving(true);
    try {
      const response = await authFetchStandalone(API_ENDPOINTS.TWIN_DETAIL(activeTwin.id), {
        method: 'PATCH',
        body: JSON.stringify({ settings: nextSettings }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Failed to save profile settings');
      }

      await refreshTwins();
      setIsEditing(false);
      showToast('Profile updated', 'success');
    } catch (error) {
      console.error('[Profile] Failed to save settings:', error);
      showToast('Failed to save profile', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-orange-500 border-t-transparent" />
      </div>
    );
  }

  if (!activeTwin) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-8">
        <h2 className="text-xl font-bold text-slate-900">No Twin Selected</h2>
        <p className="mt-2 text-sm text-slate-600">Select a twin from the sidebar to customize your profile.</p>
      </div>
    );
  }

  return (
    <div className="-mx-4 min-h-[calc(100vh-8rem)] bg-[#f3f1ef] px-4 pb-28 pt-4 md:-mx-8 md:px-8 md:pt-8">
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="flex items-center justify-between">
          <div className="inline-flex items-center gap-3 rounded-full bg-white/80 px-4 py-2 text-sm font-medium text-slate-700 shadow-sm">
            <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-slate-900 text-white">
              <IconUser />
            </span>
            <span>Profile</span>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1.5 text-xs font-semibold text-slate-600 shadow-sm">
            <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
            {draft.mindLabel}
          </div>
        </div>

        <section className="relative overflow-hidden rounded-[32px] border border-white/70 bg-white/80 p-6 shadow-[0_20px_55px_rgba(15,23,42,0.08)] backdrop-blur-sm md:p-10">
          <div className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-gradient-to-br from-orange-100/80 to-amber-100/40 blur-3xl" />
          <div className="pointer-events-none absolute -left-12 -bottom-20 h-44 w-44 rounded-full bg-gradient-to-br from-slate-100/70 to-white/30 blur-3xl" />

          <div className="relative flex flex-col gap-8">
            <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
              <div className="flex flex-col gap-5">
                <div className="h-36 w-36 overflow-hidden rounded-[30px] bg-gradient-to-br from-slate-300 to-slate-100 shadow-lg shadow-slate-900/10">
                  {draft.avatarUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={draft.avatarUrl} alt={draft.displayName} className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-slate-800 to-slate-600 text-4xl font-bold text-white">
                      {initials(draft.displayName)}
                    </div>
                  )}
                </div>
                <div className="space-y-3">
                  <h1 className="text-4xl font-black tracking-tight text-slate-900 md:text-6xl">{draft.displayName}</h1>
                  <div className="flex flex-wrap items-center gap-3 text-lg text-slate-600">
                    <span className="inline-flex items-center gap-2 rounded-full bg-[#f2f0ec] px-3 py-1 text-sm font-semibold text-slate-700">
                      <span className="inline-block h-2.5 w-2.5 rounded-full bg-orange-500" />
                      {draft.headline || 'Add a headline in edit mode'}
                    </span>
                    <span className="text-sm font-semibold text-slate-500">|</span>
                    <span className="text-sm font-semibold text-slate-600">{draft.mindLabel}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                {isEditing ? (
                  <>
                    <button
                      onClick={() => {
                        setDraft(derivedProfile);
                        setIsEditing(false);
                      }}
                      className="rounded-full bg-[#f1efec] px-5 py-2 text-base font-semibold text-slate-700 transition hover:bg-[#e7e3de]"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSave}
                      disabled={isSaving}
                      className="rounded-full bg-gradient-to-r from-orange-500 to-amber-500 px-6 py-2 text-base font-semibold text-white shadow-md shadow-orange-500/25 transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-70"
                    >
                      {isSaving ? 'Saving...' : 'Save'}
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => setIsEditing(true)}
                      className="rounded-full bg-[#f1efec] px-6 py-2 text-base font-semibold text-slate-700 transition hover:bg-[#e7e3de]"
                    >
                      Edit
                    </button>
                    <button
                      onClick={handleOpenShare}
                      className="inline-flex items-center gap-2 rounded-full bg-[#f1efec] px-6 py-2 text-base font-semibold text-slate-700 transition hover:bg-[#e7e3de]"
                    >
                      <IconShare />
                      Share
                    </button>
                  </>
                )}
              </div>
            </div>

            {!isEditing && (
              <div className="relative flex flex-col gap-6 xl:pr-72">
                <p className="max-w-3xl text-xl leading-relaxed text-slate-700">{draft.bio}</p>
                <div className="hidden rounded-3xl bg-gradient-to-br from-orange-500 to-amber-500 p-6 text-white shadow-lg shadow-orange-500/20 xl:absolute xl:bottom-0 xl:right-0 xl:block xl:w-64">
                  <p className="text-2xl font-bold">Call {firstName(draft.displayName)}</p>
                  <p className="mt-1 text-sm text-orange-100">Have a live conversation with your digital twin.</p>
                  <button
                    onClick={handleOpenChat}
                    className="mt-4 w-full rounded-full bg-white/20 px-4 py-2 text-sm font-semibold backdrop-blur transition hover:bg-white/30"
                  >
                    Open Chat
                  </button>
                </div>
              </div>
            )}
          </div>
        </section>

        {!isEditing ? (
          <div className="space-y-8 pb-12">
            <section className="rounded-3xl border border-white/60 bg-white/75 p-6 shadow-[0_10px_30px_rgba(15,23,42,0.05)]">
              <div className="mb-4 flex items-baseline gap-3">
                <h2 className="text-2xl font-bold text-slate-900">Pinned Questions</h2>
                <span className="text-sm font-medium text-slate-500">Max 5 questions</span>
              </div>
              <div className="space-y-3">
                {draft.pinnedQuestions.map((question, idx) => (
                  <div key={`${question}-${idx}`} className="rounded-2xl border border-slate-200 bg-[#f9f8f6] px-5 py-4 text-lg text-slate-800 shadow-sm">
                    {question}
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-3xl border border-white/60 bg-white/75 p-6 shadow-[0_10px_30px_rgba(15,23,42,0.05)]">
              <h2 className="text-2xl font-bold text-slate-900">Follow {firstName(draft.displayName)} for more...</h2>
              <div className="mt-4 flex flex-wrap gap-3">
                {draft.socialLinks.map((link, idx) => (
                  <a
                    key={`${link}-${idx}`}
                    href={link.startsWith('http') ? link : `https://${link}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
                  >
                    {link}
                  </a>
                ))}
              </div>
              <p className="mt-8 text-sm text-slate-500">(c) 2026 Delphi | Terms | Privacy</p>
            </section>
          </div>
        ) : (
          <section className="space-y-6 rounded-3xl border border-white/60 bg-white/80 p-6 shadow-[0_10px_30px_rgba(15,23,42,0.05)] md:p-8">
            <div>
              <label className="mb-2 block text-sm font-semibold text-slate-700">Name</label>
              <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-[#f7f5f2] px-5 py-3">
                <span className="text-lg font-medium text-slate-600">{draft.displayName}</span>
                <span className="inline-flex items-center gap-2 text-sm text-slate-500">
                  <IconLock />
                  Contact support
                </span>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm font-semibold text-slate-700">Organization</label>
                <input
                  type="text"
                  value={draft.organization}
                  onChange={(event) => setDraft((prev) => ({ ...prev, organization: event.target.value }))}
                  placeholder="Your company or brand"
                  className="w-full rounded-2xl border border-slate-200 bg-[#fdfdfc] px-5 py-3 text-lg text-slate-700 focus:border-orange-300 focus:outline-none focus:ring-2 focus:ring-orange-100"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-semibold text-slate-700">Role</label>
                <input
                  type="text"
                  value={draft.role}
                  onChange={(event) => setDraft((prev) => ({ ...prev, role: event.target.value }))}
                  placeholder="Role"
                  className="w-full rounded-2xl border border-slate-200 bg-[#fdfdfc] px-5 py-3 text-lg text-slate-700 focus:border-orange-300 focus:outline-none focus:ring-2 focus:ring-orange-100"
                />
              </div>
            </div>

            <div>
              <label className="mb-2 block text-sm font-semibold text-slate-700">Headline</label>
              <input
                type="text"
                value={draft.headline}
                onChange={(event) => setDraft((prev) => ({ ...prev, headline: event.target.value }))}
                placeholder="Headline"
                className="w-full rounded-2xl border border-slate-200 bg-[#fdfdfc] px-5 py-3 text-lg text-slate-700 focus:border-orange-300 focus:outline-none focus:ring-2 focus:ring-orange-100"
              />
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className="block text-sm font-semibold text-slate-700">Bio</label>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleBioAssist('highlight')}
                    className="rounded-full border border-slate-200 bg-[#f5f4f1] px-3 py-1 text-xs font-semibold text-slate-600 hover:bg-[#efede9]"
                  >
                    Highlight
                  </button>
                  <button
                    onClick={() => handleBioAssist('generate')}
                    className="rounded-full border border-slate-200 bg-[#f5f4f1] px-3 py-1 text-xs font-semibold text-slate-600 hover:bg-[#efede9]"
                  >
                    Generate Bio
                  </button>
                </div>
              </div>
              <textarea
                rows={7}
                value={draft.bio}
                onChange={(event) => setDraft((prev) => ({ ...prev, bio: event.target.value }))}
                className="w-full resize-y rounded-2xl border border-slate-200 bg-[#fdfdfc] px-5 py-4 text-lg leading-relaxed text-slate-700 focus:border-orange-300 focus:outline-none focus:ring-2 focus:ring-orange-100"
              />
            </div>

            <div>
              <div className="mb-2 flex items-baseline gap-3">
                <label className="text-sm font-semibold text-slate-700">Pinned Questions</label>
                <span className="text-xs font-medium text-slate-500">Max 5 questions</span>
              </div>
              <div className="space-y-3">
                {draft.pinnedQuestions.map((question, idx) => (
                  <div key={`question-${idx}`} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={question}
                      onChange={(event) => handleUpdateQuestion(idx, event.target.value)}
                      className="w-full rounded-2xl border border-slate-200 bg-[#fdfdfc] px-5 py-3 text-lg text-slate-700 focus:border-orange-300 focus:outline-none focus:ring-2 focus:ring-orange-100"
                    />
                    <button
                      onClick={() => handleRemoveQuestion(idx)}
                      className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 hover:border-rose-200 hover:text-rose-500"
                    >
                      <IconClose />
                    </button>
                  </div>
                ))}
              </div>
              <button
                onClick={handleAddQuestion}
                disabled={draft.pinnedQuestions.length >= 5}
                className="mt-3 inline-flex items-center gap-2 rounded-xl bg-[#f5f4f1] px-4 py-2 text-sm font-semibold text-slate-600 transition hover:bg-[#ece9e4] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <IconPlus />
                Add question
              </button>
            </div>

            <div>
              <label className="mb-2 block text-sm font-semibold text-slate-700">Social Links</label>
              <div className="space-y-3">
                {draft.socialLinks.map((link, idx) => (
                  <div key={`social-${idx}`} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={link}
                      onChange={(event) => handleUpdateLink(idx, event.target.value)}
                      placeholder="domain.com/your-handle"
                      className="w-full rounded-2xl border border-slate-200 bg-[#fdfdfc] px-5 py-3 text-lg text-slate-700 focus:border-orange-300 focus:outline-none focus:ring-2 focus:ring-orange-100"
                    />
                    <button
                      onClick={() => handleRemoveLink(idx)}
                      className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 hover:border-rose-200 hover:text-rose-500"
                    >
                      <IconClose />
                    </button>
                  </div>
                ))}
              </div>
              <button
                onClick={handleAddLink}
                className="mt-3 inline-flex items-center gap-2 rounded-xl bg-[#f5f4f1] px-4 py-2 text-sm font-semibold text-slate-600 transition hover:bg-[#ece9e4]"
              >
                <IconPlus />
                Add link
              </button>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-[#f8f7f4] px-5 py-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-lg font-semibold text-slate-800">Profile Video</p>
                  <p className="text-sm text-slate-500">Show animated video on your profile picture</p>
                </div>
                <button
                  onClick={() => setDraft((prev) => ({ ...prev, profileVideoEnabled: !prev.profileVideoEnabled }))}
                  className={`relative inline-flex h-7 w-14 items-center rounded-full transition ${
                    draft.profileVideoEnabled ? 'bg-orange-500' : 'bg-slate-300'
                  }`}
                >
                  <span
                    className={`inline-block h-6 w-6 transform rounded-full bg-white transition ${
                      draft.profileVideoEnabled ? 'translate-x-7' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            </div>
          </section>
        )}
      </div>

      <div className="fixed bottom-5 left-1/2 z-30 -translate-x-1/2">
        <button
          onClick={handleOpenChat}
          className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/95 px-5 py-3 text-base font-semibold text-slate-700 shadow-lg shadow-slate-900/10 backdrop-blur transition hover:-translate-y-0.5 hover:bg-white"
        >
          <IconChat />
          View chat
          <IconChevronUp />
        </button>
      </div>
    </div>
  );
}
