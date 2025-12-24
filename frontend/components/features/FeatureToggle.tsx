'use client';

import React from 'react';
import { useFeatureFlags, FeatureFlags } from '@/lib/features/FeatureFlags';

interface FeatureToggleProps {
    flag: keyof FeatureFlags;
    label: string;
    description?: string;
    disabled?: boolean;
}

export function FeatureToggle({ flag, label, description, disabled }: FeatureToggleProps) {
    const { isEnabled, toggleFlag } = useFeatureFlags();
    const enabled = isEnabled(flag);

    return (
        <div className={`flex items-center justify-between p-4 bg-white/5 border border-white/10 rounded-xl ${disabled ? 'opacity-50' : ''}`}>
            <div className="flex-1">
                <h4 className="text-sm font-medium text-white">{label}</h4>
                {description && (
                    <p className="text-xs text-slate-400 mt-0.5">{description}</p>
                )}
            </div>
            <button
                onClick={() => !disabled && toggleFlag(flag)}
                disabled={disabled}
                className={`relative w-12 h-6 rounded-full transition-colors ${enabled ? 'bg-indigo-500' : 'bg-slate-600'
                    } ${disabled ? 'cursor-not-allowed' : 'cursor-pointer'}`}
            >
                <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${enabled ? 'left-7' : 'left-1'
                    }`} />
            </button>
        </div>
    );
}

// Feature group for organizing related flags
interface FeatureGroupProps {
    title: string;
    description?: string;
    children: React.ReactNode;
}

export function FeatureGroup({ title, description, children }: FeatureGroupProps) {
    return (
        <div className="space-y-3">
            <div>
                <h3 className="text-sm font-semibold text-white uppercase tracking-wide">{title}</h3>
                {description && (
                    <p className="text-xs text-slate-500 mt-0.5">{description}</p>
                )}
            </div>
            <div className="space-y-2">
                {children}
            </div>
        </div>
    );
}

// Complete feature flags panel for settings
export function FeatureFlagsPanel() {
    const { resetFlags } = useFeatureFlags();

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-lg font-bold text-white">Feature Flags</h2>
                    <p className="text-sm text-slate-400">Enable or disable experimental features</p>
                </div>
                <button
                    onClick={resetFlags}
                    className="px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
                >
                    Reset to Defaults
                </button>
            </div>

            <FeatureGroup title="Cognitive UX" description="Enhanced interview and visualization features">
                <FeatureToggle
                    flag="cognitiveMode"
                    label="Cognitive Mode"
                    description="Enable enhanced AI-driven interview experience"
                />
                <FeatureToggle
                    flag="splitBrainLayout"
                    label="Split-Brain Layout"
                    description="Show chat and knowledge graph side-by-side"
                />
                <FeatureToggle
                    flag="knowledgeGraphPreview"
                    label="Knowledge Graph Preview"
                    description="Real-time visualization of collected knowledge"
                />
            </FeatureGroup>

            <FeatureGroup title="Premium Features" description="Advanced capabilities for power users">
                <FeatureToggle
                    flag="advancedAnalytics"
                    label="Advanced Analytics"
                    description="Detailed usage and performance metrics"
                />
                <FeatureToggle
                    flag="customBranding"
                    label="Custom Branding"
                    description="White-label your twin's appearance"
                />
                <FeatureToggle
                    flag="teamCollaboration"
                    label="Team Collaboration"
                    description="Invite team members to manage twins"
                />
            </FeatureGroup>

            <FeatureGroup title="Experimental" description="Features in development - may be unstable">
                <FeatureToggle
                    flag="voiceCloning"
                    label="Voice Cloning"
                    description="Clone your voice for audio responses"
                    disabled
                />
                <FeatureToggle
                    flag="realTimeSync"
                    label="Real-Time Sync"
                    description="Live sync across devices"
                    disabled
                />
                <FeatureToggle
                    flag="aiSuggestions"
                    label="AI Suggestions"
                    description="Smart suggestions during interviews"
                />
            </FeatureGroup>
        </div>
    );
}

export default FeatureToggle;
