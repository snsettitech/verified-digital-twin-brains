'use client';

import React, { useState, useEffect } from 'react';

interface Specialization {
    id: string;
    name: string;
    description: string;
    tier: 'free' | 'premium';
    icon: string;
    coming_soon: boolean;
}

interface ChooseSpecializationStepProps {
    selectedSpecialization: string;
    onSpecializationChange: (specId: string) => void;
    userTier?: 'free' | 'premium';
}

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export const ChooseSpecializationStep: React.FC<ChooseSpecializationStepProps> = ({
    selectedSpecialization,
    onSpecializationChange,
    userTier = 'free'
}) => {
    const [specializations, setSpecializations] = useState<Specialization[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchSpecializations = async () => {
            try {
                const response = await fetch(`${API_BASE_URL}/specializations`);
                if (response.ok) {
                    const data = await response.json();
                    setSpecializations(data);
                } else {
                    // Fallback to default list
                    setSpecializations([
                        { id: 'vanilla', name: 'Digital Twin', description: 'General-purpose AI assistant', tier: 'free', icon: '🧠', coming_soon: false },
                        { id: 'vc', name: 'VC Brain', description: 'Venture Capital operations', tier: 'free', icon: '💼', coming_soon: false },
                    ]);
                }
            } catch (err) {
                setSpecializations([
                    { id: 'vanilla', name: 'Digital Twin', description: 'General-purpose AI assistant', tier: 'free', icon: '🧠', coming_soon: false },
                    { id: 'vc', name: 'VC Brain', description: 'Venture Capital operations', tier: 'free', icon: '💼', coming_soon: false },
                ]);
            }
            setLoading(false);
        };

        fetchSpecializations();
    }, []);

    const canSelect = (spec: Specialization) => {
        if (spec.coming_soon) return false;
        if (spec.tier === 'premium' && userTier !== 'premium') return false;
        return true;
    };

    if (loading) {
        return (
            <div className="space-y-6">
                <div className="text-center">
                    <h2 className="text-2xl font-black text-slate-900">Choose Your Brain Type</h2>
                    <p className="text-slate-500 mt-2">Loading options...</p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                    {[1, 2, 3, 4].map(i => (
                        <div key={i} className="h-40 bg-slate-100 rounded-2xl animate-pulse" />
                    ))}
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="text-center">
                <h2 className="text-2xl font-black text-slate-900">Choose Your Brain Type</h2>
                <p className="text-slate-500 mt-2">This determines how your AI twin behaves and what features are available</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
                {specializations.map((spec) => {
                    const isSelected = selectedSpecialization === spec.id;
                    const isDisabled = !canSelect(spec);
                    const isPremiumLocked = spec.tier === 'premium' && userTier !== 'premium';

                    return (
                        <button
                            key={spec.id}
                            onClick={() => canSelect(spec) && onSpecializationChange(spec.id)}
                            disabled={isDisabled}
                            className={`relative p-6 rounded-2xl border-2 text-left transition-all ${isSelected
                                ? 'border-indigo-500 bg-indigo-50 shadow-lg shadow-indigo-100'
                                : isDisabled
                                    ? 'border-slate-200 bg-slate-50 opacity-60 cursor-not-allowed'
                                    : 'border-slate-200 bg-white hover:border-indigo-300 hover:shadow-md'
                                }`}
                        >
                            {/* Premium Badge */}
                            {spec.tier === 'premium' && (
                                <span className="absolute top-3 right-3 px-2 py-0.5 text-[10px] font-bold text-amber-700 bg-amber-100 rounded-full">
                                    ✨ PREMIUM
                                </span>
                            )}

                            {/* Coming Soon Badge */}
                            {spec.coming_soon && (
                                <span className="absolute top-3 right-3 px-2 py-0.5 text-[10px] font-bold text-slate-500 bg-slate-200 rounded-full">
                                    COMING SOON
                                </span>
                            )}

                            {/* Icon */}
                            <div className="text-4xl mb-3">{spec.icon}</div>

                            {/* Name */}
                            <h3 className={`text-lg font-bold ${isSelected ? 'text-indigo-900' : 'text-slate-900'}`}>
                                {spec.name}
                            </h3>

                            {/* Description */}
                            <p className={`text-sm mt-1 ${isSelected ? 'text-indigo-700' : 'text-slate-500'}`}>
                                {spec.description}
                            </p>

                            {/* Locked Message */}
                            {isPremiumLocked && !spec.coming_soon && (
                                <p className="text-xs text-amber-600 mt-3 font-medium">
                                    🔒 Upgrade to Premium to unlock
                                </p>
                            )}

                            {/* Selected Check */}
                            {isSelected && (
                                <div className="absolute top-3 left-3 w-6 h-6 bg-indigo-500 rounded-full flex items-center justify-center">
                                    <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7" />
                                    </svg>
                                </div>
                            )}
                        </button>
                    );
                })}
            </div>

            {/* Info Box */}
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center">
                <p className="text-sm text-blue-700">
                    <strong>Note:</strong> You cannot change the brain type after creation.
                    Choose carefully based on your needs.
                </p>
            </div>
        </div>
    );
};

export default ChooseSpecializationStep;
