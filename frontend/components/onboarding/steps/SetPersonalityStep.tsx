'use client';

import React from 'react';
import { WizardStep } from '../Wizard';

interface PersonalitySettings {
    tone: 'professional' | 'friendly' | 'casual' | 'technical';
    responseLength: 'concise' | 'balanced' | 'detailed';
    firstPerson: boolean;
    customInstructions: string;
}

interface SetPersonalityStepProps {
    personality: PersonalitySettings;
    onPersonalityChange: (personality: PersonalitySettings) => void;
    twinName: string;
}

const TONE_OPTIONS = [
    { id: 'professional', label: 'Professional', description: 'Formal and business-like', icon: '👔' },
    { id: 'friendly', label: 'Friendly', description: 'Warm and approachable', icon: '😊' },
    { id: 'casual', label: 'Casual', description: 'Relaxed and conversational', icon: '💬' },
    { id: 'technical', label: 'Technical', description: 'Precise and detailed', icon: '🔬' },
];

const LENGTH_OPTIONS = [
    { id: 'concise', label: 'Concise', description: 'Short, to-the-point responses' },
    { id: 'balanced', label: 'Balanced', description: 'Moderate detail level' },
    { id: 'detailed', label: 'Detailed', description: 'Comprehensive explanations' },
];

export function SetPersonalityStep({
    personality,
    onPersonalityChange,
    twinName
}: SetPersonalityStepProps) {
    const updatePersonality = (key: keyof PersonalitySettings, value: any) => {
        onPersonalityChange({ ...personality, [key]: value });
    };

    return (
        <WizardStep
            title="Set Your Twin's Personality"
            description="Define how your digital twin communicates"
        >
            <div className="max-w-2xl mx-auto space-y-8">
                {/* Tone Selection */}
                <div className="space-y-4">
                    <label className="block text-sm font-semibold text-slate-300">
                        Communication Tone
                    </label>
                    <div className="grid grid-cols-2 gap-3">
                        {TONE_OPTIONS.map((option) => (
                            <button
                                key={option.id}
                                onClick={() => updatePersonality('tone', option.id)}
                                className={`
                                    p-4 rounded-xl text-left transition-all duration-200
                                    ${personality.tone === option.id
                                        ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-500/25'
                                        : 'bg-white/5 border border-white/10 text-slate-300 hover:bg-white/10'
                                    }
                                `}
                            >
                                <div className="flex items-center gap-3">
                                    <span className="text-2xl">{option.icon}</span>
                                    <div>
                                        <p className="font-semibold">{option.label}</p>
                                        <p className={`text-xs ${personality.tone === option.id ? 'text-indigo-200' : 'text-slate-500'}`}>
                                            {option.description}
                                        </p>
                                    </div>
                                </div>
                            </button>
                        ))}
                    </div>
                </div>

                {/* Response Length */}
                <div className="space-y-4">
                    <label className="block text-sm font-semibold text-slate-300">
                        Response Length
                    </label>
                    <div className="flex rounded-xl overflow-hidden border border-white/10">
                        {LENGTH_OPTIONS.map((option) => (
                            <button
                                key={option.id}
                                onClick={() => updatePersonality('responseLength', option.id)}
                                className={`
                                    flex-1 px-4 py-3 text-sm font-medium transition-all
                                    ${personality.responseLength === option.id
                                        ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white'
                                        : 'bg-white/5 text-slate-400 hover:bg-white/10'
                                    }
                                `}
                            >
                                {option.label}
                            </button>
                        ))}
                    </div>
                </div>

                {/* First Person Toggle */}
                <div className="p-4 bg-white/5 border border-white/10 rounded-xl">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="font-semibold text-white">Speak as "I"</p>
                            <p className="text-xs text-slate-500 mt-1">
                                {personality.firstPerson
                                    ? `"I believe..." instead of "${twinName} believes..."`
                                    : `"${twinName} believes..." instead of "I believe..."`
                                }
                            </p>
                        </div>
                        <button
                            onClick={() => updatePersonality('firstPerson', !personality.firstPerson)}
                            className={`
                                w-14 h-7 rounded-full transition-all duration-200 relative
                                ${personality.firstPerson ? 'bg-indigo-600' : 'bg-white/10'}
                            `}
                        >
                            <div className={`
                                absolute top-1 w-5 h-5 bg-white rounded-full shadow-md transition-all duration-200
                                ${personality.firstPerson ? 'left-8' : 'left-1'}
                            `} />
                        </button>
                    </div>
                </div>

                {/* Custom Instructions */}
                <div className="space-y-3">
                    <label className="block text-sm font-semibold text-slate-300">
                        Custom Instructions <span className="text-slate-500">(Optional)</span>
                    </label>
                    <textarea
                        value={personality.customInstructions}
                        onChange={(e) => updatePersonality('customInstructions', e.target.value)}
                        placeholder="Add any special instructions for how your twin should communicate. E.g., 'Always mention my podcast when relevant' or 'Avoid using jargon'"
                        rows={3}
                        className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-sm transition-all resize-none"
                    />
                </div>

                {/* Preview */}
                <div className="p-4 bg-gradient-to-r from-indigo-500/10 to-purple-500/10 border border-indigo-500/20 rounded-2xl">
                    <p className="text-xs text-slate-400 mb-3">Sample Response Preview</p>
                    <div className="p-3 bg-black/20 rounded-xl">
                        <p className="text-sm text-white leading-relaxed">
                            {personality.firstPerson ? '"' : `"${twinName}: `}
                            {personality.tone === 'professional' && 'Thank you for your question. Based on my experience, I would recommend...'}
                            {personality.tone === 'friendly' && "Great question! I'd love to share my thoughts on this. From what I've seen..."}
                            {personality.tone === 'casual' && "Oh yeah, I get asked this a lot! So basically, what I've found is..."}
                            {personality.tone === 'technical' && 'To address this precisely, we need to consider the following factors...'}
                            {personality.firstPerson ? '"' : '"'}
                        </p>
                    </div>
                </div>
            </div>
        </WizardStep>
    );
}
