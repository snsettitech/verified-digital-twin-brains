'use client';

import React, { useState, Suspense, useEffect, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

// Redirect legacy onboarding to v2
function LegacyOnboardingRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/onboarding/v2');
  }, [router]);
  return null;
}

import { StepWelcome, type WelcomeData } from '@/components/onboarding/steps/StepWelcome';
import { StepLinkSuggestions } from '@/components/onboarding/steps/StepLinkSuggestions';
import { StepAddSources } from '@/components/onboarding/steps/StepAddSources';
import { StepBuilding } from '@/components/onboarding/steps/StepBuilding';
import { StepProfileLanding } from '@/components/onboarding/steps/StepProfileLanding';
import { StepClaimReview } from '@/components/onboarding/steps/StepClaimReview';
import { StepClarification } from '@/components/onboarding/steps/StepClarification';
import { StepResearch } from '@/components/onboarding/steps/StepResearch';
import { StepSourceReview } from '@/components/onboarding/steps/StepSourceReview';
import { Step1Identity, IdentityFormData } from '@/components/onboarding/steps/Step1Identity';
import { Step2ThinkingStyle } from '@/components/onboarding/steps/Step2ThinkingStyle';
import { Step3Values } from '@/components/onboarding/steps/Step3Values';
import { Step4Communication } from '@/components/onboarding/steps/Step4Communication';
import { Step5Memory } from '@/components/onboarding/steps/Step5Memory';
import { Step6Review } from '@/components/onboarding/steps/Step6Review';
import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';

// =============================================================================
// Types
// =============================================================================

type FlowType = 'link_first' | 'manual' | null;
type OnboardingStep = 
  | 'welcome'
  | 'link_suggestions'
  | 'add_sources'
  | 'source_review'
  | 'research'  // Phase 7: Deep Research flow
  | 'building'
  | 'profile'
  | 'claim_review'
  | 'clarification'
  // Manual flow steps
  | 'manual_identity'
  | 'manual_thinking'
  | 'manual_values'
  | 'manual_communication'
  | 'manual_memory'
  | 'manual_review';

type TwinStatus = 'draft' | 'ingesting' | 'claims_ready' | 'clarification_pending' | 'persona_built' | 'active';

interface Twin {
  id: string;
  name: string;
  status: TwinStatus;
  specialization: string;
  settings?: Record<string, unknown>;
}


interface ThinkingStyleData {
  decisionFramework: string;
  heuristics: string[];
  customHeuristics: string;
  clarifyingBehavior: 'ask' | 'infer';
  evidenceStandards: string[];
}

interface ValueItem {
  id: string;
  name: string;
  description: string;
}

interface ValuesData {
  prioritizedValues: ValueItem[];
  tradeoffNotes: string;
}

interface PersonalityData {
  tone: string;
  responseLength: string;
  firstPerson: boolean;
  customInstructions: string;
  signaturePhrases: string[];
}

interface MemoryAnchor {
  id: string;
  type: 'experience' | 'lesson' | 'pattern';
  content: string;
  context: string;
  tags: string[];
}

interface MemoryData {
  experiences: MemoryAnchor[];
  lessons: MemoryAnchor[];
  patterns: MemoryAnchor[];
}

// =============================================================================
// Component
// =============================================================================

function OnboardingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  
  // Redirect to v2 onboarding (legacy onboarding deprecated)
  useEffect(() => {
    router.replace('/onboarding/v2');
  }, [router]);
  
  const returnTo = searchParams.get('returnTo');
  const resumeTwinId = searchParams.get('twinId');

  // Flow state
  const [flowType, setFlowType] = useState<FlowType>(null);
  const [currentStep, setCurrentStep] = useState<OnboardingStep>('welcome');
  
  // Data state
  const [welcomeData, setWelcomeData] = useState<WelcomeData | null>(null);
  const [suggestedUrls, setSuggestedUrls] = useState<string[]>([]);
  const [lastSubmittedSources, setLastSubmittedSources] = useState<Array<{ type: string; value: string; status?: string }>>([]);
  const [submittedUrls, setSubmittedUrls] = useState<string[]>([]);
  const [researchRunId, setResearchRunId] = useState<string | null>(null);
  const [twin, setTwin] = useState<Twin | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Manual flow form data
  const [identityData, setIdentityData] = useState<IdentityFormData>({
    twinName: '',
    handle: '',
    tagline: '',
    expertise: [],
    customExpertise: [],
    goals90Days: ['', '', ''],
    boundaries: '',
    privacyConstraints: '',
    uncertaintyPreference: 'ask',
  });
  const [specialization, setSpecialization] = useState('vanilla');
  const [thinkingData, setThinkingData] = useState<ThinkingStyleData>({
    decisionFramework: 'evidence_based',
    heuristics: [],
    customHeuristics: '',
    clarifyingBehavior: 'ask',
    evidenceStandards: [],
  });
  const [valuesData, setValuesData] = useState<ValuesData>({
    prioritizedValues: [],
    tradeoffNotes: '',
  });
  const [personalityData, setPersonalityData] = useState<PersonalityData>({
    tone: 'friendly',
    responseLength: 'balanced',
    firstPerson: true,
    customInstructions: '',
    signaturePhrases: [],
  });
  const [memoryData, setMemoryData] = useState<MemoryData>({
    experiences: [],
    lessons: [],
    patterns: [],
  });

  // =============================================================================
  // Telemetry
  // =============================================================================

  const trackEvent = useCallback((event: string, properties?: Record<string, unknown>) => {
    if (typeof window !== 'undefined' && (window as unknown as { posthog?: { capture: (e: string, p?: Record<string, unknown>) => void } }).posthog) {
      (window as unknown as { posthog: { capture: (e: string, p?: Record<string, unknown>) => void } }).posthog.capture(event, properties);
    }
    console.log(`[Telemetry] ${event}`, properties);
  }, []);

  const manualStepOrder: OnboardingStep[] = [
    'manual_identity',
    'manual_thinking',
    'manual_values',
    'manual_communication',
    'manual_memory',
    'manual_review',
  ];

  const getManualStepIndex = (step: OnboardingStep) => manualStepOrder.indexOf(step);

  const goToNextManualStep = () => {
    const currentIndex = getManualStepIndex(currentStep);
    if (currentIndex >= 0 && currentIndex < manualStepOrder.length - 1) {
      setCurrentStep(manualStepOrder[currentIndex + 1]);
    }
  };

  const goToPreviousManualStep = () => {
    const currentIndex = getManualStepIndex(currentStep);
    if (currentIndex > 0) {
      setCurrentStep(manualStepOrder[currentIndex - 1]);
    }
  };

  // =============================================================================
  // Resume onboarding if twinId provided
  // =============================================================================

  useEffect(() => {
    if (resumeTwinId) {
      setIsLoading(true);
      fetchTwin(resumeTwinId).then((twinData) => {
        if (twinData) {
          setTwin(twinData);
          // Determine where to resume based on status
          switch (twinData.status) {
            case 'draft':
              setFlowType('link_first');
              setCurrentStep('add_sources');
              break;
            case 'ingesting':
              setFlowType('link_first');
              setCurrentStep('building');
              break;
            case 'claims_ready':
              setFlowType('link_first');
              setCurrentStep('profile');
              break;
            case 'clarification_pending':
              setFlowType('link_first');
              setCurrentStep('clarification');
              break;
            case 'persona_built':
            case 'active':
              setFlowType('link_first');
              setCurrentStep('profile');
              break;
          }
        }
        setIsLoading(false);
      });
    }
  }, [resumeTwinId]);

  const fetchTwin = async (twinId: string): Promise<Twin | null> => {
    const response = await authFetchStandalone(`/twins/${twinId}`);

    if (!response.ok) return null;
    return response.json();
  };

  // =============================================================================
  // Welcome Step Handler
  // =============================================================================

  const handleWelcomeSubmit = async (data: WelcomeData) => {
    setWelcomeData(data);
    trackEvent('onboarding_started', { 
      mode: data.manualMode ? 'manual' : 'link_first',
      has_location: !!data.location,
      has_role: !!data.role,
    });

    if (data.manualMode) {
      // Switch to manual flow
      setFlowType('manual');
      setCurrentStep('manual_identity');
      setIdentityData(prev => ({ ...prev, twinName: data.fullName }));
    } else {
      // Create draft twin and go to link suggestions
      setIsLoading(true);
      const twinData = await createDraftTwin(data);
      if (twinData) {
        setTwin(twinData);
        setFlowType('link_first');
        setCurrentStep('link_suggestions');
      }
      setIsLoading(false);
    }
  };

  const createDraftTwin = async (data: WelcomeData): Promise<Twin | null> => {
    try {
      const displayName = data.preferredTwinName?.trim()
        ? `${data.preferredTwinName.trim()} (Draft)`
        : `${data.fullName} (Draft)`;
      const settings: Record<string, unknown> = {};
      if (data.headline) settings.headline = data.headline;
      if (data.preferredTwinName) settings.preferred_twin_name = data.preferredTwinName;
      const response = await authFetchStandalone('/twins', {
        method: 'POST',
        body: JSON.stringify({
          name: displayName,
          mode: 'link_first',
          specialization: 'vanilla',
          settings: Object.keys(settings).length > 0 ? settings : undefined,
        }),
      });

      if (!response.ok) throw new Error('Failed to create twin');
      return response.json();
    } catch (error) {
      console.error('Failed to create draft twin:', error);
      alert('Failed to create twin. Please try again.');
      return null;
    }
  };

  // =============================================================================
  // Link Suggestions Handler
  // =============================================================================

  const handleLinkSuggestionsComplete = (urls: string[]) => {
    setSuggestedUrls(urls);
    trackEvent('link_suggestions_completed', { 
      twin_id: twin?.id,
      selected_count: urls.length 
    });
    setCurrentStep('add_sources');
  };

  const handleLinkSuggestionsSkip = () => {
    trackEvent('link_suggestions_skipped', { twin_id: twin?.id });
    setCurrentStep('add_sources');
  };

  // =============================================================================
  // Add Sources Handler
  // =============================================================================

  const handleAddSources = async (sources: { type: string; value: string; category?: string; file?: File }[]) => {
    if (!twin) return;
    
    setIsLoading(true);
    trackEvent('sources_submitted', { 
      twin_id: twin.id,
      source_count: sources.length,
      has_files: sources.some(s => s.type === 'export'),
      has_links: sources.some(s => s.type === 'link'),
      has_paste: sources.some(s => s.type === 'paste'),
    });

    // Submit sources to backend
    try {
      // Handle files (Mode A)
      const files = sources.filter(s => s.type === 'export' && s.file).map(s => s.file!);
      if (files.length > 0) {
        const formData = new FormData();
        formData.append('twin_id', twin.id);
        files.forEach(f => formData.append('files', f));
        
        const modeAResponse = await authFetchStandalone('/persona/link-compile/jobs/mode-a', {
          method: 'POST',
          body: formData,
        });
        if (!modeAResponse.ok) {
          throw new Error('Failed to submit uploaded files');
        }
      }

      // Handle paste (Mode B)
      const pasteSources = sources.filter(s => s.type === 'paste');
      for (const paste of pasteSources) {
        const modeBResponse = await authFetchStandalone('/persona/link-compile/jobs/mode-b', {
          method: 'POST',
          body: JSON.stringify({
            twin_id: twin.id,
            content: paste.value,
            title: paste.category || 'Pasted Content',
          }),
        });
        if (!modeBResponse.ok) {
          throw new Error('Failed to submit pasted content');
        }
      }

      // Handle URLs (Mode C)
      const urls = sources
        .filter(s => s.type === 'link')
        .map(s => s.value.trim())
        .filter(Boolean);
      const allUrls = [...new Set([...suggestedUrls.map((u) => u.trim()), ...urls])]
        .filter((url) => Boolean(url) && /^https?:\/\//i.test(url));
      setSubmittedUrls(allUrls);
      if (allUrls.length > 0) {
        const modeCResponse = await authFetchStandalone('/persona/link-compile/jobs/mode-c', {
          method: 'POST',
          body: JSON.stringify({
            twin_id: twin.id,
            urls: allUrls,
          }),
        });
        if (!modeCResponse.ok) {
          let detailMessage = `Failed to submit URLs (${modeCResponse.status})`;
          try {
            const payload = await modeCResponse.json();
            const detail = payload?.detail;
            if (typeof detail === 'string' && detail.trim()) {
              detailMessage = detail.trim();
            } else if (detail && typeof detail?.message === 'string' && detail.message.trim()) {
              detailMessage = detail.message.trim();
            }
          } catch {
            // Ignore parsing error and keep fallback detail message.
          }
          throw new Error(detailMessage);
        }
      }

      // Store sources for review step (suggested URLs + form sources, deduped)
      const seen = new Set<string>();
      const reviewSources: Array<{ type: string; value: string; status?: string }> = [];
      for (const url of suggestedUrls) {
        if (url && !seen.has(url)) {
          seen.add(url);
          reviewSources.push({ type: 'link', value: url, status: 'Ready' });
        }
      }
      for (const s of sources) {
        const val =
          s.type === 'link' ? s.value : s.type === 'paste' ? (s.category || 'Pasted Content') : s.value;
        if (s.type === 'link' && seen.has(val)) continue;
        if (s.type === 'link') seen.add(val);
        reviewSources.push({ type: s.type, value: val, status: 'Ready' });
      }
      setLastSubmittedSources(reviewSources);
      setCurrentStep('source_review');
    } catch (error) {
      console.error('Failed to submit sources:', error);
      const message = error instanceof Error && error.message
        ? error.message
        : 'Failed to submit sources. Please try again.';
      alert(message);
    } finally {
      setIsLoading(false);
    }
  };

  // =============================================================================
  // Source Review Handler
  // =============================================================================

  const handleSourceReviewComplete = () => {
    setCurrentStep('research');
  };

  // =============================================================================
  // Building Handler
  // =============================================================================

  const handleBuildingComplete = () => {
    trackEvent('building_completed', { twin_id: twin?.id });
    setCurrentStep('profile');
  };

  // =============================================================================
  // Profile Landing Handlers
  // =============================================================================

  const handleProfileActivate = () => {
    trackEvent('persona_activated', { twin_id: twin?.id });
    if (twin?.id) {
      try {
        localStorage.setItem('activeTwinId', twin.id);
      } catch {
        // Non-blocking storage write.
      }
      router.push(returnTo || '/dashboard/chat');
    }
  };

  const handleProfileReviewClaims = () => {
    setCurrentStep('claim_review');
  };

  const handleProfileAddSources = () => {
    setCurrentStep('add_sources');
  };

  // =============================================================================
  // Claim Review Handler
  // =============================================================================

  const handleClaimReviewComplete = () => {
    setCurrentStep('clarification');
  };

  // =============================================================================
  // Clarification Handler
  // =============================================================================

  const handleClarificationComplete = () => {
    trackEvent('clarification_completed', { twin_id: twin?.id });
    setCurrentStep('profile');
  };

  // =============================================================================
  // Manual Flow Handlers
  // =============================================================================

  const handleManualComplete = async () => {
    // Create manual twin
    setIsLoading(true);
    try {
      const response = await authFetchStandalone('/twins', {
        method: 'POST',
        body: JSON.stringify({
          name: identityData.twinName,
          mode: 'manual',
          specialization,
          settings: {
            handle: identityData.handle || undefined,
            tagline: identityData.tagline || undefined,
          },
          persona_v2_data: {
            identity: {
              ...identityData,
              specialization,
            },
            thinking_style: thinkingData,
            value_hierarchy: valuesData,
            communication: personalityData,
            memory_anchors: memoryData,
          },
        }),
      });

      if (!response.ok) throw new Error('Failed to create twin');
      
      const newTwin: Twin = await response.json();
      try {
        localStorage.setItem('activeTwinId', newTwin.id);
      } catch {
        // Non-blocking storage write.
      }
      router.push(returnTo || '/dashboard/chat');
    } catch (error) {
      console.error('Failed to create manual twin:', error);
      alert('Failed to create twin. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const renderManualNavigation = (nextLabel = 'Next →', nextDisabled = false) => (
    <div className="mt-8 flex items-center justify-between gap-3">
      <button
        onClick={goToPreviousManualStep}
        disabled={currentStep === 'manual_identity'}
        className="px-5 py-3 border border-slate-700 text-slate-300 rounded-xl hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        ← Back
      </button>
      <button
        onClick={goToNextManualStep}
        disabled={nextDisabled}
        className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {nextLabel}
      </button>
    </div>
  );

  // =============================================================================
  // Render Current Step
  // =============================================================================

  const renderStep = () => {
    switch (currentStep) {
      case 'welcome':
        return <StepWelcome onSubmit={handleWelcomeSubmit} />;

      case 'link_suggestions':
        return welcomeData ? (
          <StepLinkSuggestions
            twinId={twin?.id || null}
            fullName={welcomeData.fullName}
            location={welcomeData.location}
            role={welcomeData.role}
            onComplete={handleLinkSuggestionsComplete}
            onSkip={handleLinkSuggestionsSkip}
          />
        ) : null;

      case 'add_sources':
        return (
          <StepAddSources
            twinId={twin?.id || null}
            initialUrls={suggestedUrls}
            onSubmit={handleAddSources}
            onBack={() => setCurrentStep(flowType === 'link_first' ? 'link_suggestions' : 'welcome')}
          />
        );

      case 'source_review':
        return (
          <StepSourceReview
            sources={lastSubmittedSources}
            onSubmit={handleSourceReviewComplete}
            onBack={() => setCurrentStep('add_sources')}
          />
        );

      case 'research':
        return welcomeData ? (
          <StepResearch
            twinId={twin?.id || null}
            claimedIdentity={{
              fullName: welcomeData.fullName,
              location: welcomeData.location,
              role: welcomeData.role,
              headline: welcomeData.headline,
              preferredTwinName: welcomeData.preferredTwinName,
            }}
            seedUrls={submittedUrls.length > 0 ? submittedUrls : suggestedUrls}
            onComplete={(runId) => {
              if (runId) {
                setResearchRunId(runId);
              }
              if (twin?.id) {
                try {
                  localStorage.setItem('activeTwinId', twin.id);
                } catch {
                  // Non-blocking localStorage write
                }
                const params = new URLSearchParams();
                params.set('from', 'onboarding');
                if (runId) {
                  params.set('researchRunId', runId);
                }
                router.push(`/dashboard/profile?${params.toString()}`);
                return;
              }
              setCurrentStep('profile');
            }}
            onBack={() => setCurrentStep('source_review')}
          />
        ) : null;

      case 'building':
        return (
          <StepBuilding
            twinId={twin?.id || null}
            onComplete={handleBuildingComplete}
          />
        );

      case 'profile':
        return (
          <StepProfileLanding
            twinId={twin?.id || null}
            onActivate={handleProfileActivate}
            onReviewClaims={handleProfileReviewClaims}
            onAddMoreSources={handleProfileAddSources}
          />
        );

      case 'claim_review':
        return (
          <StepClaimReview
            twinId={twin?.id || null}
            researchRunId={researchRunId}
            onApprove={handleClaimReviewComplete}
          />
        );

      case 'clarification':
        return (
          <StepClarification
            twinId={twin?.id || null}
            onComplete={handleClarificationComplete}
          />
        );

      // Manual flow steps
      case 'manual_identity':
        return (
          <>
            <Step1Identity
              data={identityData}
              onChange={setIdentityData}
              onSpecializationChange={setSpecialization}
            />
            {renderManualNavigation('Next: Thinking Style →', !identityData.twinName.trim())}
          </>
        );

      case 'manual_thinking':
        return (
          <>
            <Step2ThinkingStyle
              data={thinkingData}
              onChange={setThinkingData}
            />
            {renderManualNavigation('Next: Values →')}
          </>
        );

      case 'manual_values':
        return (
          <>
            <Step3Values
              data={valuesData}
              onChange={setValuesData}
              specialization={specialization}
            />
            {renderManualNavigation('Next: Communication →')}
          </>
        );

      case 'manual_communication':
        return (
          <>
            <Step4Communication
              personality={personalityData}
              onPersonalityChange={setPersonalityData}
            />
            {renderManualNavigation('Next: Memory Anchors →')}
          </>
        );

      case 'manual_memory':
        return (
          <>
            <Step5Memory
              data={memoryData}
              onChange={setMemoryData}
            />
            {renderManualNavigation('Review & Launch →')}
          </>
        );

      case 'manual_review':
        return (
          <Step6Review
            data={{
              twinName: identityData.twinName,
              tagline: identityData.tagline,
              specialization,
              expertise: [...identityData.expertise, ...identityData.customExpertise],
              decisionFramework: thinkingData.decisionFramework,
              heuristics: thinkingData.heuristics,
              clarifyingBehavior: thinkingData.clarifyingBehavior,
              prioritizedValues: valuesData.prioritizedValues,
              personality: {
                tone: personalityData.tone,
                responseLength: personalityData.responseLength,
                firstPerson: personalityData.firstPerson,
              },
              memoryCount:
                memoryData.experiences.length +
                memoryData.lessons.length +
                memoryData.patterns.length,
            }}
            onTestChat={() => trackEvent('manual_review_test_chat_clicked')}
            onEditStep={(stepNumber) => {
              const manualStepMap: OnboardingStep[] = [
                'manual_identity',
                'manual_thinking',
                'manual_values',
                'manual_communication',
                'manual_memory',
              ];
              const index = Math.max(0, Math.min(stepNumber - 1, manualStepMap.length - 1));
              setCurrentStep(manualStepMap[index]);
            }}
            onLaunch={handleManualComplete}
            isLaunching={isLoading}
          />
        );

      default:
        return null;
    }
  };

  // =============================================================================
  // Loading State
  // =============================================================================

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-white">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p>{currentStep === 'welcome' ? 'Creating your twin...' : 'Processing...'}</p>
        </div>
      </div>
    );
  }

  // =============================================================================
  // Main Render
  // =============================================================================

  return (
    <div className="min-h-screen bg-slate-950">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">Create Digital Twin</h1>
            <p className="text-sm text-slate-400">
              {flowType === 'link_first' ? 'Link-First Mode' : 
               flowType === 'manual' ? 'Manual Setup' : 
               'Get started in 2 minutes'}
            </p>
          </div>
          {twin && (
            <div className="text-sm text-slate-400 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
              Draft Mode
            </div>
          )}
        </div>
      </header>

      {/* Progress Indicator (Link-First Flow) */}
      {flowType === 'link_first' && currentStep !== 'welcome' && (
        <div className="max-w-4xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            {[
              { key: 'link_suggestions', label: 'Find' },
              { key: 'add_sources', label: 'Add' },
              { key: 'source_review', label: 'Review' },
              { key: 'research', label: 'Research' },
              { key: 'profile', label: 'Profile' },
            ].map((step, idx, arr) => {
              const stepOrder = ['link_suggestions', 'add_sources', 'source_review', 'research', 'building', 'profile'];
              const isActive = currentStep === step.key;
              const isPast = stepOrder.indexOf(currentStep) > stepOrder.indexOf(step.key);
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
                  {idx < arr.length - 1 && (
                    <div className={`flex-1 h-0.5 mx-2 ${isPast ? 'bg-green-500/50' : 'bg-slate-800'}`} />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      )}

      {/* Progress Indicator (Manual Flow) */}
      {flowType === 'manual' && currentStep !== 'welcome' && (
        <div className="max-w-4xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            {[
              { key: 'manual_identity', label: 'Identity' },
              { key: 'manual_thinking', label: 'Thinking' },
              { key: 'manual_values', label: 'Values' },
              { key: 'manual_communication', label: 'Voice' },
              { key: 'manual_memory', label: 'Memory' },
              { key: 'manual_review', label: 'Review' },
            ].map((step, idx, arr) => {
              const isActive = currentStep === step.key;
              const isPast = getManualStepIndex(currentStep) > getManualStepIndex(step.key as OnboardingStep);
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
                  {idx < arr.length - 1 && (
                    <div className={`flex-1 h-0.5 mx-2 ${isPast ? 'bg-green-500/50' : 'bg-slate-800'}`} />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-3xl mx-auto px-4 pb-32 pt-8">
        {renderStep()}
      </main>
    </div>
  );
}

// Wrapper component with Suspense boundary
export default function OnboardingPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-950 flex items-center justify-center text-white">Loading...</div>}>
      <OnboardingContent />
    </Suspense>
  );
}
