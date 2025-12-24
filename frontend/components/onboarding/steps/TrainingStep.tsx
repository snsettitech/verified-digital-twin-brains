'use client';

import React, { useState, useEffect } from 'react';
import { WizardStep } from '../Wizard';

interface TrainingStepProps {
    twinName: string;
    contentCount: number;
    isTraining?: boolean;
    trainingProgress?: number;
    onStartTraining?: () => void;
}

export function TrainingStep({
    twinName,
    contentCount,
    isTraining = false,
    trainingProgress = 0,
    onStartTraining
}: TrainingStepProps) {
    const [progress, setProgress] = useState(trainingProgress);
    const [stage, setStage] = useState(0);

    const stages = [
        { name: 'Analyzing content', icon: '📖' },
        { name: 'Building knowledge graph', icon: '🧠' },
        { name: 'Learning your style', icon: '✍️' },
        { name: 'Optimizing responses', icon: '⚡' },
        { name: 'Running quality checks', icon: '✅' }
    ];

    // Simulated training progress
    useEffect(() => {
        if (isTraining && progress < 100) {
            const interval = setInterval(() => {
                setProgress(prev => {
                    const newProgress = prev + Math.random() * 3;
                    if (newProgress >= 100) {
                        clearInterval(interval);
                        return 100;
                    }
                    setStage(Math.floor((newProgress / 100) * stages.length));
                    return newProgress;
                });
            }, 200);
            return () => clearInterval(interval);
        }
    }, [isTraining, progress]);

    const isComplete = progress >= 100;

    return (
        <WizardStep
            title={isComplete ? "Training Complete!" : "Training Your Twin"}
            description={isComplete
                ? `${twinName} is ready to chat`
                : `Processing ${contentCount} piece${contentCount !== 1 ? 's' : ''} of content`}
        >
            <div className="max-w-md mx-auto">
                {/* Training Visualization */}
                <div className="relative p-8 bg-gradient-to-br from-slate-900 to-slate-800 rounded-3xl border border-white/10 mb-8">
                    {/* Animated Brain */}
                    <div className="relative w-32 h-32 mx-auto mb-6">
                        <div className={`absolute inset-0 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full blur-xl opacity-50 ${isComplete ? '' : 'animate-pulse'}`} />
                        <div className="relative w-32 h-32 bg-gradient-to-br from-slate-800 to-slate-900 rounded-full flex items-center justify-center border border-white/10">
                            {isComplete ? (
                                <svg className="w-16 h-16 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                </svg>
                            ) : (
                                <div className="text-5xl">{stages[stage]?.icon || '🧠'}</div>
                            )}
                        </div>

                        {/* Orbiting dots during training */}
                        {!isComplete && (
                            <div className="absolute inset-0 animate-spin" style={{ animationDuration: '3s' }}>
                                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-3 h-3 bg-indigo-400 rounded-full" />
                            </div>
                        )}
                    </div>

                    {/* Progress Bar */}
                    <div className="mb-4">
                        <div className="flex justify-between text-sm mb-2">
                            <span className="text-slate-400">
                                {isComplete ? 'Complete' : stages[stage]?.name || 'Processing...'}
                            </span>
                            <span className="text-white font-semibold">{Math.round(progress)}%</span>
                        </div>
                        <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                            <div
                                className={`h-full rounded-full transition-all duration-300 ${isComplete
                                        ? 'bg-gradient-to-r from-emerald-500 to-teal-500'
                                        : 'bg-gradient-to-r from-indigo-500 to-purple-500'
                                    }`}
                                style={{ width: `${progress}%` }}
                            />
                        </div>
                    </div>

                    {/* Stage indicators */}
                    <div className="flex justify-between mt-6">
                        {stages.map((s, index) => (
                            <div
                                key={index}
                                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm transition-all ${index <= stage
                                        ? 'bg-gradient-to-br from-indigo-500/20 to-purple-500/20 text-white'
                                        : 'bg-white/5 text-slate-600'
                                    }`}
                            >
                                {s.icon}
                            </div>
                        ))}
                    </div>
                </div>

                {/* Status Message */}
                {isComplete ? (
                    <div className="text-center p-6 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl">
                        <div className="text-emerald-400 font-semibold mb-1">🎉 Your twin is ready!</div>
                        <p className="text-slate-400 text-sm">
                            {twinName} has learned from your content and is ready to start chatting.
                        </p>
                    </div>
                ) : (
                    <div className="text-center">
                        <p className="text-slate-400 text-sm">
                            This usually takes 1-2 minutes depending on content size.
                            <br />
                            <span className="text-slate-500">You can continue - we'll train in the background.</span>
                        </p>
                    </div>
                )}
            </div>
        </WizardStep>
    );
}

export default TrainingStep;
