'use client';

import React, { useState, Suspense, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { UnifiedInputStep, type UnifiedInputData } from '@/components/onboarding/steps/UnifiedInputStep';
import { StepResearch } from '@/components/onboarding/steps/StepResearch';
import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';

// =============================================================================
// Types
// =============================================================================

type OnboardingStep = 'input' | 'research';

interface Twin {
  id: string;
  name: string;
  status: string;
  specialization?: string;
  settings?: Record<string, unknown>;
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

  const trackEvent = useCallback((event: string, properties?: Record<string, unknown>) => {
    if (typeof window !== 'undefined' && (window as unknown as { posthog?: { capture: (e: string, p?: Record<string, unknown>) => void } }).posthog) {
      (window as unknown as { posthog: { capture: (e: string, p?: Record<string, unknown>) => void } }).posthog.capture(event, properties);
    }
    console.log(`[Telemetry] ${event}`, properties);
  }, []);

  const handleInputSubmit = async (data: UnifiedInputData) => {
    setInputData(data);
    trackEvent('onboarding_started', {
      has_headline: !!data.headline,
      has_location: !!data.location,
      has_linkedin: !!data.linkedInUrl,
      has_sources: !!(data.sources && data.sources.length > 0),
    });

    setIsLoading(true);
    try {
      const sources = data.sources ?? [];
      const hasOptionalSources = sources.length > 0 || Boolean(data.linkedInUrl?.trim());
      const buildMode: 'with_links' | 'name_only' = hasOptionalSources ? 'with_links' : 'name_only';

      const profileResponse = await authFetchStandalone('/profile', {
        method: 'POST',
        body: JSON.stringify({
          full_name: data.fullName,
          headline: data.headline,
          build_mode: buildMode,
        }),
      });

      if (!profileResponse.ok) {
        let detailMessage = `Failed to create profile (${profileResponse.status})`;
        try {
          const payload = await profileResponse.json();
          const detail = payload?.detail;
          if (typeof detail === 'string' && detail.trim()) detailMessage = detail.trim();
          else if (detail && typeof detail?.message === 'string' && detail.message.trim()) detailMessage = detail.message.trim();
          else if (typeof payload?.message === 'string' && payload.message.trim()) detailMessage = payload.message.trim();
        } catch {
          // Ignore
        }
        throw new Error(detailMessage);
      }

      const profileData = await profileResponse.json();
      const twinData: Twin = {
        id: profileData.id,
        name: profileData.name,
        status: profileData.status || 'draft',
        specialization: profileData.specialization || 'vanilla',
        settings: profileData.settings,
      };
      setTwin(twinData);

      const urls: string[] = [];

      for (const s of sources) {
        if (s.type === 'link' && s.value.trim() && s.value.startsWith('http')) {
          urls.push(s.value.trim());
        }
      }
      if (data.linkedInUrl?.trim() && data.linkedInUrl.startsWith('http') && !urls.includes(data.linkedInUrl.trim())) {
        urls.push(data.linkedInUrl.trim());
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
            else if (detail && typeof detail?.message === 'string' && detail.message.trim()) detailMessage = detail.message.trim();
          } catch {
            // Ignore
          }
          throw new Error(detailMessage);
        }
      }

      setCurrentStep('research');
    } catch (error) {
      console.error('Failed to create twin:', error);
      const message = error instanceof Error && error.message ? error.message : 'Failed to create twin. Please try again.';
      alert(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResearchComplete = (researchRunId?: string) => {
    trackEvent('onboarding_research_completed', { twin_id: twin?.id, research_run_id: researchRunId });
    if (twin?.id) {
      try {
        localStorage.setItem('activeTwinId', twin.id);
      } catch {
        // Non-blocking
      }
      const params = new URLSearchParams();
      params.set('from', 'onboarding');
      if (researchRunId) params.set('researchRunId', researchRunId);
      router.push(returnTo ?? `/dashboard/profile?${params.toString()}`);
    }
  };

  const handleResearchBack = () => {
    setCurrentStep('input');
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-white">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p>Creating your twin...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950">
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">Create Digital Twin</h1>
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
                  <div className={`flex flex-col items-center ${isActive ? 'text-indigo-400' : isPast ? 'text-green-400' : 'text-slate-600'}`}>
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                      isActive ? 'bg-indigo-500/20 border-2 border-indigo-500' :
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
        {currentStep === 'input' && <UnifiedInputStep onSubmit={handleInputSubmit} />}
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
