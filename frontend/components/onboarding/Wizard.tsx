'use client';

import React, { useState, useEffect } from 'react';

interface WizardStep {
    id: string;
    title: string;
    description: string;
    icon: React.ReactNode;
}

interface WizardProps {
    steps: WizardStep[];
    currentStep: number;
    onStepChange: (step: number) => void;
    children: React.ReactNode;
    onComplete?: () => void;
    allowSkip?: boolean;
}

export function ProgressSteps({
    steps,
    currentStep
}: {
    steps: WizardStep[];
    currentStep: number;
}) {
    return (
        <div className="flex items-center justify-between mb-8">
            {steps.map((step, index) => {
                const isComplete = index < currentStep;
                const isCurrent = index === currentStep;
                const isPending = index > currentStep;

                return (
                    <React.Fragment key={step.id}>
                        {/* Step Circle */}
                        <div className="flex flex-col items-center">
                            <div
                                className={`
                  w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300
                  ${isComplete ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white' : ''}
                  ${isCurrent ? 'bg-gradient-to-r from-indigo-500 to-purple-500 text-white ring-4 ring-indigo-500/30' : ''}
                  ${isPending ? 'bg-white/10 text-slate-500 border border-white/10' : ''}
                `}
                            >
                                {isComplete ? (
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                    </svg>
                                ) : (
                                    index + 1
                                )}
                            </div>
                            <span className={`mt-2 text-xs font-medium ${isCurrent ? 'text-white' : 'text-slate-500'}`}>
                                {step.title}
                            </span>
                        </div>

                        {/* Connector Line */}
                        {index < steps.length - 1 && (
                            <div
                                className={`
                  flex-1 h-0.5 mx-2 rounded-full transition-all duration-500
                  ${index < currentStep ? 'bg-gradient-to-r from-emerald-500 to-teal-500' : 'bg-white/10'}
                `}
                            />
                        )}
                    </React.Fragment>
                );
            })}
        </div>
    );
}

export function Wizard({
    steps,
    currentStep,
    onStepChange,
    children,
    onComplete,
    allowSkip = false
}: WizardProps) {
    const isFirstStep = currentStep === 0;
    const isLastStep = currentStep === steps.length - 1;

    const handleNext = () => {
        if (isLastStep) {
            onComplete?.();
        } else {
            onStepChange(currentStep + 1);
        }
    };

    const handleBack = () => {
        if (!isFirstStep) {
            onStepChange(currentStep - 1);
        }
    };

    const handleSkip = () => {
        if (!isLastStep) {
            onStepChange(currentStep + 1);
        }
    };

    return (
        <div className="min-h-screen bg-[#0a0a0f] flex flex-col">
            {/* Background Effects */}
            <div className="fixed inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-indigo-600/10 rounded-full blur-3xl" />
                <div className="absolute bottom-0 right-1/4 w-[600px] h-[600px] bg-purple-600/10 rounded-full blur-3xl" />
            </div>

            {/* Content */}
            <div className="relative z-10 flex-1 flex flex-col max-w-3xl mx-auto w-full px-6 py-12">
                {/* Progress */}
                <ProgressSteps steps={steps} currentStep={currentStep} />

                {/* Step Content */}
                <div className="flex-1 flex flex-col">
                    {children}
                </div>

                {/* Navigation */}
                <div className="flex items-center justify-between pt-8 border-t border-white/10">
                    <button
                        onClick={handleBack}
                        disabled={isFirstStep}
                        className={`
              flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all
              ${isFirstStep
                                ? 'text-slate-600 cursor-not-allowed'
                                : 'text-slate-400 hover:text-white hover:bg-white/5'}
            `}
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
                        </svg>
                        Back
                    </button>

                    <div className="flex items-center gap-3">
                        {allowSkip && !isLastStep && (
                            <button
                                onClick={handleSkip}
                                className="px-4 py-2 text-sm font-medium text-slate-400 hover:text-white transition-colors"
                            >
                                Skip for now
                            </button>
                        )}

                        <button
                            onClick={handleNext}
                            className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold rounded-xl shadow-lg shadow-indigo-500/25 transition-all"
                        >
                            {isLastStep ? 'Get Started' : 'Continue'}
                            {!isLastStep && (
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                                </svg>
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

export function WizardStep({
    children,
    title,
    description
}: {
    children: React.ReactNode;
    title?: string;
    description?: string;
}) {
    return (
        <div className="flex-1 flex flex-col animate-fadeIn">
            {(title || description) && (
                <div className="text-center mb-8">
                    {title && (
                        <h1 className="text-3xl font-bold text-white mb-2">{title}</h1>
                    )}
                    {description && (
                        <p className="text-slate-400 text-lg">{description}</p>
                    )}
                </div>
            )}
            <div className="flex-1">
                {children}
            </div>
        </div>
    );
}

// Add to globals.css
const styles = `
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-fadeIn {
  animation: fadeIn 0.4s ease-out;
}
`;

export default Wizard;
