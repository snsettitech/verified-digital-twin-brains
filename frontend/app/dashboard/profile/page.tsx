'use client';

import React, { Suspense, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useTwin } from '@/lib/context/TwinContext';
import { API_ENDPOINTS } from '@/lib/constants';
import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';
import { useToast, TrainingMetrics } from '@/components/ui';
import type { TrainingMetricsData } from '@/components/ui/TrainingMetrics';
import { LinkedInImportCard } from '@/components/dashboard/LinkedInImportCard';

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

type ProfileInsightsResponse = {
  profile_pack?: PersonaProfilePack | null;
  metrics?: {
    combined?: TrainingMetricsData | null;
    twin_onboarding?: TrainingMetricsData | null;
    name_deep_research?: TrainingMetricsData | null;
  };
  question_suggestions?: string[];
  question_capacity_estimate?: number;
  question_capacity_prompt?: string;
  name_deep_research?: {
    run_id?: string;
    status?: string;
  } | null;
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
  verified_claims_count?: number;
  areas_of_expertise?: string[];
  personality_traits?: string[];
  key_achievements?: string[];
  contributions?: string[];
  speaking_style?: string;
  social_links?: Record<string, string>;
  pinned_questions?: string[];
  education?: Array<{ institution?: string; degree?: string; field?: string; start_year?: number | null; end_year?: number | null }>;
  work_experience?: Array<{ company?: string; role?: string; description?: string; start_year?: number | null; end_year?: number | null }>;
};

const DEFAULT_PINNED_QUESTIONS = [
  'What inspired you to start this project?',
  'What should people know about your style and approach?',
  'What are the best ways to connect with you?',
];

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

function normalizeSocialLinkArray(value: unknown, max = 8): string[] {
  if (isRecord(value)) {
    return normalizeStringArray(Object.values(value), [], max);
  }
  return normalizeStringArray(value, [], max);
}

function inferSocialLinkLabel(url: string, index: number): string {
  try {
    const parsed = new URL(url.startsWith('http') ? url : `https://${url}`);
    const host = parsed.hostname.toLowerCase();
    if (host.includes('linkedin.com')) return 'linkedin';
    if (host.includes('instagram.com')) return 'instagram';
    if (host.includes('youtube.com') || host.includes('youtu.be')) return 'youtube';
    if (host.includes('x.com') || host.includes('twitter.com')) return 'twitter';
    if (host.includes('github.com')) return 'github';
    if (host.includes('wikipedia.org')) return 'wikipedia';
    return index === 0 ? 'website' : `link${index + 1}`;
  } catch {
    return index === 0 ? 'website' : `link${index + 1}`;
  }
}

function socialLinksToRecord(links: string[]): Record<string, string> {
  return links.reduce<Record<string, string>>((accumulator, link, index) => {
    const cleaned = link.trim();
    if (!cleaned) return accumulator;
    const normalized = cleaned.startsWith('http') ? cleaned : `https://${cleaned}`;
    const baseLabel = inferSocialLinkLabel(normalized, index);
    let label = baseLabel;
    let suffix = 2;
    while (accumulator[label] && accumulator[label] !== normalized) {
      label = `${baseLabel}_${suffix}`;
      suffix += 1;
    }
    accumulator[label] = normalized;
    return accumulator;
  }, {});
}

function trainingMetricStrength(metrics: TrainingMetricsData | null | undefined): number {
  if (!metrics || typeof metrics !== 'object') return -1;
  const words = typeof metrics.words_processed === 'number' ? metrics.words_processed : 0;
  const questions = typeof metrics.questions_answerable_est === 'number' ? metrics.questions_answerable_est : 0;
  const mindScore = typeof metrics.mind_score === 'number' ? metrics.mind_score : 0;
  return words + questions + mindScore;
}

