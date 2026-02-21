'use client';

import React, { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import { StepIndicator } from '@/components/onboarding/StepIndicator';
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

// =============================================================================
// Step Configuration
// =============================================================================

const TOTAL_STEPS = 6;

const STEP_TITLES = [
  'Identity',
  'Thinking Style',
  'Values',
  'Communication',
  'Memory',
  'Review',
];

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

  const [currentStep, setCurrentStep] = useState(1);
  const [isLaunching, setIsLaunching] = useState(false);

  // Form data state
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

  // Specialization (passed between steps)
  const [specialization, setSpecialization] = useState('vanilla');

  // =============================================================================
  // Validation
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

  // =============================================================================
  // Navigation
  // =============================================================================

  const handleNext = () => {
    if (currentStep < TOTAL_STEPS && isStepValid()) {
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
  // Launch (Create Twin)
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
        router.push(`/twins/${twin.id}`);
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
  // Render Step Content
  // =============================================================================

  const renderStep = () => {
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
              5-Layer Persona System v2
            </p>
          </div>
          <div className="text-sm text-slate-400">
            Step {currentStep} of {TOTAL_STEPS}
          </div>
        </div>
      </header>

      {/* Progress */}
      <div className="max-w-4xl mx-auto px-4 py-6">
        <StepIndicator currentStep={currentStep} totalSteps={TOTAL_STEPS} stepTitles={STEP_TITLES} />
      </div>

      {/* Main Content */}
      <main className="max-w-3xl mx-auto px-4 pb-32">
        <div key={currentStep}>
          {renderStep()}
        </div>
      </main>

      {/* Navigation Footer */}
      <footer className="fixed bottom-0 left-0 right-0 border-t border-slate-800 bg-slate-900/95 backdrop-blur-sm">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
          <button
            onClick={handleBack}
            disabled={currentStep === 1 || isLaunching}
            className="px-4 py-2 border border-slate-700 hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
          >
            ← Back
          </button>

          {currentStep < TOTAL_STEPS && (
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
