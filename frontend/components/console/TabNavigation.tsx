'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';

export interface Tab {
    id: string;
    label: string;
    icon: React.ReactNode;
    badge?: number;
}

interface TabNavigationProps {
    tabs: Tab[];
    twinId: string;
    activeTab?: string;
    onChange?: (tabId: string) => void;
}

export function TabNavigation({ tabs, twinId, activeTab, onChange }: TabNavigationProps) {
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const currentTab = activeTab || searchParams.get('tab') || tabs[0]?.id;

    return (
        <div className="border-b border-white/10">
            <nav className="flex gap-1 px-6 -mb-px overflow-x-auto scrollbar-thin">
                {tabs.map((tab) => {
                    const isActive = currentTab === tab.id;

                    return (
                        <Link
                            key={tab.id}
                            href={`/dashboard/twins/${twinId}?tab=${tab.id}`}
                            onClick={() => onChange?.(tab.id)}
                            className={`
                relative flex items-center gap-2 px-4 py-3 text-sm font-medium whitespace-nowrap transition-all
                ${isActive
                                    ? 'text-white'
                                    : 'text-slate-400 hover:text-slate-200'}
              `}
                        >
                            <span className={`${isActive ? 'text-indigo-400' : ''}`}>
                                {tab.icon}
                            </span>
                            {tab.label}

                            {tab.badge !== undefined && tab.badge > 0 && (
                                <span className={`
                  ml-1 px-1.5 py-0.5 text-xs font-semibold rounded-full
                  ${isActive
                                        ? 'bg-indigo-500 text-white'
                                        : 'bg-white/10 text-slate-400'}
                `}>
                                    {tab.badge > 99 ? '99+' : tab.badge}
                                </span>
                            )}

                            {/* Active indicator */}
                            {isActive && (
                                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full" />
                            )}
                        </Link>
                    );
                })}
            </nav>
        </div>
    );
}

export default TabNavigation;
