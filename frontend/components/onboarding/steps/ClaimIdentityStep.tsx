'use client';

import React, { useState, useEffect } from 'react';
import { WizardStep } from '../Wizard';

interface ClaimIdentityStepProps {
    twinName: string;
    handle: string;
    tagline: string;
    avatarUrl?: string;
    onTwinNameChange: (name: string) => void;
    onHandleChange: (handle: string) => void;
    onTaglineChange: (tagline: string) => void;
    onAvatarChange?: (url: string) => void;
}

export function ClaimIdentityStep({
    twinName,
    handle,
    tagline,
    avatarUrl,
    onTwinNameChange,
    onHandleChange,
    onTaglineChange,
    onAvatarChange
}: ClaimIdentityStepProps) {
    const [handleError, setHandleError] = useState<string | null>(null);
    const [isCheckingHandle, setIsCheckingHandle] = useState(false);

    // Generate initials for avatar placeholder
    const initials = twinName
        .split(' ')
        .map(n => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2) || '?';

    // Debounced handle validation
    useEffect(() => {
        if (!handle) {
            setHandleError(null);
            return;
        }

        const timer = setTimeout(async () => {
            setIsCheckingHandle(true);
            // Validate handle format
            const handleRegex = /^[a-z0-9_]{3,20}$/;
            if (!handleRegex.test(handle)) {
                setHandleError('Handle must be 3-20 characters, lowercase letters, numbers, and underscores only');
                setIsCheckingHandle(false);
                return;
            }
            // TODO: Check uniqueness against backend
            setHandleError(null);
            setIsCheckingHandle(false);
        }, 500);

        return () => clearTimeout(timer);
    }, [handle]);

    return (
        <WizardStep
            title="Claim Your Identity"
            description="Give your digital twin a name and unique handle"
        >
            <div className="max-w-md mx-auto space-y-8">
                {/* Avatar Preview */}
                <div className="flex justify-center">
                    <div className="relative group">
                        <div className="w-28 h-28 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-3xl font-bold text-white shadow-2xl shadow-indigo-500/30">
                            {avatarUrl ? (
                                <img src={avatarUrl} alt="Avatar" className="w-full h-full rounded-full object-cover" />
                            ) : (
                                initials
                            )}
                        </div>
                        <button className="absolute bottom-0 right-0 w-8 h-8 bg-white/10 backdrop-blur-sm border border-white/20 rounded-full flex items-center justify-center text-white hover:bg-white/20 transition-colors group-hover:scale-110">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                        </button>
                    </div>
                </div>

                {/* Name Input */}
                <div className="space-y-2">
                    <label className="block text-sm font-semibold text-slate-300">
                        Display Name <span className="text-red-400">*</span>
                    </label>
                    <input
                        type="text"
                        value={twinName}
                        onChange={(e) => onTwinNameChange(e.target.value)}
                        placeholder="Dr. Sarah Chen"
                        className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all"
                    />
                    <p className="text-xs text-slate-500">This is how your twin will introduce itself</p>
                </div>

                {/* Handle Input */}
                <div className="space-y-2">
                    <label className="block text-sm font-semibold text-slate-300">
                        Unique Handle <span className="text-red-400">*</span>
                    </label>
                    <div className="relative">
                        <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500">@</span>
                        <input
                            type="text"
                            value={handle}
                            onChange={(e) => onHandleChange(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
                            placeholder="sarahchen"
                            className={`w-full pl-8 pr-10 py-3 bg-white/5 border rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 transition-all ${handleError
                                    ? 'border-red-500/50 focus:ring-red-500/50'
                                    : handle && !isCheckingHandle
                                        ? 'border-emerald-500/50 focus:ring-emerald-500/50'
                                        : 'border-white/10 focus:ring-indigo-500/50 focus:border-indigo-500/50'
                                }`}
                        />
                        <div className="absolute right-4 top-1/2 -translate-y-1/2">
                            {isCheckingHandle ? (
                                <svg className="w-5 h-5 text-slate-400 animate-spin" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                </svg>
                            ) : handle && !handleError ? (
                                <svg className="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                </svg>
                            ) : null}
                        </div>
                    </div>
                    {handleError ? (
                        <p className="text-xs text-red-400">{handleError}</p>
                    ) : (
                        <p className="text-xs text-slate-500">Your unique identifier for sharing</p>
                    )}
                </div>

                {/* Tagline Input */}
                <div className="space-y-2">
                    <label className="block text-sm font-semibold text-slate-300">
                        Tagline
                    </label>
                    <input
                        type="text"
                        value={tagline}
                        onChange={(e) => onTaglineChange(e.target.value)}
                        placeholder="AI/ML Expert & Startup Advisor"
                        maxLength={80}
                        className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all"
                    />
                    <p className="text-xs text-slate-500">{tagline.length}/80 characters</p>
                </div>

                {/* Preview Card */}
                {twinName && (
                    <div className="p-4 bg-gradient-to-r from-indigo-500/10 to-purple-500/10 border border-indigo-500/20 rounded-2xl">
                        <p className="text-xs text-slate-400 mb-2">Preview</p>
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-sm font-bold text-white">
                                {initials}
                            </div>
                            <div>
                                <p className="font-semibold text-white">{twinName}</p>
                                {handle && <p className="text-xs text-slate-400">@{handle}</p>}
                            </div>
                        </div>
                        {tagline && <p className="mt-2 text-sm text-slate-300">{tagline}</p>}
                    </div>
                )}
            </div>
        </WizardStep>
    );
}
