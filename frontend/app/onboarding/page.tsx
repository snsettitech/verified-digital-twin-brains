'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getSupabaseClient } from '@/lib/supabase/client';
import {
    Wizard,
    WelcomeStep,
    ChooseSpecializationStep,
    ClaimIdentityStep,
    DefineExpertiseStep,
    AddContentStep,
    SeedFAQsStep,
    SetPersonalityStep,
    PreviewTwinStep,
    LaunchStep
} from '@/components/onboarding';

// 9-Step Delphi-Style Onboarding with Specialization
const WIZARD_STEPS = [
    { id: 'welcome', title: 'Welcome', description: 'Get started', icon: '👋' },
    { id: 'specialization', title: 'Brain Type', description: 'Choose type', icon: '🧠' },
    { id: 'identity', title: 'Identity', description: 'Claim your name', icon: '✨' },
    { id: 'expertise', title: 'Expertise', description: 'Define domains', icon: '🎯' },
    { id: 'content', title: 'Content', description: 'Add knowledge', icon: '📚' },
    { id: 'faqs', title: 'FAQs', description: 'Seed answers', icon: '❓' },
    { id: 'personality', title: 'Personality', description: 'Set tone', icon: '🎭' },
    { id: 'preview', title: 'Preview', description: 'Test twin', icon: '👁️' },
    { id: 'launch', title: 'Launch', description: 'Go live', icon: '🚀' },
];

interface PersonalitySettings {
    tone: 'professional' | 'friendly' | 'casual' | 'technical';
    responseLength: 'concise' | 'balanced' | 'detailed';
    firstPerson: boolean;
    customInstructions: string;
}

interface FAQPair {
    question: string;
    answer: string;
}

