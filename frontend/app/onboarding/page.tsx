'use client';

import React, { useState, Suspense, useEffect, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import { StepIndicator } from '@/components/onboarding/StepIndicator';
import { StepModeSelect } from '@/components/onboarding/steps/StepModeSelect';
import { StepLinkSubmission } from '@/components/onboarding/steps/StepLinkSubmission';
import { StepIngestionProgress } from '@/components/onboarding/steps/StepIngestionProgress';
import { StepClaimReview } from '@/components/onboarding/steps/StepClaimReview';
import { StepClarification } from '@/components/onboarding/steps/StepClarification';
import { StepPersonaPreview } from '@/components/onboarding/steps/StepPersonaPreview';
import { Step1Identity, IdentityFormData } from '@/components/onboarding/steps/Step1Identity';
import { Step2ThinkingStyle } from '@/components/onboarding/steps/Step2ThinkingStyle';
import { Step3Values } from '@/components/onboarding/steps/Step3Values';
import { Step4Communication } from '@/components/onboarding/steps/Step4Communication';
import { Step5Memory } from '@/components/onboarding/steps/Step5Memory';
import { Step6Review } from '@/components/onboarding/steps/Step6Review';
import { getSupabaseClient } from '@/lib/supabase/client';
import { API_BASE_URL } from '@/lib/constants';

// =============================================================================
// Types
// =============================================================================

type OnboardingMode = 'manual' | 'link_first' | null;
type LinkFirstStep = 'mode-select' | 'link-submission' | 'ingestion' | 'claims' | 'clarification' | 'preview';
type TwinStatus = 'draft' | 'ingesting' | 'claims_ready' | 'clarification_pending' | 'persona_built' | 'active';

interface ThinkingStyleData {
  decisionFramework: string;
  heuristics: string[];
  customHeuristics: string;
  clarifyingBehavior: 'ask' | 'infer';
  evidenceStandards: string[];
}

interface ValuesData {
  prioritizedValues: { id: string; name: string; description: string }[];
  tradeoffNotes: string;
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

interface Twin {
  id: string;
  name: string;
  status: TwinStatus;
  specialization: string;
  settings?: {
    link_first_urls?: string[];
  };
}

// =============================================================================
// Feature Flag
// =============================================================================

const LINK_FIRST_ENABLED = process.env.NEXT_PUBLIC_LINK_FIRST_ENABLED === 'true';

// =============================================================================
// Default Data
// =============================================================================

const defaultIdentityData: IdentityFormData = {
  twinName: '',
  handle: '',
  tagline: '',
  expertise: [],
  customExpertise: [],
  goals90Days: ['', '', ''],
  boundaries: '',
  privacyConstraints: '',
  uncertaintyPreference: 'ask',
};

const defaultThinkingData: ThinkingStyleData = {
  decisionFramework: 'evidence_based',
  heuristics: [],
  customHeuristics: '',
  clarifyingBehavior: 'ask',
  evidenceStandards: ['source_credibility', 'recency', 'relevance'],
};

const defaultValuesData: ValuesData = {
  prioritizedValues: [],
  tradeoffNotes: '',
};

const defaultMemoryData: MemoryData = {
  experiences: [],
  lessons: [],
  patterns: [],
};

// =============================================================================
// Component
// =============================================================================

function OnboardingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnTo = searchParams.get('returnTo');
  const resumeTwinId = searchParams.get('twinId');

  // Mode and flow state
  const [mode, setMode] = useState<OnboardingMode>(null);
  const [linkFirstStep, setLinkFirstStep] = useState<LinkFirstStep>('mode-select');
  
  // Manual flow state
  const [currentStep, setCurrentStep] = useState(1);
  const [isLaunching, setIsLaunching] = useState(false);

  // Link-first flow state
  const [twin, setTwin] = useState<Twin | null>(null);
  const [isLoadingTwin, setIsLoadingTwin] = useState(false);

  // Form data state (manual mode)
  const [identityData, setIdentityData] = useState<IdentityFormData>(defaultIdentityData);
  const [personalityData, setPersonalityData] = useState({
    tone: 'professional',
    responseLength: 'balanced',
    firstPerson: true,
    customInstructions: '',
    signaturePhrases: [] as string[],
  });
  const [thinkingData, setThinkingData] = useState<ThinkingStyleData>(defaultThinkingData);
  const [valuesData, setValuesData] = useState<ValuesData>(defaultValuesData);
  const [memoryData, setMemoryData] = useState<MemoryData>(defaultMemoryData);
  const [specialization, setSpecialization] = useState('vanilla');

  // =============================================================================
  // Resume onboarding if twinId provided
  // =============================================================================

  const fetchTwin = useCallback(async (twinId: string): Promise<Twin | null> => {
    const supabase = getSupabaseClient();
    const { data: sessionData } = await supabase.auth.getSession();
    const token = sessionData?.session?.access_token;

    const response = await fetch(`${API_BASE_URL}/twins/${twinId}`, {
      headers: token ? { 'Authorization': `Bearer ${token}` } : {},
    });

    if (!response.ok) return null;
    return response.json();
  }, []);

  useEffect(() => {
    if (resumeTwinId) {
      setIsLoadingTwin(true);
      fetchTwin(resumeTwinId).then((twinData) => {
        if (twinData) {
          setTwin(twinData);
          // Determine where to resume based on status
          if (twinData.status === 'draft') {
            setMode('link_first');
            setLinkFirstStep('link-submission');
          } else if (twinData.status === 'ingesting') {
            setMode('link_first');
            setLinkFirstStep('ingestion');
          } else if (twinData.status === 'claims_ready') {
            setMode('link_first');
            setLinkFirstStep('claims');
          } else if (twinData.status === 'clarification_pending') {
            setMode('link_first');
            setLinkFirstStep('clarification');
          } else if (twinData.status === 'persona_built') {
            setMode('link_first');
            setLinkFirstStep('preview');
          } else if (twinData.status === 'active') {
            // Twin is already active, redirect to chat
            router.push(returnTo || `/chat?twinId=${twinData.id}`);
          }
        }
        setIsLoadingTwin(false);
      });
    }
  }, [resumeTwinId, fetchTwin, router, returnTo]);

  // =============================================================================
  // Telemetry
  // =============================================================================

  const trackEvent = useCallback((event: string, properties?: Record<string, unknown>) => {
    // Send to analytics (e.g., PostHog, Mixpanel, etc.)
    if (typeof window !== 'undefined' && (window as { posthog?: { capture: (e: string, p?: Record<string, unknown>) => void } }).posthog) {
      (window as { posthog: { capture: (e: string, p?: Record<string, unknown>) => void } }).posthog.capture(event, properties);
    }
    console.log(`[Telemetry] ${event}`, properties);
  }, []);

  // =============================================================================
  // Mode Selection
  // =============================================================================

  const handleModeSelect = (selectedMode: 'manual' | 'link_first') => {
    setMode(selectedMode);
    trackEvent('link_first_onboarding_started', { mode: selectedMode });
    
    if (selectedMode === 'link_first') {
      setLinkFirstStep('link-submission');
      // Create draft twin immediately for link-first mode
      createDraftTwin();
    }
  };

  // =============================================================================
  // Create Draft Twin (Link-First Mode)
  // =============================================================================

  const createDraftTwin = async () => {
    setIsLaunching(true);
    
    try {
      const supabase = getSupabaseClient();
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData?.session?.access_token;

      // Generate a temporary name
      const tempName = `Draft Twin ${new Date().toLocaleDateString()}`;

      const response = await fetch('/api/twins', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          name: tempName,
          mode: 'link_first',
          specialization: 'vanilla',
        }),
      });

      if (!response.ok) {
        const error = await response.text();
        throw new Error(error || 'Failed to create twin');
      }

      const twinData = await response.json();
      setTwin(twinData);
      trackEvent('link_first_twin_created', { twin_id: twinData.id });
    } catch (error) {
      console.error('Failed to create draft twin:', error);
      alert(error instanceof Error ? error.message : 'Failed to create twin');
    } finally {
      setIsLaunching(false);
    }
  };

  // =============================================================================
  // Link-First Flow Handlers
  // =============================================================================

  const handleLinksSubmitted = (urls: string[], files: File[]) => {
    trackEvent('ingestion_started', { 
      twin_id: twin?.id, 
      url_count: urls.length, 
      file_count: files.length 
    });
    setLinkFirstStep('ingestion');
  };

  const handleIngestionComplete = () => {
    trackEvent('claims_ready', { twin_id: twin?.id });
    setLinkFirstStep('claims');
  };

  const handleClaimsApproved = () => {
    setLinkFirstStep('clarification');
  };

  const handleClarificationComplete = () => {
    trackEvent('clarification_completed', { twin_id: twin?.id });
    setLinkFirstStep('preview');
  };

  const handlePersonaActivated = () => {
    trackEvent('persona_activated', { twin_id: twin?.id });
    if (twin?.id) {
      router.push(returnTo || `/chat?twinId=${twin.id}`);
    }
  };

  // =============================================================================
  // Manual Flow: Validation
  // =============================================================================

  const isStepValid = () => {
    switch (currentStep) {
      case 1:
        return identityData.twinName.trim().length >= 2;
      case 2:
        return true;
      case 3:
        return valuesData.prioritizedValues.length > 0;
      case 4:
        return true;
      case 5:
        return true;
      case 6:
        return true;
      default:
        return false;
    }
  };

  const handleNext = () => {
    if (currentStep < 6 && isStepValid()) {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const handleEditStep = (step: number) => {
    setCurrentStep(step);
  };

  // =============================================================================
  // Manual Flow: Build Persona Data
  // =============================================================================

  const buildPersonaV2Data = () => {
    return {
      twin_name: identityData.twinName,
      tagline: identityData.tagline,
      specialization: specialization,
      role_definition: `${identityData.twinName} - ${identityData.tagline || 'Digital Twin'}`,
      selected_domains: identityData.expertise.filter((e) => !e.startsWith('custom:')),
      custom_expertise: identityData.expertise
        .filter((e) => e.startsWith('custom:'))
        .map((e) => e.replace('custom:', '')),
      background: '',
      goals_90_days: identityData.goals90Days.filter((g) => g.trim()),
      boundaries: identityData.boundaries ? [identityData.boundaries] : [],
      uncertainty_preference: identityData.uncertaintyPreference,
      decision_framework: thinkingData.decisionFramework,
      heuristics: thinkingData.heuristics.map((h) => ({
        id: h,
        name: h.replace(/_/g, ' '),
        description: '',
        applicable_types: ['evaluation'],
        priority: 50,
      })),
      clarifying_behavior: thinkingData.clarifyingBehavior,
      evidence_standards: thinkingData.evidenceStandards,
      prioritized_values: valuesData.prioritizedValues,
      tradeoff_preferences: valuesData.tradeoffNotes
        ? [
            {
              value_a: 'speed',
              value_b: 'quality',
              resolution: 'context_dependent',
              context_override: valuesData.tradeoffNotes,
            },
          ]
        : [],
      personality: {
        tone: personalityData.tone,
        response_length: personalityData.responseLength,
        first_person: personalityData.firstPerson,
        custom_instructions: personalityData.customInstructions,
      },
      signature_phrases: personalityData.signaturePhrases,
      key_experiences: memoryData.experiences.map((e) => ({
        content: e.content,
        context: e.context,
        applicable_intents: ['advice', 'evaluation'],
        weight: 0.8,
      })),
      lessons_learned: memoryData.lessons.map((l) => ({
        content: l.content,
        context: l.context,
        applicable_intents: ['advice'],
        weight: 0.9,
      })),
      recurring_patterns: memoryData.patterns.map((p) => ({
        content: p.content,
        context: p.context,
        applicable_intents: ['evaluation'],
        weight: 0.7,
      })),
    };
  };

  // =============================================================================
  // Manual Flow: Create Twin
  // =============================================================================

  const createTwin = async () => {
    setIsLaunching(true);

    try {
      const personaV2Data = buildPersonaV2Data();

      const expertiseText = identityData.expertise.join(', ');
      const legacySystemInstructions = `You are ${identityData.twinName}${
        identityData.tagline ? `, ${identityData.tagline}` : ''
      }.
Your areas of expertise include: ${expertiseText || 'general topics'}.
Communication style: ${personalityData.tone}, ${personalityData.responseLength} responses.
${personalityData.firstPerson ? 'Speak in first person ("I believe...")' : `Refer to yourself as ${identityData.twinName}`}
Top goals for next 90 days: ${identityData.goals90Days.filter((g) => g.trim()).join('; ') || 'Not set'}
Boundaries: ${identityData.boundaries || 'Not set'}
Privacy constraints: ${identityData.privacyConstraints || 'Not set'}
Uncertainty preference: ${
        identityData.uncertaintyPreference === 'ask'
          ? 'Ask clarifying questions when uncertain.'
          : 'Infer best effort and confirm quickly.'
      }
${personalityData.customInstructions ? `Additional instructions: ${personalityData.customInstructions}` : ''}`;

      const supabase = getSupabaseClient();
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData?.session?.access_token;

      const response = await fetch('/api/twins', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          name: identityData.twinName,
          description: identityData.tagline,
          specialization: specialization,
          mode: 'manual',
          settings: {
            system_prompt: legacySystemInstructions,
            handle: identityData.handle,
            tagline: identityData.tagline,
            expertise: identityData.expertise,
            personality: personalityData,
            intent_profile: {
              goals_90_days: identityData.goals90Days.filter((g) => g.trim()),
              boundaries: identityData.boundaries,
              privacy_constraints: identityData.privacyConstraints,
              uncertainty_preference: identityData.uncertaintyPreference,
            },
            use_5layer_persona: true,
            persona_v2_version: '2.0.0',
          },
          persona_v2_data: personaV2Data,
        }),
      });

      if (!response.ok) {
        const error = await response.text();
        throw new Error(error || 'Failed to create twin');
      }

      const twin = await response.json();

      // Redirect to the new twin or return to caller
      if (returnTo) {
        router.push(returnTo);
      } else if (twin.id) {
        router.push(`/chat?twinId=${twin.id}`);
      } else {
        router.push('/dashboard');
      }
    } catch (error) {
      console.error('Failed to create twin:', error);
      alert(error instanceof Error ? error.message : 'Failed to create twin');
    } finally {
      setIsLaunching(false);
    }
  };

  // =============================================================================
  // Render Link-First Flow
  // =============================================================================

  const renderLinkFirstFlow = () => {
    switch (linkFirstStep) {
      case 'mode-select':
        return <StepModeSelect onSelect={handleModeSelect} />;

      case 'link-submission':
        return (
          <StepLinkSubmission
            twinId={twin?.id || null}
            onSubmit={handleLinksSubmitted}
          />
        );

      case 'ingestion':
        return (
          <StepIngestionProgress
            twinId={twin?.id || null}
            onComplete={handleIngestionComplete}
          />
        );

      case 'claims':
        return (
          <StepClaimReview
            twinId={twin?.id || null}
            onApprove={handleClaimsApproved}
          />
        );

      case 'clarification':
        return (
          <StepClarification
            twinId={twin?.id || null}
            onComplete={handleClarificationComplete}
          />
        );

      case 'preview':
        return (
          <StepPersonaPreview
            twinId={twin?.id || null}
            onActivate={handlePersonaActivated}
          />
        );

      default:
        return null;
    }
  };

  // =============================================================================
  // Render Manual Flow Step
  // =============================================================================

  const renderManualStep = () => {
    switch (currentStep) {
      case 1:
        return (
          <Step1Identity
            data={identityData}
            onChange={setIdentityData}
            onSpecializationChange={setSpecialization}
          />
        );

      case 2:
        return <Step2ThinkingStyle data={thinkingData} onChange={setThinkingData} />;

      case 3:
        return (
          <Step3Values
            data={valuesData}
            onChange={setValuesData}
            specialization={specialization}
          />
        );

      case 4:
        return (
          <Step4Communication
            personality={personalityData}
            onPersonalityChange={setPersonalityData}
          />
        );

      case 5:
        return <Step5Memory data={memoryData} onChange={setMemoryData} />;

      case 6:
        return (
          <Step6Review
            data={{
              twinName: identityData.twinName,
              tagline: identityData.tagline,
              specialization: specialization,
              expertise: identityData.expertise,
              decisionFramework: thinkingData.decisionFramework,
              heuristics: thinkingData.heuristics,
              clarifyingBehavior: thinkingData.clarifyingBehavior,
              prioritizedValues: valuesData.prioritizedValues,
              personality: personalityData,
              memoryCount: memoryData.experiences.length + memoryData.lessons.length + memoryData.patterns.length,
            }}
            onTestChat={() => {
              alert('Test chat feature coming soon!');
            }}
            onEditStep={handleEditStep}
            onLaunch={createTwin}
            isLaunching={isLaunching}
          />
        );

      default:
        return null;
    }
  };

  // =============================================================================
  // Loading State
  // =============================================================================

  if (isLoadingTwin) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-white">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p>Resuming onboarding...</p>
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
              {mode === 'link_first' ? 'Link-First Persona Builder' : '5-Layer Persona System v2'}
            </p>
          </div>
          <div className="text-sm text-slate-400">
            {mode === 'link_first' ? (
              <span className="inline-flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                Draft Mode
              </span>
            ) : mode === 'manual' ? (
              `Step ${currentStep} of 6`
            ) : (
              'Select Mode'
            )}
          </div>
        </div>
      </header>

      {/* Progress (Manual Mode Only) */}
      {mode === 'manual' && (
        <div className="max-w-4xl mx-auto px-4 py-6">
          <StepIndicator 
            currentStep={currentStep} 
            totalSteps={6} 
            stepTitles={['Identity', 'Thinking Style', 'Values', 'Communication', 'Memory', 'Review']} 
          />
        </div>
      )}

      {/* Link-First Progress Indicator */}
      {mode === 'link_first' && (
        <div className="max-w-4xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            {[
              { key: 'link-submission', label: 'Submit' },
              { key: 'ingestion', label: 'Processing' },
              { key: 'claims', label: 'Review' },
              { key: 'clarification', label: 'Clarify' },
              { key: 'preview', label: 'Activate' },
            ].map((step, idx, arr) => {
              const isActive = linkFirstStep === step.key;
              const isPast = arr.findIndex(s => s.key === linkFirstStep) > idx;
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
      <main className="max-w-3xl mx-auto px-4 pb-32">
        {mode === null && LINK_FIRST_ENABLED ? (
          <StepModeSelect onSelect={handleModeSelect} />
        ) : mode === 'link_first' ? (
          renderLinkFirstFlow()
        ) : (
          <div key={currentStep}>
            {renderManualStep()}
          </div>
        )}
      </main>

      {/* Navigation Footer (Manual Mode Only) */}
      {mode === 'manual' && (
        <footer className="fixed bottom-0 left-0 right-0 border-t border-slate-800 bg-slate-900/95 backdrop-blur-sm">
          <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
            <button
              onClick={handleBack}
              disabled={currentStep === 1 || isLaunching}
              className="px-4 py-2 border border-slate-700 hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
            >
              ← Back
            </button>

            {currentStep < 6 && (
              <button
                onClick={handleNext}
                disabled={!isStepValid()}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
              >
                Next →
              </button>
            )}
          </div>
        </footer>
      )}
    </div>
  );
}

// Wrapper component with Suspense boundary for useSearchParams
export default function OnboardingPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-950 flex items-center justify-center text-white">Loading...</div>}>
      <OnboardingContent />
    </Suspense>
  );
}
