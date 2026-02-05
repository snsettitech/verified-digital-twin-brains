'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useTwin } from '@/lib/context/TwinContext';



const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// Specialization icons
const SPEC_ICONS: Record<string, string> = {
    vanilla: '🧠',
};

export const TwinSelector: React.FC = () => {
    const router = useRouter();
    const { twins, isLoading: loading, setActiveTwin, activeTwin } = useTwin();
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Derived: current twin from the context list
    // Handle case where context might still be hydrating
    const currentTwin = activeTwin;

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleTwinSelect = (twinId: string) => {
        setActiveTwin(twinId);
        setIsOpen(false);
    };

    const handleCreateNew = () => {
        // Clear the existing twin check so onboarding shows
        localStorage.removeItem('activeTwinId');
        router.push('/onboarding');
    };

    if (loading) {
        return (
            <div className="px-4 py-3">
                <div className="h-12 bg-slate-100 rounded-xl animate-pulse" />
            </div>
        );
    }

    if (twins.length === 0) {
        return (
            <div className="px-4 py-3">
                <button
                    onClick={handleCreateNew}
                    className="w-full flex items-center gap-3 px-4 py-3 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-xl hover:from-indigo-600 hover:to-purple-700 transition-all shadow-lg shadow-indigo-200"
                >
                    <span className="text-xl">✨</span>
                    <span className="font-semibold">Create Your First Twin</span>
                </button>
            </div>
        );
    }

    return (
        <div className="px-4 py-3" ref={dropdownRef}>
            {/* Current Twin Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center gap-3 px-4 py-3 bg-white border border-slate-200 rounded-xl hover:border-indigo-300 hover:shadow-md transition-all"
            >
                {/* Icon */}
                <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center text-white text-lg">
                    {SPEC_ICONS[currentTwin?.specialization || 'vanilla'] || '🧠'}
                </div>

                {/* Name */}
                <div className="flex-1 text-left">
                    <p className="font-semibold text-slate-900 truncate">
                        {currentTwin?.name || 'Select Twin'}
                    </p>
                    <p className="text-xs text-slate-500 capitalize">
                        Digital Twin
                    </p>
                </div>

                {/* Chevron */}
                <svg
                    className={`w-5 h-5 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                </svg>
            </button>

            {/* Dropdown */}
            {isOpen && (
                <div className="absolute left-4 right-4 mt-2 bg-white border border-slate-200 rounded-xl shadow-xl z-50 overflow-hidden">
                    {/* Twin List */}
                    <div className="max-h-60 overflow-y-auto">
                        {twins.map((twin) => (
                            <button
                                key={twin.id}
                                onClick={() => handleTwinSelect(twin.id)}
                                className={`w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-50 transition-colors ${twin.id === activeTwin?.id ? 'bg-indigo-50' : ''
                                    }`}
                            >
                                <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm ${twin.id === activeTwin?.id
                                    ? 'bg-indigo-500 text-white'
                                    : 'bg-slate-100 text-slate-600'
                                    }`}>
                                    {SPEC_ICONS[twin.specialization || 'vanilla'] || '🧠'}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className={`font-medium truncate ${twin.id === activeTwin?.id ? 'text-indigo-900' : 'text-slate-900'
                                        }`}>
                                        {twin.name}
                                    </p>
                                    <p className="text-xs text-slate-500 capitalize">
                                        Digital Twin
                                    </p>
                                </div>
                                {twin.id === activeTwin?.id && (
                                    <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                    </svg>
                                )}
                            </button>
                        ))}
                    </div>

                    {/* Divider */}
                    <div className="border-t border-slate-100" />

                    {/* Create New Button */}
                    <button
                        onClick={handleCreateNew}
                        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-indigo-50 transition-colors"
                    >
                        <div className="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                            </svg>
                        </div>
                        <span className="font-medium text-indigo-600">Create New Twin</span>
                    </button>
                </div>
            )}
        </div>
    );
};

export default TwinSelector;
