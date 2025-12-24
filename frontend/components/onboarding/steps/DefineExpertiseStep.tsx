'use client';

import React, { useState } from 'react';
import { WizardStep } from '../Wizard';

interface DefineExpertiseStepProps {
    selectedDomains: string[];
    customExpertise: string[];
    onDomainsChange: (domains: string[]) => void;
    onCustomExpertiseChange: (expertise: string[]) => void;
}

const SUGGESTED_DOMAINS = [
    { id: 'technology', label: 'Technology', icon: '💻' },
    { id: 'ai-ml', label: 'AI & Machine Learning', icon: '🤖' },
    { id: 'finance', label: 'Finance & Investing', icon: '📈' },
    { id: 'healthcare', label: 'Healthcare', icon: '🏥' },
    { id: 'legal', label: 'Legal', icon: '⚖️' },
    { id: 'marketing', label: 'Marketing', icon: '📣' },
    { id: 'sales', label: 'Sales', icon: '💼' },
    { id: 'engineering', label: 'Engineering', icon: '⚙️' },
    { id: 'education', label: 'Education', icon: '📚' },
    { id: 'consulting', label: 'Consulting', icon: '🎯' },
    { id: 'design', label: 'Design', icon: '🎨' },
    { id: 'product', label: 'Product Management', icon: '📦' },
];

export function DefineExpertiseStep({
    selectedDomains,
    customExpertise,
    onDomainsChange,
    onCustomExpertiseChange
}: DefineExpertiseStepProps) {
    const [customInput, setCustomInput] = useState('');

    const toggleDomain = (domainId: string) => {
        if (selectedDomains.includes(domainId)) {
            onDomainsChange(selectedDomains.filter(d => d !== domainId));
        } else {
            onDomainsChange([...selectedDomains, domainId]);
        }
    };

    const addCustomExpertise = () => {
        if (customInput.trim() && !customExpertise.includes(customInput.trim())) {
            onCustomExpertiseChange([...customExpertise, customInput.trim()]);
            setCustomInput('');
        }
    };

    const removeCustomExpertise = (expertise: string) => {
        onCustomExpertiseChange(customExpertise.filter(e => e !== expertise));
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            addCustomExpertise();
        }
    };

    return (
        <WizardStep
            title="Define Your Expertise"
            description="Select the domains where your twin can provide expert guidance"
        >
            <div className="max-w-2xl mx-auto space-y-8">
                {/* Domain Chips */}
                <div className="space-y-4">
                    <label className="block text-sm font-semibold text-slate-300">
                        Select Your Domains
                    </label>
                    <div className="flex flex-wrap gap-3">
                        {SUGGESTED_DOMAINS.map((domain) => {
                            const isSelected = selectedDomains.includes(domain.id);
                            return (
                                <button
                                    key={domain.id}
                                    onClick={() => toggleDomain(domain.id)}
                                    className={`
                                        flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200
                                        ${isSelected
                                            ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-500/25 scale-105'
                                            : 'bg-white/5 text-slate-300 border border-white/10 hover:bg-white/10 hover:border-white/20'
                                        }
                                    `}
                                >
                                    <span className="text-lg">{domain.icon}</span>
                                    <span>{domain.label}</span>
                                    {isSelected && (
                                        <svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                        </svg>
                                    )}
                                </button>
                            );
                        })}
                    </div>
                </div>

                {/* Custom Expertise */}
                <div className="space-y-4">
                    <label className="block text-sm font-semibold text-slate-300">
                        Add Custom Expertise
                    </label>
                    <div className="flex gap-2">
                        <input
                            type="text"
                            value={customInput}
                            onChange={(e) => setCustomInput(e.target.value)}
                            onKeyPress={handleKeyPress}
                            placeholder="e.g., Blockchain, Climate Tech, SaaS"
                            className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all"
                        />
                        <button
                            onClick={addCustomExpertise}
                            disabled={!customInput.trim()}
                            className="px-4 py-3 bg-white/10 border border-white/10 rounded-xl text-white hover:bg-white/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                            </svg>
                        </button>
                    </div>

                    {/* Custom Tags */}
                    {customExpertise.length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-3">
                            {customExpertise.map((expertise) => (
                                <span
                                    key={expertise}
                                    className="flex items-center gap-1 px-3 py-1.5 bg-emerald-500/20 text-emerald-300 rounded-lg text-sm font-medium border border-emerald-500/30"
                                >
                                    {expertise}
                                    <button
                                        onClick={() => removeCustomExpertise(expertise)}
                                        className="ml-1 hover:text-white transition-colors"
                                    >
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                                        </svg>
                                    </button>
                                </span>
                            ))}
                        </div>
                    )}
                </div>

                {/* Summary */}
                <div className="p-4 bg-gradient-to-r from-indigo-500/10 to-purple-500/10 border border-indigo-500/20 rounded-2xl">
                    <div className="flex items-center gap-2 mb-2">
                        <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span className="text-sm font-semibold text-white">Expertise Summary</span>
                    </div>
                    <p className="text-sm text-slate-300">
                        {selectedDomains.length + customExpertise.length > 0 ? (
                            <>
                                Your twin will be an expert in{' '}
                                <span className="text-indigo-300 font-medium">
                                    {[
                                        ...selectedDomains.map(d => SUGGESTED_DOMAINS.find(sd => sd.id === d)?.label || d),
                                        ...customExpertise
                                    ].join(', ')}
                                </span>
                            </>
                        ) : (
                            <span className="text-slate-500">Select at least one domain to continue</span>
                        )}
                    </p>
                </div>
            </div>
        </WizardStep>
    );
}
