'use client';

import React, { useState } from 'react';

interface Escalation {
    id: string;
    question: string;
    answer?: string;
    status: 'pending' | 'approved' | 'rejected';
    createdAt: string;
    source?: string;
}

interface EscalationsTabProps {
    twinId: string;
    escalations?: Escalation[];
    onApprove?: (id: string, answer: string) => void;
    onReject?: (id: string) => void;
}

export function EscalationsTab({ twinId, escalations = [], onApprove, onReject }: EscalationsTabProps) {
    const [selectedEscalation, setSelectedEscalation] = useState<Escalation | null>(null);
    const [editedAnswer, setEditedAnswer] = useState('');
    const [filter, setFilter] = useState<'all' | 'pending' | 'approved' | 'rejected'>('pending');

    const filteredEscalations = escalations.filter(
        e => filter === 'all' || e.status === filter
    );

    const handleSelect = (escalation: Escalation) => {
        setSelectedEscalation(escalation);
        setEditedAnswer(escalation.answer || '');
    };

    const handleApprove = () => {
        if (selectedEscalation && editedAnswer) {
            onApprove?.(selectedEscalation.id, editedAnswer);
            setSelectedEscalation(null);
        }
    };

    const handleReject = () => {
        if (selectedEscalation) {
            onReject?.(selectedEscalation.id);
            setSelectedEscalation(null);
        }
    };

    const statusColors = {
        pending: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
        approved: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
        rejected: 'bg-red-500/20 text-red-400 border-red-500/30'
    };

    return (
        <div className="flex h-[calc(100vh-200px)]">
            {/* List Panel */}
            <div className="w-1/2 border-r border-white/10 flex flex-col">
                {/* Filters */}
                <div className="p-4 border-b border-white/10">
                    <div className="flex gap-2">
                        {(['pending', 'approved', 'rejected', 'all'] as const).map((f) => (
                            <button
                                key={f}
                                onClick={() => setFilter(f)}
                                className={`px-3 py-1.5 text-xs font-medium rounded-lg capitalize transition-colors ${filter === f
                                        ? 'bg-white/10 text-white'
                                        : 'text-slate-400 hover:text-white hover:bg-white/5'
                                    }`}
                            >
                                {f} {f === 'pending' && escalations.filter(e => e.status === 'pending').length > 0 && (
                                    <span className="ml-1 px-1.5 py-0.5 bg-amber-500 text-white text-[10px] rounded-full">
                                        {escalations.filter(e => e.status === 'pending').length}
                                    </span>
                                )}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Escalation List */}
                <div className="flex-1 overflow-y-auto">
                    {filteredEscalations.length === 0 ? (
                        <div className="p-8 text-center">
                            <div className="w-16 h-16 mx-auto mb-4 bg-emerald-500/10 rounded-2xl flex items-center justify-center">
                                <svg className="w-8 h-8 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                            </div>
                            <h3 className="text-lg font-semibold text-white mb-1">
                                {filter === 'pending' ? "You're all caught up!" : 'No escalations found'}
                            </h3>
                            <p className="text-slate-400 text-sm mb-6">
                                {filter === 'pending'
                                    ? "No questions need your review. Your twin is handling things."
                                    : "No escalations match this filter."}
                            </p>
                            {filter === 'pending' && (
                                <div className="flex flex-col sm:flex-row gap-3 justify-center">
                                    <a
                                        href={`/dashboard/twins/${twinId}?tab=chat`}
                                        className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-xl transition-colors"
                                    >
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                                        </svg>
                                        Test Your Twin
                                    </a>
                                    <a
                                        href={`/dashboard/twins/${twinId}?tab=training`}
                                        className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 text-white text-sm font-medium rounded-xl border border-white/10 transition-colors"
                                    >
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                                        </svg>
                                        Add Knowledge
                                    </a>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="divide-y divide-white/5">
                            {filteredEscalations.map((escalation) => (
                                <button
                                    key={escalation.id}
                                    onClick={() => handleSelect(escalation)}
                                    className={`w-full p-4 text-left hover:bg-white/5 transition-colors ${selectedEscalation?.id === escalation.id ? 'bg-white/5' : ''
                                        }`}
                                >
                                    <div className="flex items-start justify-between mb-2">
                                        <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded border ${statusColors[escalation.status]}`}>
                                            {escalation.status}
                                        </span>
                                        <span className="text-xs text-slate-500">{escalation.createdAt}</span>
                                    </div>
                                    <p className="text-white text-sm line-clamp-2">{escalation.question}</p>
                                    {escalation.source && (
                                        <p className="text-slate-500 text-xs mt-1">via {escalation.source}</p>
                                    )}
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Detail Panel */}
            <div className="w-1/2 flex flex-col">
                {selectedEscalation ? (
                    <>
                        <div className="p-6 border-b border-white/10">
                            <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded border mb-3 ${statusColors[selectedEscalation.status]}`}>
                                {selectedEscalation.status}
                            </span>
                            <h3 className="text-lg font-semibold text-white mb-2">Question Asked:</h3>
                            <p className="text-slate-300 bg-white/5 p-4 rounded-xl">{selectedEscalation.question}</p>
                        </div>

                        <div className="flex-1 p-6 overflow-y-auto">
                            <h3 className="text-lg font-semibold text-white mb-3">Suggested Answer:</h3>
                            <textarea
                                value={editedAnswer}
                                onChange={(e) => setEditedAnswer(e.target.value)}
                                placeholder="Write or edit the answer..."
                                rows={8}
                                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all resize-none"
                            />
                            <p className="text-xs text-slate-500 mt-2">
                                This answer will be stored as verified knowledge for future questions.
                            </p>
                        </div>

                        <div className="p-4 border-t border-white/10 flex gap-3">
                            <button
                                onClick={handleReject}
                                className="flex-1 py-2.5 text-sm font-medium text-red-400 hover:text-white bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-xl transition-colors"
                            >
                                Reject
                            </button>
                            <button
                                onClick={handleApprove}
                                disabled={!editedAnswer.trim()}
                                className="flex-1 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 rounded-xl transition-all disabled:opacity-50"
                            >
                                Approve Answer
                            </button>
                        </div>
                    </>
                ) : (
                    <div className="flex-1 flex items-center justify-center">
                        <div className="text-center">
                            <svg className="w-16 h-16 mx-auto mb-4 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
                            </svg>
                            <h3 className="text-lg font-semibold text-white mb-1">Select an escalation</h3>
                            <p className="text-slate-400 text-sm">Choose an item from the list to review</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

export default EscalationsTab;
