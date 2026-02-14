'use client';

import Link from 'next/link';

const SIMULATOR_PAGES = [
    {
        title: 'Owner Simulator',
        description: 'Test normal owner chat behavior (no training session context).',
        href: '/dashboard/simulator/owner',
    },
    {
        title: 'Training Simulator',
        description: 'Test owner training behavior with an active training session.',
        href: '/dashboard/simulator/training',
    },
    {
        title: 'Public Simulator',
        description: 'Test public-facing behavior and validate share-chat flow.',
        href: '/dashboard/simulator/public',
    },
    {
        title: 'Training Workflow',
        description: 'Full end-to-end training module with all steps in one page.',
        href: '/dashboard/simulator/workflow',
    },
    {
        title: 'Retrieval Debug',
        description: 'Inspect retrieval health, namespaces, metrics, and live query diagnostics.',
        href: '/dashboard/simulator/retrieval-debug',
    },
];

export default function SimulatorHubPage() {
    return (
        <div className="min-h-screen bg-[#0a0a0f] text-white p-6 md:p-10">
            <div className="max-w-5xl mx-auto space-y-8">
                <div>
                    <h1 className="text-3xl font-black tracking-tight">Simulator Hub</h1>
                    <p className="text-sm text-slate-400 mt-2">
                        Use separate simulator pages to isolate behavior and debug faster.
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {SIMULATOR_PAGES.map((page) => (
                        <Link
                            key={page.href}
                            href={page.href}
                            className="group rounded-2xl border border-white/10 bg-white/5 p-5 hover:border-indigo-400/40 hover:bg-white/[0.07] transition-colors"
                        >
                            <div className="text-lg font-bold">{page.title}</div>
                            <div className="text-sm text-slate-400 mt-2">{page.description}</div>
                            <div className="text-xs text-indigo-300 mt-4 font-semibold uppercase tracking-wider">
                                Open
                            </div>
                        </Link>
                    ))}
                </div>
            </div>
        </div>
    );
}
