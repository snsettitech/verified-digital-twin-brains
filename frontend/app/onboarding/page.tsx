'use client';

import React, { useState, Suspense, useEffect, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import { StepWelcome } from '@/components/onboarding/steps/StepWelcome';
import { StepLinkSuggestions } from '@/components/onboarding/steps/StepLinkSuggestions';
import { StepAddSources } from '@/components/onboarding/steps/StepAddSources';
import { StepBuilding } from '@/components/onboarding/steps/StepBuilding';
import { StepProfileLanding } from '@/components/onboarding/steps/StepProfileLanding';
import { StepClaimReview } from '@/components/onboarding/steps/StepClaimReview';
import { StepClarification } from '@/components/onboarding/steps/StepClarification';
import { Step1Identity, IdentityFormData } from '@/components/onboarding/steps/Step1Identity';
import { Step2ThinkingStyle } from '@/components/onboarding/steps/Step2ThinkingStyle';
import { Step3Values } from '@/components/onboarding/steps/Step3Values';
import { Step4Communication } from '@/components/onboarding/steps/Step4Communication';
import { Step5Memory } from '@/components/onboarding/steps/Step5Memory';
import { Step6Review } from '@/components/onboarding/steps/Step6Review';
import { getSupabaseClient } from '@/lib/supabase/client';

// =============================================================================
// Types
// =============================================================================

type FlowType = 'link_first' | 'manual' | null;
type OnboardingStep = 
  | 'welcome'
  | 'link_suggestions'
  | 'add_sources'
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

interface WelcomeData {
  fullName: string;
  location?: string;
  role?: string;
  consent: boolean;
  manualMode?: boolean;
}

// =============================================================================
// Component
// =============================================================================

function OnboardingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnTo = searchParams.get('returnTo');
  const resumeTwinId = searchParams.get('twinId');

  // Flow state
  const [flowType, setFlowType] = useState<FlowType>(null);
  const [currentStep, setCurrentStep] = useState<OnboardingStep>('welcome');
  
  // Data state
  const [welcomeData, setWelcomeData] = useState<WelcomeData | null>(null);
  const [suggestedUrls, setSuggestedUrls] = useState<string[]>([]);
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

  // =============================================================================
  // Telemetry
  // =============================================================================

  const trackEvent = useCallback((event: string, properties?: Record<string, unknown>) => {
    if (typeof window !== 'undefined' && (window as unknown as { posthog?: { capture: (e: string, p?: Record<string, unknown>) => void } }).posthog) {
      (window as unknown as { posthog: { capture: (e: string, p?: Record<string, unknown>) => void } }).posthog.capture(event, properties);
    }
    console.log(`[Telemetry] ${event}`, properties);
  }, []);

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
    const supabase = getSupabaseClient();
    const { data: sessionData } = await supabase.auth.getSession();
    const token = sessionData?.session?.access_token;

    const response = await fetch(`/api/twins/${twinId}`, {
      headers: token ? { 'Authorization': `Bearer ${token}` } : {},
    });

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
      const twinData = await createDraftTwin(data.fullName);
      if (twinData) {
        setTwin(twinData);
        setFlowType('link_first');
        setCurrentStep('link_suggestions');
      }
      setIsLoading(false);
    }
  };

  const createDraftTwin = async (name: string): Promise<Twin | null> => {
    try {
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
          name: `${name} (Draft)`,
          mode: 'link_first',
          specialization: 'vanilla',
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
      const supabase = getSupabaseClient();
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData?.session?.access_token;

      // Handle files (Mode A)
      const files = sources.filter(s => s.type === 'export' && s.file).map(s => s.file!);
      if (files.length > 0) {
        const formData = new FormData();
        formData.append('twin_id', twin.id);
        files.forEach(f => formData.append('files', f));
        
        await fetch('/api/persona/link-compile/jobs/mode-a', {
          method: 'POST',
          headers: token ? { 'Authorization': `Bearer ${token}` } : {},
          body: formData,
        });
      }

      // Handle paste (Mode B)
      const pasteSources = sources.filter(s => s.type === 'paste');
      for (const paste of pasteSources) {
        await fetch('/api/persona/link-compile/jobs/mode-b', {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
          },
          body: JSON.stringify({
            twin_id: twin.id,
            content: paste.value,
            title: paste.category || 'Pasted Content',
          }),
        });
      }

      // Handle URLs (Mode C)
      const urls = sources.filter(s => s.type === 'link').map(s => s.value);
      const allUrls = [...suggestedUrls, ...urls];
      if (allUrls.length > 0) {
        await fetch('/api/persona/link-compile/jobs/mode-c', {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
          },
          body: JSON.stringify({
            twin_id: twin.id,
            urls: allUrls,
          }),
        });
      }

      setCurrentStep('building');
    } catch (error) {
      console.error('Failed to submit sources:', error);
      alert('Failed to submit sources. Please try again.');
    } finally {
      setIsLoading(false);
    }
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
      router.push(returnTo || `/chat?twinId=${twin.id}`);
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
          mode: 'manual',
          specialization,
          persona_v2_data: { /* ... */ },
        }),
      });

      if (!response.ok) throw new Error('Failed to create twin');
      
      const newTwin = await response.json();
      router.push(returnTo || `/chat?twinId=${newTwin.id}`);
    } catch (error) {
      console.error('Failed to create manual twin:', error);
      alert('Failed to create twin. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

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
          <Step1Identity
            data={identityData}
            onChange={setIdentityData}
            onSpecializationChange={setSpecialization}
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
              { key: 'building', label: 'Build' },
              { key: 'profile', label: 'Review' },
            ].map((step, idx, arr) => {
              const isActive = currentStep === step.key;
              const isPast = ['link_suggestions', 'add_sources', 'building', 'profile'].indexOf(currentStep) > 
                            ['link_suggestions', 'add_sources', 'building', 'profile'].indexOf(step.key);
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