function chooseBestTrainingMetrics(
  ...candidates: Array<TrainingMetricsData | null | undefined>
): TrainingMetricsData | null {
  let best: TrainingMetricsData | null = null;
  let bestScore = -1;
  for (const candidate of candidates) {
    const score = trainingMetricStrength(candidate);
    if (score > bestScore) {
      best = candidate ?? null;
      bestScore = score;
    }
  }
  return best;
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

function profileLifeLine(profile: PersonaProfilePack | null): string {
  if (!profile) return '';
  const years =
    profile.birth_year || profile.death_year
      ? `${profile.birth_year || ''}${profile.birth_year || profile.death_year ? ' - ' : ''}${profile.death_year || 'Present'}`
      : '';
  if (profile.nationality && years) return `${profile.nationality} • ${years}`;
  return profile.nationality || years;
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

function ProfilePageContent() {
  const { activeTwin, user, refreshTwins, isLoading, twins, setActiveTwin } = useTwin();
  const { showToast } = useToast();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedTwinId = searchParams.get('twinId');
  const [canonicalProfileId, setCanonicalProfileId] = useState<string | null>(null);
  const [profileInsights, setProfileInsights] = useState<ProfileInsightsResponse | null>(null);

  useEffect(() => {
    void refreshTwins();
  }, [refreshTwins]);

  useEffect(() => {
    let cancelled = false;

    async function resolveCanonicalProfile() {
      try {
        const response = await authFetchStandalone('/profile');
        if (!response.ok) {
          if (response.status === 404 && !cancelled) {
            setCanonicalProfileId(null);
          }
          return;
        }
        const payload = await response.json();
        if (!cancelled) {
          setCanonicalProfileId(typeof payload?.id === 'string' ? payload.id : null);
        }
      } catch (error) {
        console.error('[Profile] Failed to resolve canonical profile:', error);
      }
    }

    void resolveCanonicalProfile();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!requestedTwinId) return;
    if (canonicalProfileId && requestedTwinId !== canonicalProfileId) return;
    if (activeTwin?.id === requestedTwinId) return;
    const exists = twins.some((t) => t.id === requestedTwinId);
    if (!exists) return;
    setActiveTwin(requestedTwinId);
  }, [requestedTwinId, canonicalProfileId, activeTwin?.id, twins, setActiveTwin]);

  useEffect(() => {
    if (!canonicalProfileId) return;
    if (activeTwin?.id === canonicalProfileId) return;
    const exists = twins.some((t) => t.id === canonicalProfileId);
    if (!exists) return;
    setActiveTwin(canonicalProfileId);
  }, [canonicalProfileId, activeTwin?.id, twins, setActiveTwin]);

  const effectiveTwin = useMemo(() => {
    if (!canonicalProfileId) return activeTwin;
    return twins.find((t) => t.id === canonicalProfileId) || activeTwin;
  }, [canonicalProfileId, twins, activeTwin]);

  // Extract training metrics from twin data
  const trainingMetrics = useMemo<TrainingMetricsData | null>(() => {
    if (!effectiveTwin?.settings) return null;
    
    const settings = isRecord(effectiveTwin.settings) ? effectiveTwin.settings : {};
    
    // Check for training_metrics in settings (from API)
    const metrics = settings.training_metrics;
    if (isRecord(metrics)) {
      return {
        words_processed: typeof metrics.words_processed === 'number' ? metrics.words_processed : 0,
        words_processed_display: typeof metrics.words_processed_display === 'string' ? metrics.words_processed_display : '0',
        questions_answerable_est: typeof metrics.questions_answerable_est === 'number' ? metrics.questions_answerable_est : 0,
        questions_answerable_display: typeof metrics.questions_answerable_display === 'string' ? metrics.questions_answerable_display : '0',
        mind_score: typeof metrics.mind_score === 'number' ? metrics.mind_score : 0,
        mind_score_label: typeof metrics.mind_score_label === 'string' ? metrics.mind_score_label : 'Early',
        method_version: typeof metrics.method_version === 'string' ? metrics.method_version : 'v1_heuristic',
        last_computed_at: typeof metrics.last_computed_at === 'string' ? metrics.last_computed_at : undefined,
        notes: typeof metrics.notes === 'string' ? metrics.notes : undefined,
      };
    }
    
    return null;
  }, [effectiveTwin?.settings]);

  useEffect(() => {
    let cancelled = false;

    async function loadProfileInsights() {
      if (!effectiveTwin?.id) {
        setProfileInsights(null);
        return;
      }

      try {
        const response = await authFetchStandalone(API_ENDPOINTS.TWIN_PROFILE_INSIGHTS(effectiveTwin.id));
        if (!response.ok) {
          throw new Error(`Failed to load profile insights (${response.status})`);
        }
        const payload = await response.json();
        if (!cancelled) {
          setProfileInsights(payload as ProfileInsightsResponse);
        }
      } catch (error) {
        console.error('[Profile] Failed to load profile insights:', error);
        if (!cancelled) {
          setProfileInsights(null);
        }
      }
    }

    void loadProfileInsights();
    return () => {
      cancelled = true;
    };
  }, [effectiveTwin?.id]);

  const effectiveTrainingMetrics = useMemo<TrainingMetricsData | null>(() => {
    return chooseBestTrainingMetrics(
      profileInsights?.metrics?.combined,
      profileInsights?.metrics?.name_deep_research,
      profileInsights?.metrics?.twin_onboarding,
      trainingMetrics,
    );
  }, [profileInsights, trainingMetrics]);

  const derivedProfile = useMemo<ProfileDraft>(() => {
    const settings = isRecord(effectiveTwin?.settings) ? effectiveTwin.settings : {};
    const profile = isRecord(settings.public_profile) ? settings.public_profile : {};
    const tagline = typeof settings.tagline === 'string' ? settings.tagline : '';
    const publicIntro = typeof settings.public_intro === 'string' ? settings.public_intro : '';
    const displayName =
      (typeof profile.display_name === 'string' && profile.display_name.trim()) ||
      effectiveTwin?.name ||
      user?.full_name ||
      'Persona';

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
    const socialLinks = normalizeSocialLinkArray(profile.social_links, 8);
    const profileVideoEnabled =
      typeof profile.profile_video_enabled === 'boolean' ? profile.profile_video_enabled : true;
    const avatarUrl =
      (typeof profile.avatar_url === 'string' && profile.avatar_url.trim()) ||
      user?.avatar_url ||
      '';
    
    // Use training metrics for mind label if available
    const metricsLabel = effectiveTrainingMetrics?.mind_score_label;
    const metricsWords = effectiveTrainingMetrics?.words_processed_display;
    const mindLabel = metricsLabel && metricsWords
      ? `${metricsWords} ${metricsLabel}`
      : (typeof profile.mind_label === 'string' && profile.mind_label.trim()) ||
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
  }, [effectiveTwin?.name, effectiveTwin?.settings, user?.avatar_url, user?.full_name, effectiveTrainingMetrics]);

  const previewProfile = useMemo<PersonaProfilePack>(() => {
    const pack = profileInsights?.profile_pack;
    const packSocial =
      isRecord(pack?.social_links)
        ? Object.fromEntries(
            Object.entries(pack.social_links).filter(([, url]) => typeof url === 'string' && url.trim())
          ) as Record<string, string>
        : Object.fromEntries(
            derivedProfile.socialLinks
              .filter((link) => link.trim())
              .map((link, index) => [`link${index + 1}`, link.trim()])
          );

    return {
      name: pack?.name || derivedProfile.displayName,
      occupation:
        pack?.occupation ||
        [derivedProfile.role, derivedProfile.organization].filter(Boolean).join(' at ') ||
        derivedProfile.headline,
      headline: pack?.headline || derivedProfile.headline,
      bio: pack?.bio || derivedProfile.bio,
      short_description: pack?.short_description || pack?.bio || derivedProfile.bio,
      avatar_url: pack?.avatar_url || pack?.image_url || derivedProfile.avatarUrl,
      birth_year: pack?.birth_year,
      death_year: pack?.death_year,
      nationality: pack?.nationality,
      verified_profile: Boolean(pack?.verified_profile),
      verified_claims_count: pack?.verified_claims_count,
      areas_of_expertise: normalizeStringArray(pack?.areas_of_expertise, [], 6),
      personality_traits: normalizeStringArray(pack?.personality_traits, [], 6),
      key_achievements: normalizeStringArray(pack?.key_achievements, [], 6),
      contributions: normalizeStringArray(pack?.contributions, [], 6),
      speaking_style: typeof pack?.speaking_style === 'string' ? pack.speaking_style : '',
      social_links: packSocial,
      pinned_questions: normalizeStringArray(pack?.pinned_questions, derivedProfile.pinnedQuestions, 5),
      education: Array.isArray(pack?.education) ? pack.education : [],
      work_experience: Array.isArray(pack?.work_experience) ? pack.work_experience : [],
    };
  }, [derivedProfile, profileInsights?.profile_pack]);

  const previewLifeLine = useMemo(() => profileLifeLine(previewProfile), [previewProfile]);
  const previewSocialLinks = useMemo(() => Object.entries(previewProfile.social_links || {}), [previewProfile]);

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

  const handleOpenChat = (seedQuestion?: string) => {
    if (!effectiveTwin?.id) {
      showToast('No profile is selected yet.', 'info');
      return;
    }
    const twinStatus = String(effectiveTwin?.status || '').toLowerCase();
    const canChatByStatus =
      twinStatus === 'active' || twinStatus === 'persona_built' || twinStatus === 'live';
    const canChatByLegacyFlag = !twinStatus && Boolean(effectiveTwin?.is_active);
    const canChat = canChatByStatus || canChatByLegacyFlag;
    if (!canChat) {
      showToast('Profile is still building. Chat unlocks when setup is complete.', 'info');
      return;
    }

    const params = new URLSearchParams();
    params.set('source', 'profile');
    params.set('twinId', effectiveTwin.id);
    if (seedQuestion && seedQuestion.trim()) {
      params.set('q', seedQuestion.trim());
    }
    router.push(`/dashboard/chat?${params.toString()}`);
  };

  const handleBioAssist = (mode: 'highlight' | 'generate') => {
    if (mode === 'highlight') {
      showToast('Highlighting support is coming soon.', 'info');
      return;
    }
    showToast('Bio generation support is coming soon.', 'info');
  };

  const handleSave = async () => {
    if (!effectiveTwin) return;

    const cleanedPinned = draft.pinnedQuestions
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
      .slice(0, 5);

    const cleanedSocial = draft.socialLinks
      .map((item) => item.trim())
      .filter((item) => item.length > 0);

    const currentSettings = isRecord(effectiveTwin.settings) ? effectiveTwin.settings : {};
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
        social_links: socialLinksToRecord(cleanedSocial),
        profile_video_enabled: draft.profileVideoEnabled,
        avatar_url: draft.avatarUrl.trim(),
        mind_label: draft.mindLabel.trim() || '16.5K Mind',
      },
    };

    setIsSaving(true);
    try {
      const response = await authFetchStandalone(API_ENDPOINTS.TWIN_DETAIL(effectiveTwin.id), {
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

  if (!effectiveTwin) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-8">
        <h2 className="text-xl font-bold text-slate-900">No Twin Selected</h2>
        <p className="mt-2 text-sm text-slate-600">Select a twin from the sidebar to customize your profile.</p>
      </div>
    );
  }

  const linkedInImportDone = Boolean(
    isRecord(effectiveTwin?.settings) &&
    isRecord((effectiveTwin.settings as Record<string, unknown>).public_profile_meta) &&
    ((effectiveTwin.settings as Record<string, unknown>).public_profile_meta as Record<string, unknown>).linkedin_export_imported
  );

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

        {/* LinkedIn import nudge — shown once until user imports or dismisses */}
        {effectiveTwin && !linkedInImportDone && (
          <LinkedInImportCard twinId={effectiveTwin.id} onImported={refreshTwins} />
        )}

        <section className="relative overflow-hidden rounded-[32px] border border-white/70 bg-white/80 p-6 shadow-[0_20px_55px_rgba(15,23,42,0.08)] backdrop-blur-sm md:p-10">
          <div className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-gradient-to-br from-orange-100/80 to-amber-100/40 blur-3xl" />
          <div className="pointer-events-none absolute -left-12 -bottom-20 h-44 w-44 rounded-full bg-gradient-to-br from-slate-100/70 to-white/30 blur-3xl" />

          <div className="relative flex flex-col gap-8">
            <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
              <div className="flex flex-col gap-5">
                <div className="h-36 w-36 overflow-hidden rounded-[30px] bg-gradient-to-br from-slate-300 to-slate-100 shadow-lg shadow-slate-900/10">
                  {draft.avatarUrl ? (
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
                      {previewProfile.occupation || previewProfile.headline || 'Add a headline in edit mode'}
                    </span>
                    {previewProfile.verified_profile && (
                      <span className="inline-flex items-center rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">
                        Verified
                      </span>
                    )}
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

            {/* Training Metrics - Delphi-style Stats */}
            {!isEditing && (
              <div className="mt-4">
                <TrainingMetrics 
                  metrics={effectiveTrainingMetrics}
                  isLoading={isLoading}
                  size="md"
                  className="max-w-2xl"
                />
                <p className="mt-2 text-xs text-slate-400">
                  Higher mind scores indicate more trained and accurate profiles. 
                  Metrics are estimates and improve as more high-quality sources are added.
                </p>
                {profileInsights?.metrics?.name_deep_research ? (
                  <p className="mt-1 text-xs text-slate-500">
                    Combined from onboarding ({profileInsights.metrics.twin_onboarding?.words_processed_display || '0'} words)
                    and deep research ({profileInsights.metrics.name_deep_research.words_processed_display || '0'} words).
                  </p>
                ) : null}
              </div>
            )}

            {!isEditing && (
              <div className="relative flex flex-col gap-6 xl:pr-72">
                <p className="max-w-3xl text-xl leading-relaxed text-slate-700">
                  {previewProfile.short_description || previewProfile.bio || draft.bio}
                </p>
                <div className="hidden rounded-3xl bg-gradient-to-br from-orange-500 to-amber-500 p-6 text-white shadow-lg shadow-orange-500/20 xl:absolute xl:bottom-0 xl:right-0 xl:block xl:w-64">
                  <p className="text-2xl font-bold">Call {firstName(draft.displayName)}</p>
                  <p className="mt-1 text-sm text-orange-100">Have a live conversation with your persona.</p>
                  <button
                    onClick={() => handleOpenChat()}
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
            <section className="rounded-3xl border border-white/60 bg-white/80 p-6 shadow-[0_10px_30px_rgba(15,23,42,0.05)] md:p-8">
              <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <h2 className="text-3xl font-bold text-slate-900">Marketplace Preview</h2>
                    {previewLifeLine && (
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-600">
                        {previewLifeLine}
                      </span>
                    )}
                  </div>
                  <p className="mt-3 max-w-3xl text-base leading-7 text-slate-600">
                    {previewProfile.short_description || previewProfile.bio || draft.bio}
                  </p>

                  {previewSocialLinks.length > 0 && (
                    <div className="mt-5 flex flex-wrap gap-2">
                      {previewSocialLinks.map(([label, url]) => (
                        <a
                          key={`${label}-${url}`}
                          href={url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
                        >
                          {label}
                        </a>
                      ))}
                    </div>
                  )}
                </div>

                <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
                  <div className="rounded-3xl bg-[#f8f7f4] p-5">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Profile</p>
                    <p className="mt-2 text-base font-bold text-slate-900">
                      {previewProfile.verified_profile ? 'Verified public persona' : 'Public digital persona'}
                    </p>
                  </div>
                  <div className="rounded-3xl bg-[#f8f7f4] p-5">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Verified Claims</p>
                    <p className="mt-2 text-3xl font-bold text-slate-900">
                      {previewProfile.verified_claims_count || 0}
                    </p>
                  </div>
                  <div className="rounded-3xl bg-[#f8f7f4] p-5">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Speaking Style</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      {previewProfile.speaking_style || 'Direct, clear, and grounded in the public profile.'}
                    </p>
                  </div>
                </div>
              </div>

              <div className="mt-6 grid gap-4 lg:grid-cols-2">
                {previewProfile.areas_of_expertise && previewProfile.areas_of_expertise.length > 0 && (
                  <div className="rounded-3xl bg-[#f8f7f4] p-5">
                    <h3 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">Areas of Expertise</h3>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {previewProfile.areas_of_expertise.map((item) => (
                        <span key={`expertise-${item}`} className="rounded-full bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {previewProfile.key_achievements && previewProfile.key_achievements.length > 0 && (
                  <div className="rounded-3xl bg-[#f8f7f4] p-5">
                    <h3 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">Key Achievements</h3>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {previewProfile.key_achievements.map((item) => (
                        <span key={`achievement-${item}`} className="rounded-full bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {previewProfile.personality_traits && previewProfile.personality_traits.length > 0 && (
                  <div className="rounded-3xl bg-[#f8f7f4] p-5">
                    <h3 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">Personality Traits</h3>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {previewProfile.personality_traits.map((item) => (
                        <span key={`trait-${item}`} className="rounded-full bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {previewProfile.contributions && previewProfile.contributions.length > 0 && (
                  <div className="rounded-3xl bg-[#f8f7f4] p-5">
                    <h3 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">Contributions</h3>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {previewProfile.contributions.map((item) => (
                        <span key={`contribution-${item}`} className="rounded-full bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {((previewProfile.education && previewProfile.education.length > 0) ||
                (previewProfile.work_experience && previewProfile.work_experience.length > 0)) && (
                <div className="mt-6 grid gap-4 lg:grid-cols-2">
                  {previewProfile.education && previewProfile.education.length > 0 && (
                    <div className="rounded-3xl bg-[#f8f7f4] p-5">
                      <h3 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">Education</h3>
                      <div className="mt-4 space-y-3">
                        {previewProfile.education.slice(0, 4).map((entry, idx) => (
                          <div key={`education-preview-${idx}`} className="rounded-2xl bg-white px-4 py-3 shadow-sm">
                            <p className="font-medium text-slate-900">{entry.degree || entry.field || entry.institution || 'Education'}</p>
                            {entry.institution && <p className="mt-1 text-sm text-slate-600">{entry.institution}</p>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {previewProfile.work_experience && previewProfile.work_experience.length > 0 && (
                    <div className="rounded-3xl bg-[#f8f7f4] p-5">
                      <h3 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">Work Experience</h3>
                      <div className="mt-4 space-y-3">
                        {previewProfile.work_experience.slice(0, 4).map((entry, idx) => (
                          <div key={`work-preview-${idx}`} className="rounded-2xl bg-white px-4 py-3 shadow-sm">
                            <p className="font-medium text-slate-900">{entry.role || entry.company || 'Experience'}</p>
                            {entry.company && <p className="mt-1 text-sm text-slate-600">{entry.company}</p>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </section>

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

            {Array.isArray(profileInsights?.question_suggestions) && profileInsights.question_suggestions.length > 0 ? (
              <section className="rounded-3xl border border-white/60 bg-white/75 p-6 shadow-[0_10px_30px_rgba(15,23,42,0.05)]">
                <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-2xl font-bold text-slate-900">Chat Follow-ups</h2>
                  <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">
                    ~{(profileInsights.question_capacity_estimate || 0).toLocaleString()} answerable questions
                  </span>
                </div>
                {profileInsights.question_capacity_prompt ? (
                  <p className="mb-4 text-sm text-slate-600">{profileInsights.question_capacity_prompt}</p>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  {profileInsights.question_suggestions.slice(0, 10).map((question, idx) => (
                    <button
                      key={`${question}-${idx}`}
                      onClick={() => handleOpenChat(question)}
                      className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </section>
            ) : null}

            <section className="rounded-3xl border border-white/60 bg-white/75 p-6 shadow-[0_10px_30px_rgba(15,23,42,0.05)]">
              <h2 className="text-2xl font-bold text-slate-900">Follow {firstName(draft.displayName)} for more...</h2>
              <div className="mt-4 flex flex-wrap gap-3">
                {previewSocialLinks.length > 0 ? (
                  previewSocialLinks.map(([label, url]) => (
                    <a
                      key={`${label}-${url}`}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
                    >
                      {label}
                    </a>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">Public links will appear here once they are added to the profile.</p>
                )}
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
          onClick={() => handleOpenChat()}
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

function ProfilePageFallback() {
  return (
    <div className="flex h-[60vh] items-center justify-center">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-orange-500 border-t-transparent" />
    </div>
  );
}

export default function ProfilePage() {
  return (
    <Suspense fallback={<ProfilePageFallback />}>
      <ProfilePageContent />
    </Suspense>
  );
}
