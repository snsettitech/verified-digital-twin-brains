'use client';

import React, { useState } from 'react';

interface Action {
    id: string;
    name: string;
    trigger: string;
    status: 'active' | 'paused';
    executions: number;
}

interface ActionsTabProps {
    twinId: string;
    actions?: Action[];
    onToggleAction?: (id: string, active: boolean) => void;
    onCreateAction?: () => void;
}

export function ActionsTab({ twinId, actions = [], onToggleAction, onCreateAction }: ActionsTabProps) {
    const [showCreateModal, setShowCreateModal] = useState(false);

    const triggerTypes = [
        { id: 'keyword', label: 'Keyword Match', icon: '🔤', description: 'Trigger when message contains specific words' },
        { id: 'intent', label: 'Intent Detection', icon: '🎯', description: 'Trigger based on detected user intent' },
        { id: 'schedule', label: 'Scheduled', icon: '⏰', description: 'Run at specific times or intervals' },
        { id: 'escalation', label: 'On Escalation', icon: '🚨', description: 'Trigger when twin escalates a question' }
    ];

    return (
        <div className="p-6 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold text-white">Automation Actions</h2>
                    <p className="text-slate-400 text-sm mt-1">Create automated workflows triggered by your twin's conversations</p>
                </div>
                <button
                    onClick={() => setShowCreateModal(true)}
                    className="px-4 py-2 text-sm font-semibold text-white bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 rounded-lg shadow-lg shadow-indigo-500/20 transition-all"
                >
                    <span className="flex items-center gap-2">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                        </svg>
                        Create Action
                    </span>
                </button>
            </div>

            {/* Actions List */}
            {actions.length === 0 ? (
                <div className="bg-white/5 border border-white/10 rounded-2xl p-12 text-center">
                    <div className="w-20 h-20 mx-auto mb-4 bg-gradient-to-br from-indigo-500/20 to-purple-500/20 rounded-2xl flex items-center justify-center">
                        <svg className="w-10 h-10 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                    </div>
                    <h3 className="text-lg font-semibold text-white mb-2">No actions yet</h3>
                    <p className="text-slate-400 text-sm mb-6 max-w-md mx-auto">
                        Create automated actions that trigger based on conversations, keywords, or schedules.
                    </p>

                    {/* Trigger Type Cards */}
                    <div className="grid grid-cols-2 gap-4 max-w-xl mx-auto">
                        {triggerTypes.map((trigger) => (
                            <button
                                key={trigger.id}
                                onClick={() => setShowCreateModal(true)}
                                className="p-4 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-left transition-colors"
                            >
                                <span className="text-2xl">{trigger.icon}</span>
                                <h4 className="text-white font-medium mt-2">{trigger.label}</h4>
                                <p className="text-slate-500 text-xs mt-1">{trigger.description}</p>
                            </button>
                        ))}
                    </div>
                </div>
            ) : (
                <div className="space-y-4">
                    {actions.map((action) => (
                        <div
                            key={action.id}
                            className="bg-white/5 border border-white/10 rounded-xl p-4 hover:bg-white/[0.07] transition-colors"
                        >
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${action.status === 'active'
                                            ? 'bg-emerald-500/20 text-emerald-400'
                                            : 'bg-slate-500/20 text-slate-400'
                                        }`}>
                                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                                        </svg>
                                    </div>
                                    <div>
                                        <h4 className="font-semibold text-white">{action.name}</h4>
                                        <p className="text-slate-400 text-sm">Trigger: {action.trigger}</p>
                                    </div>
                                </div>

                                <div className="flex items-center gap-4">
                                    <span className="text-slate-500 text-sm">{action.executions} runs</span>
                                    <button
                                        onClick={() => onToggleAction?.(action.id, action.status !== 'active')}
                                        className={`relative w-12 h-6 rounded-full transition-colors ${action.status === 'active' ? 'bg-emerald-500' : 'bg-slate-600'
                                            }`}
                                    >
                                        <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${action.status === 'active' ? 'left-7' : 'left-1'
                                            }`} />
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Create Modal */}
            {showCreateModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
                    <div className="bg-[#111117] border border-white/10 rounded-2xl p-6 w-full max-w-lg">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-bold text-white">Create Action</h2>
                            <button
                                onClick={() => setShowCreateModal(false)}
                                className="p-1 text-slate-400 hover:text-white transition-colors"
                            >
                                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">Action Name</label>
                                <input
                                    type="text"
                                    placeholder="e.g., Email follow-up"
                                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">Trigger Type</label>
                                <select className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all">
                                    {triggerTypes.map((t) => (
                                        <option key={t.id} value={t.id}>{t.label}</option>
                                    ))}
                                </select>
                            </div>

                            <p className="text-slate-500 text-sm">More configuration options coming soon...</p>
                        </div>

                        <div className="flex justify-end gap-3 mt-6">
                            <button
                                onClick={() => setShowCreateModal(false)}
                                className="px-4 py-2 text-sm font-medium text-slate-400 hover:text-white transition-colors"
                            >
                                Cancel
                            </button>
                            <button className="px-4 py-2 text-sm font-semibold text-white bg-gradient-to-r from-indigo-600 to-purple-600 rounded-lg">
                                Create Action
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default ActionsTab;