export default function OnboardingPage() {
    const router = useRouter();
    const supabase = getSupabaseClient();

    // State
    const [currentStep, setCurrentStep] = useState(0);
    const [twinId, setTwinId] = useState<string | null>(null);

    // Step 1: Specialization
    const [selectedSpecialization, setSelectedSpecialization] = useState('vanilla');

    // Step 2: Identity
    const [twinName, setTwinName] = useState('');
    const [handle, setHandle] = useState('');
    const [tagline, setTagline] = useState('');

    // Step 3: Expertise
    const [selectedDomains, setSelectedDomains] = useState<string[]>([]);
    const [customExpertise, setCustomExpertise] = useState<string[]>([]);

    // Step 4: Content
    const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
    const [pendingUrls, setPendingUrls] = useState<string[]>([]);

    // Step 5: FAQs
    const [faqs, setFaqs] = useState<FAQPair[]>([]);

    // Step 6: Personality
    const [personality, setPersonality] = useState<PersonalitySettings>({
        tone: 'friendly',
        responseLength: 'balanced',
        firstPerson: true,
        customInstructions: ''
    });

    // Check if should skip onboarding (returning user with existing twins)
    useEffect(() => {
        const checkExistingTwins = async () => {
            const { data: twins } = await supabase
                .from('twins')
                .select('id')
                .limit(1);

            if (twins && twins.length > 0) {
                router.push('/dashboard');
            }
        };
        checkExistingTwins();
    }, []);

    const handleFileUpload = (files: File[]) => {
        setUploadedFiles(prev => [...prev, ...files]);
    };

    const handleUrlSubmit = (url: string) => {
        setPendingUrls(prev => [...prev, url]);
    };

    const handleStepChange = async (newStep: number) => {
        // Create twin after identity step (now step 2 -> 3)
        if (currentStep === 2 && newStep === 3 && twinName && !twinId) {
            await createTwin();
        }

        // Upload content after content step (now step 4 -> 5)
        if (currentStep === 4 && newStep === 5 && twinId) {
            await uploadContent();
        }

        // Save FAQs after FAQ step (now step 5 -> 6)
        if (currentStep === 5 && newStep === 6 && twinId) {
            await saveFaqs();
        }

        // Save personality after personality step (now step 6 -> 7)
        if (currentStep === 6 && newStep === 7 && twinId) {
            await savePersonality();
        }

        setCurrentStep(newStep);
    };

    const createTwin = async () => {
        try {
            const { data: { user } } = await supabase.auth.getUser();
            if (!user) return;

            const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
            const expertiseText = [...selectedDomains, ...customExpertise].join(', ');

            const systemInstructions = `You are ${twinName}${tagline ? `, ${tagline}` : ''}.
Your areas of expertise include: ${expertiseText || 'general topics'}.
Communication style: ${personality.tone}, ${personality.responseLength} responses.
${personality.firstPerson ? 'Speak in first person ("I believe...")' : `Refer to yourself as ${twinName}`}
${personality.customInstructions ? `Additional instructions: ${personality.customInstructions}` : ''}`;

            // Debug: Log what we're saving
            console.log('Creating twin with specialization:', selectedSpecialization);

            // Call backend API to create twin (bypasses RLS)
            const response = await fetch(`${backendUrl}/twins`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: twinName,
                    tenant_id: user.id,
                    description: tagline || `${twinName}'s digital twin`,
                    specialization: selectedSpecialization,
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
                console.log('Twin created:', data);
                setTwinId(data.id);
            } else {
                const error = await response.json();
                console.error('Error creating twin:', error);
            }
        } catch (error) {
            console.error('Error creating twin:', error);
        }
    };

    const uploadContent = async () => {
        if (!twinId) return;

        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

        // Upload files
        for (const file of uploadedFiles) {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('twin_id', twinId);

            try {
                await fetch(`${backendUrl}/ingest/document`, {
                    method: 'POST',
                    body: formData,
                });
            } catch (error) {
                console.error('Error uploading file:', error);
            }
        }

        // Submit URLs
        for (const url of pendingUrls) {
            try {
                await fetch(`${backendUrl}/ingest/url`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url, twin_id: twinId }),
                });
            } catch (error) {
                console.error('Error submitting URL:', error);
            }
        }
    };

    const saveFaqs = async () => {
        if (!twinId) return;

        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
        const { data: { user } } = await supabase.auth.getUser();

        for (const faq of faqs) {
            if (faq.question && faq.answer) {
                try {
                    await fetch(`${backendUrl}/twins/${twinId}/verified-qna`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
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

    const savePersonality = async () => {
        if (!twinId) return;

        const expertiseText = [...selectedDomains, ...customExpertise].join(', ');
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

        const systemInstructions = `You are ${twinName}${tagline ? `, ${tagline}` : ''}.
Your areas of expertise include: ${expertiseText || 'general topics'}.
Communication style: ${personality.tone}, ${personality.responseLength} responses.
${personality.firstPerson ? 'Speak in first person ("I believe...")' : `Refer to yourself as ${twinName}`}
${personality.customInstructions ? `Additional instructions: ${personality.customInstructions}` : ''}`;

        try {
            // Use backend PATCH endpoint
            await fetch(`${backendUrl}/twins/${twinId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    description: tagline || `${twinName}'s digital twin`,
                    settings: {
                        system_prompt: systemInstructions,
                        handle,
                        tagline,
                        expertise: [...selectedDomains, ...customExpertise],
                        personality
                    }
                })
            });
        } catch (error) {
            console.error('Error saving personality:', error);
        }
    };

    const handleLaunch = async () => {
        if (!twinId) return;

        // Save the active twin ID and onboarding completed flag
        localStorage.setItem('activeTwinId', twinId);
        localStorage.setItem('onboardingCompleted', 'true');
    };

    const handleComplete = () => {
        if (twinId) {
            router.push(`/dashboard`);
        } else {
            router.push('/dashboard');
        }
    };

    const renderStep = () => {
        switch (currentStep) {
            case 0:
                return <WelcomeStep />;
            case 1:
                return (
                    <ChooseSpecializationStep
                        selectedSpecialization={selectedSpecialization}
                        onSpecializationChange={setSelectedSpecialization}
                    />
                );
            case 2:
                return (
                    <ClaimIdentityStep
                        twinName={twinName}
                        handle={handle}
                        tagline={tagline}
                        onTwinNameChange={setTwinName}
                        onHandleChange={setHandle}
                        onTaglineChange={setTagline}
                    />
                );
            case 3:
                return (
                    <DefineExpertiseStep
                        selectedDomains={selectedDomains}
                        customExpertise={customExpertise}
                        onDomainsChange={setSelectedDomains}
                        onCustomExpertiseChange={setCustomExpertise}
                    />
                );
            case 4:
                return (
                    <AddContentStep
                        onFileUpload={handleFileUpload}
                        onUrlSubmit={handleUrlSubmit}
                        uploadedFiles={uploadedFiles}
                        pendingUrls={pendingUrls}
                    />
                );
            case 5:
                return (
                    <SeedFAQsStep
                        faqs={faqs}
                        onFaqsChange={setFaqs}
                        expertiseDomains={selectedDomains}
                    />
                );
            case 6:
                return (
                    <SetPersonalityStep
                        personality={personality}
                        onPersonalityChange={setPersonality}
                        twinName={twinName || 'Your Twin'}
                    />
                );
            case 7:
                return (
                    <PreviewTwinStep
                        twinId={twinId}
                        twinName={twinName || 'Your Twin'}
                        tagline={tagline}
                    />
                );
            case 8:
                return (
                    <LaunchStep
                        twinName={twinName || 'Your Twin'}
                        handle={handle}
                        twinId={twinId}
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
            onComplete={handleComplete}
            allowSkip={currentStep === 4 || currentStep === 5} // Allow skip on content and FAQ steps
        >
            {renderStep()}
        </Wizard>
    );
}
