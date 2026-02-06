'use client';

import React from 'react';
import { useTwin } from '@/lib/context/TwinContext';
import { TrainingTab } from '@/components/console/tabs/TrainingTab';

export default function TrainingModulePage() {
    const { activeTwin, isLoading } = useTwin();

    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-[#0a0a0f]">
                <div className="w-12 h-12 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
            </div>
        );
    }

    if (!activeTwin) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-[#0a0a0f] p-6">
                <div className="max-w-md text-center space-y-4">
                    <h2 className="text-xl font-bold text-white">No twin selected</h2>
                    <p className="text-sm text-slate-400">
                        Select or create a twin in your dashboard to start training.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[#0a0a0f]">
            <TrainingTab twinId={activeTwin.id} />
        </div>
    );
}
