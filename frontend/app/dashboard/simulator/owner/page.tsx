'use client';

import Link from 'next/link';
import { SimulatorView } from '@/components/training';
import { useTwin } from '@/lib/context/TwinContext';

export default function SimulatorOwnerPage() {
    const { activeTwin } = useTwin();

    return (
        <div className="min-h-screen bg-[#0a0a0f] text-white p-6 md:p-10">
            <div className="max-w-6xl mx-auto space-y-4">
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <h1 className="text-2xl font-black tracking-tight">Owner Simulator</h1>
                        <p className="text-sm text-slate-400 mt-1">
                            Dedicated page for normal owner chat behavior.
                        </p>
                    </div>
                    <Link
                        href="/dashboard/simulator"
                        className="px-3 py-2 text-xs font-semibold rounded-lg border border-white/15 bg-white/5 hover:bg-white/10 transition-colors"
                    >
                        Back to Hub
                    </Link>
                </div>

                <SimulatorView twinId={activeTwin?.id} mode="owner" />
            </div>
        </div>
    );
}
