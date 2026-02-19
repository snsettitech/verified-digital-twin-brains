'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { getSupabaseClient } from '@/lib/supabase/client';
import { Wizard } from '@/components/onboarding';
import Step1Identity from '@/components/onboarding/steps/Step1Identity';
import Step2Knowledge from '@/components/onboarding/steps/Step2Knowledge';
import Step3Launch from '@/components/onboarding/steps/Step3Launch';
import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';
import { resolveApiBaseUrl } from '@/lib/api';
import { ingestUrlWithFallback, uploadFileWithFallback } from '@/lib/ingestionApi';

// 3-Step Streamlined Onboarding
const WIZARD_STEPS = [
  { id: 'identity', title: 'Identity', description: 'Set up your twin', icon: '✨' },
  { id: 'knowledge', title: 'Knowledge', description: 'Add content', icon: '📚' },
  { id: 'launch', title: 'Launch', description: 'Go live', icon: '🚀' },
];

interface FAQPair {
  question: string;
  answer: string;
}

const getOnboardingTwinStorageKey = (userId: string) => `onboardingTwinId:${userId}`;

export default function OnboardingPage() {
  const router = useRouter();
  const supabase = getSupabaseClient();
  const [forceNewTwin, setForceNewTwin] = useState(false);
  const [forceNewReady, setForceNewReady] = useState(false);

  // State
  const [currentStep, setCurrentStep] = useState(0);
  const [twinId, setTwinId] = useState<string | null>(null);
  const [creatingTwinRef] = useState({ current: false });
  const [isLaunching, setIsLaunching] = useState(false);

  // Step 1: Identity State
  const [twinName, setTwinName] = useState('');
  const [handle, setHandle] = useState('');
  const [tagline, setTagline] = useState('');
  const [specialization, setSpecialization] = useState('vanilla');
  const [selectedDomains, setSelectedDomains] = useState<string[]>([]);
  const [customExpertise, setCustomExpertise] = useState<string[]>([]);
  const [personality, setPersonality] = useState({
    tone: 'friendly' as const,
    responseLength: 'balanced' as const,
    firstPerson: true,
    customInstructions: '',
  });

  // Step 2: Knowledge State
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [pendingUrls, setPendingUrls] = useState<string[]>([]);
  const [faqs, setFaqs] = useState<FAQPair[]>([]);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const fromQuery = new URLSearchParams(window.location.search).get('new') === '1';
    const fromStorage = localStorage.getItem('forceCreateTwin') === '1';
    const forceCreate = fromQuery || fromStorage;

    // One-shot flag from TwinSelector.
    if (fromStorage) {
      localStorage.removeItem('forceCreateTwin');
    }

    setForceNewTwin(forceCreate);
    setForceNewReady(true);
  }, []);

  // Check if should skip onboarding (returning user with existing twins)
  useEffect(() => {
    if (!forceNewReady) {
      return;
    }

    const checkExistingTwins = async () => {
      if (forceNewTwin) {
        return;
      }
      try {
        await authFetchStandalone('/auth/sync-user', { method: 'POST' });
        const response = await authFetchStandalone('/auth/my-twins');
        if (response.ok) {
          const twins = await response.json();
          if (twins && twins.length > 0) {
            router.push('/dashboard');
          }
        }
      } catch (error) {
        console.error('[Onboarding] Error checking twins:', error);
      }
    };
    checkExistingTwins();
  }, [router, forceNewTwin, forceNewReady]);

  const handleStepChange = async (newStep: number) => {
    // Moving from Step 1 to Step 2: Create twin
    if (currentStep === 0 && newStep === 1 && twinName && !twinId) {
      await createTwin();
    }
    
    // Moving from Step 2 to Step 3: Upload content and save FAQs
    if (currentStep === 1 && newStep === 2 && twinId) {
      await uploadContentAndFaqs();
    }

    setCurrentStep(newStep);
  };

  const createTwin = async () => {
    if (creatingTwinRef.current || twinId) return;
    creatingTwinRef.current = true;

    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      await authFetchStandalone('/auth/sync-user', { method: 'POST' });

      // Check for existing twin
      if (!forceNewTwin) {
        const existingRes = await authFetchStandalone('/auth/my-twins');
        if (existingRes.ok) {
          const existingTwins = await existingRes.json();
          if (Array.isArray(existingTwins) && existingTwins.length > 0) {
            const existingTwinId = existingTwins[0]?.id;
            if (existingTwinId) {
              setTwinId(existingTwinId);
              localStorage.setItem(getOnboardingTwinStorageKey(user.id), existingTwinId);
              return;
            }
          }
        }
      }

      const expertiseText = [...selectedDomains, ...customExpertise].join(', ');
      const systemInstructions = `You are ${twinName}${tagline ? `, ${tagline}` : ''}.
Your areas of expertise include: ${expertiseText || 'general topics'}.
Communication style: ${personality.tone}, ${personality.responseLength} responses.
${personality.firstPerson ? 'Speak in first person ("I believe...")' : `Refer to yourself as ${twinName}`}
${personality.customInstructions ? `Additional instructions: ${personality.customInstructions}` : ''}`;

      const response = await authFetchStandalone('/twins', {
        method: 'POST',
        body: JSON.stringify({
          name: twinName,
          description: tagline || `${twinName}'s digital twin`,
          specialization,
          settings: {
            system_prompt: systemInstructions,
            handle,
            tagline,
            expertise: [...selectedDomains, ...customExpertise],
            personality
          }
        })
      });

      if (response.ok) {
        const data = await response.json();
        setTwinId(data.id);
        localStorage.setItem(getOnboardingTwinStorageKey(user.id), data.id);
      } else {
        const error = await response.json();
        console.error('Error creating twin:', error);
      }
    } catch (error) {
      console.error('Error creating twin:', error);
    } finally {
      creatingTwinRef.current = false;
    }
  };

  const uploadContentAndFaqs = async () => {
    if (!twinId) return;
    const backendUrl = resolveApiBaseUrl();
    const { data: { session } } = await supabase.auth.getSession();
    const headers: Record<string, string> = {};
    if (session?.access_token) {
      headers['Authorization'] = `Bearer ${session.access_token}`;
    }

    // Upload files
    for (const file of uploadedFiles) {
      try {
        await uploadFileWithFallback({ backendUrl, twinId, file, headers });
      } catch (error) {
        console.error('Error uploading file:', error);
      }
    }

    // Submit URLs
    for (const url of pendingUrls) {
      try {
        await ingestUrlWithFallback({ backendUrl, twinId, url, headers });
      } catch (error) {
        console.error('Error submitting URL:', error);
      }
    }

    // Save FAQs
    const { data: { user } } = await supabase.auth.getUser();
    for (const faq of faqs) {
      if (faq.question && faq.answer) {
        try {
          await authFetchStandalone(`/twins/${twinId}/verified-qna`, {
            method: 'POST',
            body: JSON.stringify({
              question: faq.question,
              answer: faq.answer,
              owner_id: user?.id
            }),
          });
        } catch (error) {
          console.error('Error saving FAQ:', error);
        }
      }
    }
  };

  const handleLaunch = async () => {
    if (!twinId) return;
    setIsLaunching(true);

    try {
      // Final personality update
      const expertiseText = [...selectedDomains, ...customExpertise].join(', ');
      const systemInstructions = `You are ${twinName}${tagline ? `, ${tagline}` : ''}.
Your areas of expertise include: ${expertiseText || 'general topics'}.
Communication style: ${personality.tone}, ${personality.responseLength} responses.
${personality.firstPerson ? 'Speak in first person ("I believe...")' : `Refer to yourself as ${twinName}`}
${personality.customInstructions ? `Additional instructions: ${personality.customInstructions}` : ''}`;

      await authFetchStandalone(`/twins/${twinId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          description: tagline || `${twinName}'s digital twin`,
          settings: {
            system_prompt: systemInstructions,
            handle,
            tagline,
            expertise: [...selectedDomains, ...customExpertise],
            personality,
            widget_settings: {
              public_share_enabled: true,
              share_token: Math.random().toString(36).substring(2, 15),
            }
          }
        })
      });

      // Enable public sharing
      localStorage.setItem('activeTwinId', twinId);
      localStorage.setItem('onboardingCompleted', 'true');
      
      // Clear onboarding twin key
      const { data: { user } } = await supabase.auth.getUser();
      if (user?.id) {
        localStorage.removeItem(getOnboardingTwinStorageKey(user.id));
      }
      
      router.push('/dashboard');
    } catch (error) {
      console.error('Error launching twin:', error);
    } finally {
      setIsLaunching(false);
    }
  };

  const renderStep = () => {
    switch (currentStep) {
      case 0:
        return (
          <Step1Identity
            twinName={twinName}
            handle={handle}
            tagline={tagline}
            specialization={specialization}
            selectedDomains={selectedDomains}
            customExpertise={customExpertise}
            personality={personality}
            onTwinNameChange={setTwinName}
            onHandleChange={setHandle}
            onTaglineChange={setTagline}
            onSpecializationChange={setSpecialization}
            onDomainsChange={setSelectedDomains}
            onCustomExpertiseChange={setCustomExpertise}
            onPersonalityChange={setPersonality}
          />
        );
      case 1:
        return (
          <Step2Knowledge
            uploadedFiles={uploadedFiles}
            pendingUrls={pendingUrls}
            faqs={faqs}
            onFileUpload={(files) => setUploadedFiles(prev => [...prev, ...files])}
            onUrlSubmit={(url) => setPendingUrls(prev => [...prev, url])}
            onFaqsChange={setFaqs}
            onRemoveFile={(index) => setUploadedFiles(prev => prev.filter((_, i) => i !== index))}
            onRemoveUrl={(index) => setPendingUrls(prev => prev.filter((_, i) => i !== index))}
          />
        );
      case 2:
        return (
          <Step3Launch
            twinId={twinId}
            twinName={twinName}
            handle={handle}
            tagline={tagline}
            specialization={specialization}
            isLaunching={isLaunching}
            onLaunch={handleLaunch}
          />
        );
      default:
        return null;
    }
  };

  return (
    <Wizard
      steps={WIZARD_STEPS}
      currentStep={currentStep}
      onStepChange={handleStepChange}
      onComplete={handleLaunch}
      allowSkip={currentStep === 1} // Allow skip on knowledge step
    >
      {renderStep()}
    </Wizard>
  );
}
