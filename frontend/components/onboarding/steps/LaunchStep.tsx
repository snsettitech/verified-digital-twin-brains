'use client';

import React, { useState, useEffect } from 'react';
import { WizardStep } from '../Wizard';

interface LaunchStepProps {
    twinName: string;
    handle: string;
    twinId: string | null;
    onLaunch: () => Promise<void>;
}

export function LaunchStep({
    twinName,
    handle,
    twinId,
    onLaunch
}: LaunchStepProps) {
    const [isLaunching, setIsLaunching] = useState(false);
    const [isLaunched, setIsLaunched] = useState(false);
    const [shareUrl, setShareUrl] = useState('');
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        if (twinId && handle) {
            const baseUrl = window.location.origin;
            setShareUrl(`${baseUrl}/share/${handle}`);
        }
    }, [twinId, handle]);

    const handleLaunch = async () => {
        setIsLaunching(true);
        try {
            await onLaunch();
            setIsLaunched(true);
        } catch (error) {
            console.error('Launch failed:', error);
        } finally {
            setIsLaunching(false);
        }
    };

    const copyShareUrl = () => {
        navigator.clipboard.writeText(shareUrl);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const initials = twinName
        .split(' ')
        .map(n => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2) || '?';

    if (isLaunched) {
        return (
            <WizardStep>
                <div className="max-w-lg mx-auto text-center space-y-8">
                    {/* Success Animation */}
                    <div className="relative">
                        <div className="w-32 h-32 mx-auto rounded-full bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center shadow-2xl shadow-emerald-500/30 animate-bounce">
                            <svg className="w-16 h-16 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                            </svg>
                        </div>
                        {/* Confetti Effect */}
                        <div className="absolute inset-0 pointer-events-none">
                            {[...Array(12)].map((_, i) => (
                                <div
                                    key={i}
                                    className="absolute w-3 h-3 rounded-full animate-ping"
                                    style={{
                                        backgroundColor: ['#6366f1', '#8b5cf6', '#10b981', '#f59e0b'][i % 4],
                                        left: `${20 + (i * 5)}%`,
                                        top: `${10 + (i * 7) % 50}%`,
                                        animationDelay: `${i * 100}ms`,
                                        animationDuration: '2s'
                                    }}
                                />
                            ))}
                        </div>
                    </div>

                    <div>
                        <h1 className="text-4xl font-black text-white mb-3">
                            🎉 {twinName} is Live!
                        </h1>
                        <p className="text-lg text-slate-400">
                            Your digital twin is ready to engage with the world
                        </p>
                    </div>

                    {/* Share URL */}
                    {shareUrl && (
                        <div className="p-4 bg-white/5 border border-white/10 rounded-2xl">
                            <p className="text-xs text-slate-400 mb-2">Share Link</p>
                            <div className="flex items-center gap-2">
                                <div className="flex-1 px-3 py-2 bg-black/20 rounded-lg text-sm text-slate-300 truncate">
                                    {shareUrl}
                                </div>
                                <button
                                    onClick={copyShareUrl}
                                    className={`px-4 py-2 rounded-lg font-medium text-sm transition-all ${copied
                                            ? 'bg-emerald-500 text-white'
                                            : 'bg-white/10 text-white hover:bg-white/20'
                                        }`}
                                >
                                    {copied ? 'Copied!' : 'Copy'}
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Next Steps */}
                    <div className="grid grid-cols-2 gap-3 pt-4">
                        <a
                            href="/dashboard"
                            className="p-4 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-all text-left"
                        >
                            <div className="w-10 h-10 bg-indigo-500/20 rounded-lg flex items-center justify-center mb-3">
                                <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
                                </svg>
                            </div>
                            <p className="font-semibold text-white text-sm">Go to Dashboard</p>
                            <p className="text-xs text-slate-500 mt-1">Manage your twin</p>
                        </a>
                        <a
                            href="/dashboard/studio"
                            className="p-4 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-all text-left"
                        >
                            <div className="w-10 h-10 bg-purple-500/20 rounded-lg flex items-center justify-center mb-3">
                                <svg className="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                                </svg>
                            </div>
                            <p className="font-semibold text-white text-sm">Add More Content</p>
                            <p className="text-xs text-slate-500 mt-1">Train your twin further</p>
                        </a>
                    </div>
                </div>
            </WizardStep>
        );
    }

    return (
        <WizardStep
            title="Ready to Launch?"
            description="Your digital twin is configured and ready to go live"
        >
            <div className="max-w-lg mx-auto text-center space-y-8">
                {/* Twin Preview Card */}
                <div className="p-6 bg-gradient-to-br from-indigo-500/10 via-purple-500/10 to-pink-500/10 border border-indigo-500/20 rounded-3xl">
                    <div className="w-20 h-20 mx-auto rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-2xl font-bold text-white shadow-xl shadow-indigo-500/30 mb-4">
                        {initials}
                    </div>
                    <h3 className="text-xl font-bold text-white">{twinName}</h3>
                    {handle && <p className="text-slate-400 text-sm">@{handle}</p>}
                </div>

                {/* Checklist */}
                <div className="text-left space-y-3">
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Setup Complete</p>
                    {[
                        'Identity configured',
                        'Expertise defined',
                        'Personality set',
                        'Ready for conversations'
                    ].map((item, index) => (
                        <div key={index} className="flex items-center gap-3 text-sm">
                            <div className="w-5 h-5 rounded-full bg-emerald-500/20 flex items-center justify-center">
                                <svg className="w-3 h-3 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                </svg>
                            </div>
                            <span className="text-slate-300">{item}</span>
                        </div>
                    ))}
                </div>

                {/* Launch Button */}
                <button
                    onClick={handleLaunch}
                    disabled={isLaunching}
                    className="w-full py-4 bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 text-white font-bold text-lg rounded-2xl shadow-xl shadow-indigo-500/30 hover:shadow-indigo-500/50 transition-all disabled:opacity-70 disabled:cursor-not-allowed relative overflow-hidden group"
                >
                    {isLaunching ? (
                        <span className="flex items-center justify-center gap-2">
                            <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                            </svg>
                            Launching...
                        </span>
                    ) : (
                        <span className="flex items-center justify-center gap-2">
                            🚀 Launch {twinName}
                        </span>
                    )}
                    <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/20 to-white/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-1000" />
                </button>

                <p className="text-xs text-slate-500">
                    You can always update your twin's settings from the dashboard
                </p>
            </div>
        </WizardStep>
    );
}
