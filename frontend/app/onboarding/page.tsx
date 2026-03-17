'use client';

import React, { useState, Suspense, useCallback, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { UnifiedInputStep, type UnifiedInputData } from '@/components/onboarding/steps/UnifiedInputStep';
import { StepProgress, type ProgressStep, getResearchStepLabel } from '@/components/onboarding/StepProgress';
import { StepReviewEdit } from '@/components/onboarding/steps/StepReviewEdit';
import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';

// =============================================================================
// Types
// =============================================================================

type OnboardingStep = 'input' | 'progress' | 'review-edit';

interface Twin {
  id: string;
  name: string;
  status: string;
}

// =============================================================================
// Wikipedia identity match check
// =============================================================================

interface WikiSummary {
  type?: string;
  description?: string;
  extract?: string;
  content_urls?: { desktop?: { page?: string } };
}

const PERSON_SIGNALS = [
  'born', 'american', 'british', 'canadian', 'australian', 'indian', 'is a', 'was a',
  'politician', 'author', 'actor', 'director', 'ceo', 'founder', 'professor', 'scientist',
  'engineer', 'entrepreneur', 'executive', 'journalist', 'businessman', 'businesswoman',
];

const STOP_WORDS = new Set([
  'at', 'of', 'the', 'a', 'an', 'and', 'or', 'in', 'for', 'with', 'by', 'to', 'is',
  'as', 'on', 'co', 'inc', 'llc', 'ltd', 'group',
]);

function isWikipediaConfidentMatch(wiki: WikiSummary, headline: string | undefined): boolean {
  if (wiki.type === 'disambiguation') return false;
  const combined = `${wiki.description ?? ''} ${wiki.extract ?? ''}`.toLowerCase();
  const hasPerson = PERSON_SIGNALS.some(s => combined.includes(s));
  if (!hasPerson) return false;
  if (!headline) return true;
  const keywords = headline
    .toLowerCase()
    .split(/[\s,|\/\-]+/)
    .map(w => w.replace(/[^a-z0-9]/g, ''))
    .filter(w => w.length >= 4 && !STOP_WORDS.has(w));
  if (keywords.length === 0) return true;
  return keywords.some(kw => combined.includes(kw));
}

// =============================================================================
// Component
// =============================================================================

function OnboardingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnTo = searchParams.get('returnTo');

  const [currentStep, setCurrentStep] = useState<OnboardingStep>('input');
  const [twin, setTwin] = useState<Twin | null>(null);
  const [inputData, setInputData] = useState<UnifiedInputData | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Progress steps state
  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>([]);

  // Ref to allow updating a single step without full re-render churn
  const stepsRef = useRef<ProgressStep[]>([]);

  const updateStep = useCallback((id: string, patch: Partial<ProgressStep>) => {
    stepsRef.current = stepsRef.current.map(s => s.id === id ? { ...s, ...patch } : s);
    setProgressSteps([...stepsRef.current]);
  }, []);

  const trackEvent = useCallback((event: string, props?: Record<string, unknown>) => {
    if (typeof window !== 'undefined') {
      const ph = (window as unknown as { posthog?: { capture: (e: string, p?: Record<string, unknown>) => void } }).posthog;
      ph?.capture(event, props);
    }
    console.log(`[Telemetry] ${event}`, props);
  }, []);

  // ---------------------------------------------------------------------------
  // Phase A — LinkedIn OAuth pre-seed (image + social link, locked)
  // ---------------------------------------------------------------------------
  const prePopulateLinkedInFields = useCallback(async (twinId: string, data: UnifiedInputData): Promise<void> => {
    const identity = data.linkedInIdentity;
    if (!identity) return;

    const publicProfile: Record<string, unknown> = {};
    if (identity.imageUrl) {
      publicProfile.image_url = identity.imageUrl;
      publicProfile.avatar_url = identity.imageUrl;
    }
    if (identity.profileUrl) {
      publicProfile.social_links = { linkedin: identity.profileUrl };
    }
    if (!identity.imageUrl && !identity.profileUrl) return;

    const settingsPatch: Record<string, unknown> = { public_profile: publicProfile };
    if (identity.imageUrl) {
      settingsPatch.public_profile_meta = {
        image_source_type: 'oauth',
        image_source_url: identity.profileUrl ?? identity.imageUrl,
      };
    }

    try {
      await authFetchStandalone(`/twins/${twinId}`, {
        method: 'PATCH',
        body: JSON.stringify({ settings: settingsPatch }),
      });
    } catch (err) {
      console.warn('[Onboarding] LinkedIn pre-seed failed (non-blocking):', err);
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Phase B — Resume Mode A (parallel, fire-and-forget)
  // ---------------------------------------------------------------------------
  const submitResume = useCallback((twinId: string, file: File): void => {
    void (async () => {
      try {
        const formData = new FormData();
        formData.append('twin_id', twinId);
        formData.append('files', file);
        await authFetchStandalone('/persona/link-compile/jobs/mode-a', {
          method: 'POST',
          body: formData,
        });
        updateStep('resume', { status: 'done' });
      } catch (err) {
        console.warn('[Onboarding] Resume Mode A failed (non-blocking):', err);
        updateStep('resume', { status: 'skipped' });
      }
    })();
  }, [updateStep]);

  // ---------------------------------------------------------------------------
  // Phase C — Wikipedia fast-index (fire-and-forget, all users)
  // ---------------------------------------------------------------------------
  const tryWikipediaFastIndex = useCallback((
    twinId: string,
    fullName: string,
    headline: string | undefined,
  ): void => {
    const slug = encodeURIComponent(fullName.trim());
    void (async () => {
      try {
        const wikiRes = await fetch(
          `https://en.wikipedia.org/api/rest_v1/page/summary/${slug}`,
          { signal: AbortSignal.timeout(8000) },
        );
        if (!wikiRes.ok) {
          updateStep('wikipedia', { status: 'skipped' });
          return;
        }
        const wiki: WikiSummary = await wikiRes.json();
        if (!isWikipediaConfidentMatch(wiki, headline)) {
          updateStep('wikipedia', { status: 'skipped' });
          return;
        }
        const pageUrl = wiki.content_urls?.desktop?.page
          ?? `https://en.wikipedia.org/wiki/${slug}`;
        await authFetchStandalone('/persona/link-compile/jobs/mode-c', {
          method: 'POST',
          body: JSON.stringify({ twin_id: twinId, urls: [pageUrl] }),
        });
        updateStep('wikipedia', { status: 'done' });
      } catch {
        updateStep('wikipedia', { status: 'skipped' });
      }
    })();
  }, [updateStep]);

  // ---------------------------------------------------------------------------
  // Phase D — Deep research (all users who give consent)
  // ---------------------------------------------------------------------------
  const pollDeepResearch = useCallback(async (runId: string): Promise<void> => {
    const TERMINAL = new Set(['completed', 'failed']);
    for (;;) {
      await new Promise(r => setTimeout(r, 3000));
      const res = await authFetchStandalone(`/deep-research/runs/${runId}`);
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload?.detail?.message ?? `Research check failed (${res.status})`);
      }
      const data = await res.json();
      // Update the research step sublabel with current status
      updateStep('research', { sublabel: getResearchStepLabel(data.status) });
      if (TERMINAL.has(data.status)) {
        if (data.status === 'failed') throw new Error(data.error_message ?? 'Research failed');
        return;
      }
    }
  }, [updateStep]);

  const runDeepResearch = useCallback(async (twinId: string, data: UnifiedInputData): Promise<void> => {
    // Unified: works for LinkedIn, website URL, or name-only
    const name = data.linkedInIdentity?.displayName ?? data.fullName;
    const websiteHint = data.profileUrl
      ?? data.linkedInIdentity?.profileUrl
      ?? undefined;

    updateStep('research', { status: 'running', sublabel: 'Starting…' });

    const runRes = await authFetchStandalone('/deep-research/runs', {
      method: 'POST',
      body: JSON.stringify({
        name,
        hints: {
          website: websiteHint,
          company: data.headline ?? data.linkedInIdentity?.headline,
        },
      }),
    });
    if (!runRes.ok) {
      const payload = await runRes.json().catch(() => ({}));
      throw new Error(payload?.detail?.message ?? `Failed to start research (${runRes.status})`);
    }
    const { run_id: runId } = await runRes.json();

    await pollDeepResearch(runId);
    updateStep('research', { status: 'done', sublabel: undefined });

    const compileRes = await authFetchStandalone(`/deep-research/runs/${runId}/compile-to-twin`, {
      method: 'POST',
      body: JSON.stringify({ twin_id: twinId }),
    });
    if (!compileRes.ok) {
      const payload = await compileRes.json().catch(() => ({}));
      throw new Error(payload?.detail?.message ?? `Compile failed (${compileRes.status})`);
    }
  }, [pollDeepResearch, updateStep]);

  // ---------------------------------------------------------------------------
  // Main submit handler — unified for ALL user types
  // ---------------------------------------------------------------------------
  const handleInputSubmit = async (data: UnifiedInputData) => {
    setInputData(data);
    setSubmitError(null);
    trackEvent('onboarding_started', {
      has_linkedin: !!data.linkedInIdentity,
      has_url: !!data.profileUrl,
      has_resume: !!data.resumeFile,
      url_type: data.profileUrl?.includes('linkedin.com') ? 'linkedin' : data.profileUrl ? 'website' : 'none',
    });

    // Build initial progress steps
    const steps: ProgressStep[] = [
      { id: 'create',    label: 'Profile created',        status: 'pending' },
      { id: 'linkedin',  label: 'LinkedIn photo saved',   status: data.linkedInIdentity?.imageUrl ? 'pending' : 'skipped' },
      { id: 'resume',    label: 'Resume indexed',         status: data.resumeFile ? 'pending' : 'skipped' },
      { id: 'wikipedia', label: 'Wikipedia page found',  status: 'pending' },
      { id: 'research',  label: 'Searching the web',     status: 'pending' },
      { id: 'review',    label: 'Review & finalise',     status: 'pending' },
    ];
    stepsRef.current = steps;
    setProgressSteps(steps);

    setIsLoading(true);
    let createdInAttempt = false;

    try {
      // Step 1: Create profile
      const profileRes = await authFetchStandalone('/profile', {
        method: 'POST',
        body: JSON.stringify({
          full_name: data.fullName,
          headline: data.headline ?? data.linkedInIdentity?.headline,
          build_mode: (data.profileUrl || data.linkedInIdentity || data.resumeFile) ? 'with_links' : 'name_only',
        }),
      });

      if (!profileRes.ok) {
        if (profileRes.status === 409) {
          const payload = await profileRes.json().catch(() => ({}));
          const msg = payload?.detail?.message ?? payload?.detail ?? 'You already have a profile.';
          setSubmitError(`${msg} Go to your dashboard or reset your profile first.`);
          return;
        }
        let msg = `Failed to create profile (${profileRes.status})`;
        try {
          const payload = await profileRes.json();
          const d = payload?.detail;
          if (typeof d === 'string' && d.trim()) msg = d.trim();
          else if (d?.message) msg = d.message.trim();
        } catch { /* ignore */ }
        throw new Error(msg);
      }

      const profileData = await profileRes.json();
      const createdHeader = profileRes.headers.get('x-profile-created');
      createdInAttempt = createdHeader === 'true';
      const twinData: Twin = { id: profileData.id, name: profileData.name, status: profileData.status ?? 'draft' };
      setTwin(twinData);
      updateStep('create', { status: 'done' });

      // Switch to progress screen immediately after create
      setCurrentStep('progress');

      // Step 2A: LinkedIn pre-seed (if OAuth)
      if (data.linkedInIdentity) {
        await prePopulateLinkedInFields(twinData.id, data);
        updateStep('linkedin', { status: 'done' });
      }

      // Step 2B: Resume Mode A — fire-and-forget (runs in parallel with deep research)
      if (data.resumeFile) {
        updateStep('resume', { status: 'running' });
        submitResume(twinData.id, data.resumeFile);
      }

      // Step 2C: Wikipedia — fire-and-forget (all users)
      updateStep('wikipedia', { status: 'running' });
      tryWikipediaFastIndex(
        twinData.id,
        data.fullName,
        data.headline ?? data.linkedInIdentity?.headline,
      );

      // Step 3: Deep research — awaited (all users who gave consent)
      if (data.consent) {
        await runDeepResearch(twinData.id, data);
      }

      trackEvent('onboarding_research_completed', { twin_id: twinData.id });
      try { localStorage.setItem('activeTwinId', twinData.id); } catch { /* non-blocking */ }

      // Step 4: Review & edit
      updateStep('review', { status: 'done' });
      setCurrentStep('review-edit');

    } catch (error) {
      console.error('[Onboarding] Failed:', error);
      let rollbackApplied = false;
      if (createdInAttempt) {
        try {
          const rb = await authFetchStandalone('/profile/reset', { method: 'POST' });
          rollbackApplied = rb.ok;
        } catch { /* ignore */ }
      }
      let message = error instanceof Error && error.message
        ? error.message
        : 'Failed to create persona. Please try again.';
      if (createdInAttempt && rollbackApplied) {
        message += '\n\nProfile reset automatically — you can retry.';
      } else if (createdInAttempt && !rollbackApplied) {
        message += '\n\nA partial profile may exist. Use Settings → Reset Profile before retrying.';
      }
      setSubmitError(message);
      setCurrentStep('input');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReviewEditComplete = useCallback(() => {
    router.push(returnTo ?? '/dashboard/profile?from=onboarding');
  }, [router, returnTo]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="min-h-screen bg-slate-950">

      {/* Header — only show on input step */}
      {currentStep === 'input' && (
        <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm sticky top-0 z-50">
          <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-white">Create Your Persona</h1>
              <p className="text-sm text-slate-400">Get started in 2 minutes</p>
            </div>
          </div>
        </header>
      )}

      {/* Review-edit header */}
      {currentStep === 'review-edit' && (
        <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm sticky top-0 z-50">
          <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-white">Review Your Profile</h1>
              <p className="text-sm text-slate-400">Confirm or edit before heading to your dashboard</p>
            </div>
            <div className="text-sm text-slate-400 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-400" />
              Live
            </div>
          </div>
        </header>
      )}

      {/* Input step */}
      {currentStep === 'input' && (
        <main className="max-w-2xl mx-auto px-4 pb-32 pt-8">
          {submitError && (
            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
              <p className="text-red-400 text-sm whitespace-pre-line">{submitError}</p>
              {submitError.includes('already have a profile') && (
                <a href="/dashboard" className="mt-2 inline-block text-sm text-blue-400 hover:text-blue-300 underline">
                  Go to dashboard →
                </a>
              )}
            </div>
          )}
          {isLoading ? (
            <div className="flex items-center justify-center py-20">
              <div className="text-center">
                <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                <p className="text-slate-400">Creating your persona…</p>
              </div>
            </div>
          ) : (
            <UnifiedInputStep onSubmit={handleInputSubmit} />
          )}
        </main>
      )}

      {/* Progress step — full screen, no max-width constraint */}
      {currentStep === 'progress' && inputData && (
        <StepProgress
          name={inputData.linkedInIdentity?.displayName ?? inputData.fullName}
          steps={progressSteps}
        />
      )}

      {/* Review & edit step */}
      {currentStep === 'review-edit' && twin && (
        <main className="max-w-2xl mx-auto px-4 pb-32 pt-8">
          <StepReviewEdit
            twinId={twin.id}
            onComplete={handleReviewEditComplete}
          />
        </main>
      )}
    </div>
  );
}

export default function OnboardingPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-white">
        Loading…
      </div>
    }>
      <OnboardingContent />
    </Suspense>
  );
}
