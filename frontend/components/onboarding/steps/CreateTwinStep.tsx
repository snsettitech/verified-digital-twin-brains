'use client';

import React, { useState } from 'react';
import { WizardStep } from '../Wizard';

interface CreateTwinStepProps {
    twinName: string;
    twinPurpose: string;
    onTwinNameChange: (name: string) => void;
    onTwinPurposeChange: (purpose: string) => void;
}

const PURPOSE_OPTIONS = [
    {
        id: 'coach',
        title: 'Coaching & Mentoring',
        description: 'Help people learn from your expertise',
        icon: '🎯'
    },
    {
        id: 'creator',
        title: 'Content Creator',
        description: 'Let fans interact with your content',
        icon: '🎬'
    },
    {
        id: 'expert',
        title: 'Subject Expert',
        description: 'Share specialized knowledge',
        icon: '🧠'
    },
    {
        id: 'business',
        title: 'Business Owner',
        description: 'Represent your brand and services',
        icon: '💼'
    },
    {
        id: 'other',
        title: 'Something Else',
        description: 'Custom use case',
        icon: '✨'
    }
];

export function CreateTwinStep({
    twinName,
    twinPurpose,
    onTwinNameChange,
    onTwinPurposeChange
}: CreateTwinStepProps) {
    return (
        <WizardStep
            title="Create Your Twin"
            description="Give your digital twin a name and purpose"
        >
            <div className="max-w-xl mx-auto space-y-8">
                {/* Name Input */}
                <div>
                    <label className="block text-sm font-medium text-slate-300 mb-3">
                        What should we call your twin?
                    </label>
                    <input
                        type="text"
                        value={twinName}
                        onChange={(e) => onTwinNameChange(e.target.value)}
                        placeholder="e.g., Sarah's AI, TechGuru, My Expert Twin"
                        className="w-full px-5 py-4 bg-white/5 border border-white/10 rounded-xl text-white text-lg placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                    />
                    <p className="mt-2 text-sm text-slate-500">
                        This is how your twin will be presented to others
                    </p>
                </div>

                {/* Purpose Selection */}
                <div>
                    <label className="block text-sm font-medium text-slate-300 mb-3">
                        What will your twin help with?
                    </label>
                    <div className="grid grid-cols-2 gap-3">
                        {PURPOSE_OPTIONS.map((option) => (
                            <button
                                key={option.id}
                                onClick={() => onTwinPurposeChange(option.id)}
                                className={`
                  p-4 rounded-xl text-left transition-all duration-200
                  ${twinPurpose === option.id
                                        ? 'bg-gradient-to-r from-indigo-500/20 to-purple-500/20 border-2 border-indigo-500'
                                        : 'bg-white/5 border border-white/10 hover:bg-white/10'}
                `}
                            >
                                <div className="flex items-start gap-3">
                                    <span className="text-2xl">{option.icon}</span>
                                    <div>
                                        <div className="font-semibold text-white text-sm">{option.title}</div>
                                        <div className="text-slate-400 text-xs mt-0.5">{option.description}</div>
                                    </div>
                                </div>
                            </button>
                        ))}
                    </div>
                </div>

                {/* Preview Card */}
                {twinName && (
                    <div className="p-6 bg-gradient-to-r from-indigo-500/10 to-purple-500/10 border border-indigo-500/20 rounded-2xl">
                        <div className="flex items-center gap-4">
                            <div className="w-14 h-14 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center text-white text-xl font-bold">
                                {twinName.charAt(0).toUpperCase()}
                            </div>
                            <div>
                                <div className="text-white font-semibold text-lg">{twinName}</div>
                                <div className="text-slate-400 text-sm">
                                    {PURPOSE_OPTIONS.find(o => o.id === twinPurpose)?.title || 'Your Digital Twin'}
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </WizardStep>
    );
}

export default CreateTwinStep;
