'use client';

import React, { useState, Suspense, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { UnifiedInputStep, type UnifiedInputData } from '@/components/onboarding/steps/UnifiedInputStep';
import { StepResearch } from '@/components/onboarding/steps/StepResearch';
import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';

// =============================================================================
// Types
// =============================================================================

type OnboardingStep = 'input' | 'deep-research' | 'research';

interface Twin {
  id: string;
  name: string;
  status: string;
  specialization?: string;
  settings?: Record<string, unknown>;
}

// =============================================================================
// Deep Research Progress (inline component)
// =============================================================================

function DeepResearchProgress({ status, name }: { status: string; name: string }) {
  const statusLabels: Record<string, string> = {
    created: 'Starting research…',
    searching: 'Searching the web…',
    crawling: 'Reading public content…',
    extracting: 'Extracting information…',
    synthesizing: 'Synthesizing profile…',
    completed: 'Research complete!',
    failed: 'Research failed.',
  };
  const label = statusLabels[status] ?? status;

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center text-white">
      <div className="text-center max-w-md">
        {status !== 'failed' && (
          <div className="w-14 h-14 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-6" />
        )}
        <h2 className="text-2xl font-bold mb-2">Researching {name}</h2>
        <p className="text-slate-400">{label}</p>
      </div>
    </div>
  );
}

// =============================================================================
// Component
// =============================================================================

function OnboardingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnTo = searchParams.get('returnTo');

  const [currentStep, setCurrentStep] = useState<OnboardingStep>('input');
  const [inputData, setInputData] = useState<UnifiedInputData | null>(null);
  const [twin, setTwin] = useState<Twin | null>(null);
  const [submittedUrls, setSubmittedUrls] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [deepResearchStatus, setDeepResearchStatus] = useState('created');
  const [submitError, setSubmitError] = useState<string | null>(null);

  const trackEvent = useCallback((event: string, properties?: Record<string, unknown>) => {
    if (typeof window !== 'undefined' && (window as unknown as { posthog?: { capture: (e: string, p?: Record<string, unknown>) => void } }).posthog) {
      (window as unknown as { posthog: { capture: (e: string, p?: Record<string, unknown>) => void } }).posthog.capture(event, properties);
    }
    console.log(`[Telemetry] ${event}`, properties);
  }, []);

  // ---------------------------------------------------------------------------
  // Deep research polling helper
  // ---------------------------------------------------------------------------
  const pollDeepResearch = useCallback(async (runId: string): Promise<void> => {
    const TERMINAL = new Set(['completed', 'failed']);
    for (;;) {
      await new Promise(r => setTimeout(r, 3000));
      const res = await authFetchStandalone(`/deep-research/runs/${runId}`);
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload?.detail?.message ?? `Research status check failed (${res.status})`);
      }
      const data = await res.json();
      setDeepResearchStatus(data.status);
      if (TERMINAL.has(data.status)) {
        if (data.status === 'failed') {
          throw new Error(data.error_message ?? 'Deep research run failed');
        }
        return;
      }
    }
  }, []);

  // ---------------------------------------------------------------------------
  // LinkedIn deep research path
  // ---------------------------------------------------------------------------
  const runLinkedInDeepResearch = useCallback(async (
    twinId: string,
    data: UnifiedInputData,
  ): Promise<void> => {
    const identity = data.linkedInIdentity!;

    // 1. Start deep research run
    const runRes = await authFetchStandalone('/deep-research/runs', {
      method: 'POST',
      body: JSON.stringify({
        name: identity.displayName,
        hints: {
          location: data.location ?? undefined,
          company: identity.headline ?? undefined,
          website: identity.profileUrl ?? undefined,
        },
      }),
    });
    if (!runRes.ok) {
      const payload = await runRes.json().catch(() => ({}));
      throw new Error(payload?.detail?.message ?? `Failed to start deep research (${runRes.status})`);
    }
    const { run_id: runId } = await runRes.json();

    setCurrentStep('deep-research');
    setDeepResearchStatus('created');

    // 2. Poll to completion
    await pollDeepResearch(runId);

    // 3. Compile deep research result into twin (index to Pinecone, store claims, build persona, write bio)
    const compileRes = await authFetchStandalone(`/deep-research/runs/${runId}/compile-to-twin`, {
      method: 'POST',
      body: JSON.stringify({ twin_id: twinId }),
    });
    if (!compileRes.ok) {
      const payload = await compileRes.json().catch(() => ({}));
      throw new Error(payload?.detail?.message ?? `Failed to compile research (${compileRes.status})`);
    }
  }, [pollDeepResearch]);

  // ---------------------------------------------------------------------------
  // Main submit handler
  // ---------------------------------------------------------------------------
  const handleInputSubmit = async (data: UnifiedInputData) => {
    setInputData(data);
    setSubmitError(null);
    trackEvent('onboarding_started', {
      has_headline: !!data.headline,
      has_location: !!data.location,
      has_linkedin: !!data.linkedInIdentity,
      has_sources: !!(data.sources && data.sources.length > 0),
    });

    setIsLoading(true);
    let createdProfileInAttempt = false;
    try {
      const sources = data.sources ?? [];
      const hasOptionalSources = sources.length > 0;
      const buildMode: 'with_links' | 'name_only' = (hasOptionalSources || data.linkedInIdentity) ? 'with_links' : 'name_only';

      // Step 1: create profile
      const profileResponse = await authFetchStandalone('/profile', {
        method: 'POST',
        body: JSON.stringify({
          full_name: data.fullName,
          headline: data.headline,
          build_mode: buildMode,
        }),
      });

      if (!profileResponse.ok) {
        if (profileResponse.status === 409) {
          const payload = await profileResponse.json().catch(() => ({}));
          const msg = payload?.detail?.message ?? payload?.detail ?? 'You already have a profile.';
          setSubmitError(`${msg} Go to your dashboard or reset your profile first.`);
          return;
        }
        let detailMessage = `Failed to create profile (${profileResponse.status})`;
        try {
          const payload = await profileResponse.json();
          const detail = payload?.detail;
          if (typeof detail === 'string' && detail.trim()) detailMessage = detail.trim();
          else if (detail && typeof detail?.message === 'string') detailMessage = detail.message.trim();
        } catch { /* ignore */ }
        throw new Error(detailMessage);
      }

      const profileData = await profileResponse.json();
      const profileCreatedHeader = profileResponse.headers.get('x-profile-created');
      createdProfileInAttempt = profileCreatedHeader === 'true';
      const twinData: Twin = {
        id: profileData.id,
        name: profileData.name,
        status: profileData.status || 'draft',
        specialization: profileData.specialization || 'vanilla',
        settings: profileData.settings,
      };
      setTwin(twinData);

      // Step 2a: LinkedIn path — deep research
      if (data.linkedInIdentity) {
        await runLinkedInDeepResearch(twinData.id, data);
        trackEvent('onboarding_deep_research_completed', { twin_id: twinData.id });
        try { localStorage.setItem('activeTwinId', twinData.id); } catch { /* non-blocking */ }
        router.push(returnTo ?? `/dashboard/profile?from=onboarding`);
        return;
      }

      // Step 2b: Standard path — Mode A/B/C + StepResearch
      const urls: string[] = [];
      for (const s of sources) {
        if (s.type === 'link' && s.value.trim() && s.value.startsWith('http')) {
          urls.push(s.value.trim());
        }
      }
      const allUrls = [...new Set(urls)].filter(Boolean);
      setSubmittedUrls(allUrls);

      // Submit files (Mode A)
      const files = sources.filter((s): s is typeof s & { file: File } => s.type === 'export' && !!s.file).map(s => s.file);
      if (files.length > 0) {
        const formData = new FormData();
        formData.append('twin_id', twinData.id);
        files.forEach(f => formData.append('files', f));
        const modeAResponse = await authFetchStandalone('/persona/link-compile/jobs/mode-a', {
          method: 'POST',
          body: formData,
        });
        if (!modeAResponse.ok) throw new Error('Failed to submit uploaded files');
      }

      // Submit paste (Mode B)
      const pasteSources = sources.filter(s => s.type === 'paste');
      for (const paste of pasteSources) {
        const modeBResponse = await authFetchStandalone('/persona/link-compile/jobs/mode-b', {
          method: 'POST',
          body: JSON.stringify({
            twin_id: twinData.id,
            content: paste.value,
            title: paste.category || 'Pasted Content',
          }),
        });
        if (!modeBResponse.ok) throw new Error('Failed to submit pasted content');
      }

      // Submit URLs (Mode C)
      if (allUrls.length > 0) {
        const modeCResponse = await authFetchStandalone('/persona/link-compile/jobs/mode-c', {
          method: 'POST',
          body: JSON.stringify({
            twin_id: twinData.id,
            urls: allUrls,
          }),
        });
        if (!modeCResponse.ok) {
          let detailMessage = `Failed to submit URLs (${modeCResponse.status})`;
          try {
            const payload = await modeCResponse.json();
            const detail = payload?.detail;
            if (typeof detail === 'string' && detail.trim()) detailMessage = detail.trim();
            else if (detail && typeof detail?.message === 'string') detailMessage = detail.message.trim();
          } catch { /* ignore */ }
          throw new Error(detailMessage);
        }
      }

      setCurrentStep('research');
    } catch (error) {
      console.error('Failed to create twin:', error);
      let rollbackApplied = false;
      if (createdProfileInAttempt) {
        try {
          const rollbackResponse = await authFetchStandalone('/profile/reset', { method: 'POST' });
          rollbackApplied = rollbackResponse.ok;
        } catch (rollbackError) {
          console.error('Failed to rollback profile:', rollbackError);
        }
      }
      let message = error instanceof Error && error.message ? error.message : 'Failed to create twin. Please try again.';
      if (createdProfileInAttempt && rollbackApplied) {
        message = `${message}\n\nProfile reset automatically — you can retry.`;
      } else if (createdProfileInAttempt && !rollbackApplied) {
        message = `${message}\n\nA partial profile may exist. Use Settings → Reset Profile before retrying.`;
      }
      setSubmitError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResearchComplete = (researchRunId?: string) => {
    trackEvent('onboarding_research_completed', { twin_id: twin?.id, research_run_id: researchRunId });
    if (twin?.id) {
      try { localStorage.setItem('activeTwinId', twin.id); } catch { /* non-blocking */ }
      const params = new URLSearchParams();
      params.set('from', 'onboarding');
      if (researchRunId) params.set('researchRunId', researchRunId);
      router.push(returnTo ?? `/dashboard/profile?${params.toString()}`);
    }
  };

  const handleResearchBack = () => {
    setCurrentStep('input');
  };

  // Loading spinner while initial profile call is in flight
  if (isLoading && currentStep === 'input') {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-white">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p>Creating your persona…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950">
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">Create Your Persona</h1>
            <p className="text-sm text-slate-400">
              {currentStep === 'input' ? 'Get started in 2 minutes' : 'Research in progress'}
            </p>
          </div>
          {twin && (
            <div className="text-sm text-slate-400 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
              Profile Building
            </div>
          )}
        </div>
      </header>

      {currentStep === 'research' && (
        <div className="max-w-4xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            {[
              { key: 'input', label: 'Input' },
              { key: 'research', label: 'Research' },
              { key: 'complete', label: 'Complete' },
            ].map((step, idx) => {
              const isActive = currentStep === step.key || (step.key === 'complete' && currentStep === 'research');
              const isPast = step.key === 'input' && currentStep === 'research';
              return (
                <React.Fragment key={step.key}>
                  <div className={`flex flex-col items-center ${isActive ? 'text-blue-400' : isPast ? 'text-green-400' : 'text-slate-600'}`}>
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                      isActive ? 'bg-blue-500/20 border-2 border-blue-500' :
                      isPast ? 'bg-green-500/20 border-2 border-green-500' :
                      'bg-slate-800 border-2 border-slate-700'
                    }`}>
                      {isPast ? '✓' : idx + 1}
                    </div>
                    <span className="text-xs mt-1">{step.label}</span>
                  </div>
                  {idx < 2 && (
                    <div className={`flex-1 h-0.5 mx-2 ${isPast ? 'bg-green-500/50' : 'bg-slate-800'}`} />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      )}

      <main className="max-w-3xl mx-auto px-4 pb-32 pt-8">
        {currentStep === 'input' && (
          <>
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
            <UnifiedInputStep onSubmit={handleInputSubmit} />
          </>
        )}
        {currentStep === 'deep-research' && inputData && (
          <DeepResearchProgress status={deepResearchStatus} name={inputData.fullName} />
        )}
        {currentStep === 'research' && inputData && twin && (
          <StepResearch
            twinId={twin.id}
            claimedIdentity={{
              fullName: inputData.fullName,
              location: inputData.location,
              headline: inputData.headline,
              role: inputData.headline,
            }}
            seedUrls={submittedUrls}
            onComplete={handleResearchComplete}
            onBack={handleResearchBack}
          />
        )}
      </main>
    </div>
  );
}

export default function OnboardingPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-950 flex items-center justify-center text-white">Loading...</div>}>
      <OnboardingContent />
    </Suspense>
  );
}
