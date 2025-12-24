'use client';

import React, { useState } from 'react';

interface TwinSettings {
    name: string;
    systemInstructions: string;
    responseStyle: 'concise' | 'detailed' | 'balanced';
    temperature: number;
    escalationThreshold: number;
}

interface SettingsTabProps {
    twinId: string;
    settings?: Partial<TwinSettings>;
    onSave?: (settings: Partial<TwinSettings>) => void;
    onDelete?: () => void;
}

export function SettingsTab({ twinId, settings, onSave, onDelete }: SettingsTabProps) {
    const [form, setForm] = useState<Partial<TwinSettings>>({
        name: settings?.name || '',
        systemInstructions: settings?.systemInstructions || '',
        responseStyle: settings?.responseStyle || 'balanced',
        temperature: settings?.temperature ?? 0.7,
        escalationThreshold: settings?.escalationThreshold ?? 0.6,
    });
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const [isSaving, setIsSaving] = useState(false);

    const handleSave = async () => {
        setIsSaving(true);
        try {
            await onSave?.(form);
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <div className="p-6 space-y-6 max-w-2xl">
            {/* Basic Settings */}
            <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-white mb-4">General Settings</h3>

                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">Twin Name</label>
                        <input
                            type="text"
                            value={form.name}
                            onChange={(e) => setForm({ ...form, name: e.target.value })}
                            className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">System Instructions</label>
                        <textarea
                            value={form.systemInstructions}
                            onChange={(e) => setForm({ ...form, systemInstructions: e.target.value })}
                            rows={4}
                            placeholder="Define how your twin should behave, what tone to use, and any specific rules..."
                            className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all resize-none"
                        />
                        <p className="text-xs text-slate-500 mt-1">These instructions guide how your twin responds to questions.</p>
                    </div>
                </div>
            </div>

            {/* Response Settings */}
            <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Response Settings</h3>

                <div className="space-y-6">
                    <div>
                        <label className="block text-sm font-medium text-slate-300 mb-3">Response Style</label>
                        <div className="grid grid-cols-3 gap-3">
                            {(['concise', 'balanced', 'detailed'] as const).map((style) => (
                                <button
                                    key={style}
                                    onClick={() => setForm({ ...form, responseStyle: style })}
                                    className={`p-4 rounded-xl border text-center transition-all ${form.responseStyle === style
                                            ? 'bg-indigo-500/20 border-indigo-500 text-white'
                                            : 'bg-white/5 border-white/10 text-slate-400 hover:bg-white/10'
                                        }`}
                                >
                                    <span className="text-xl mb-1 block">
                                        {style === 'concise' ? '⚡' : style === 'balanced' ? '⚖️' : '📚'}
                                    </span>
                                    <span className="text-sm font-medium capitalize">{style}</span>
                                </button>
                            ))}
                        </div>
                    </div>

                    <div>
                        <div className="flex items-center justify-between mb-2">
                            <label className="text-sm font-medium text-slate-300">Creativity</label>
                            <span className="text-sm text-slate-400">{Math.round((form.temperature || 0.7) * 100)}%</span>
                        </div>
                        <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.1"
                            value={form.temperature}
                            onChange={(e) => setForm({ ...form, temperature: parseFloat(e.target.value) })}
                            className="w-full h-2 bg-white/10 rounded-full appearance-none cursor-pointer accent-indigo-500"
                        />
                        <div className="flex justify-between text-xs text-slate-500 mt-1">
                            <span>More focused</span>
                            <span>More creative</span>
                        </div>
                    </div>

                    <div>
                        <div className="flex items-center justify-between mb-2">
                            <label className="text-sm font-medium text-slate-300">Escalation Threshold</label>
                            <span className="text-sm text-slate-400">{Math.round((form.escalationThreshold || 0.6) * 100)}%</span>
                        </div>
                        <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.1"
                            value={form.escalationThreshold}
                            onChange={(e) => setForm({ ...form, escalationThreshold: parseFloat(e.target.value) })}
                            className="w-full h-2 bg-white/10 rounded-full appearance-none cursor-pointer accent-amber-500"
                        />
                        <div className="flex justify-between text-xs text-slate-500 mt-1">
                            <span>Escalate more</span>
                            <span>Answer more</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Save Button */}
            <div className="flex justify-end">
                <button
                    onClick={handleSave}
                    disabled={isSaving}
                    className="px-6 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 rounded-xl shadow-lg shadow-indigo-500/20 transition-all disabled:opacity-50"
                >
                    {isSaving ? 'Saving...' : 'Save Changes'}
                </button>
            </div>

            {/* Danger Zone */}
            <div className="bg-red-500/10 border border-red-500/20 rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-red-400 mb-2">Danger Zone</h3>
                <p className="text-slate-400 text-sm mb-4">Once you delete a twin, there is no going back. Please be certain.</p>
                <button
                    onClick={() => setShowDeleteConfirm(true)}
                    className="px-4 py-2 text-sm font-medium text-red-400 hover:text-white bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-lg transition-colors"
                >
                    Delete Twin
                </button>
            </div>

            {/* Delete Confirmation Modal */}
            {showDeleteConfirm && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
                    <div className="bg-[#111117] border border-white/10 rounded-2xl p-6 w-full max-w-md">
                        <div className="text-center mb-6">
                            <div className="w-16 h-16 mx-auto mb-4 bg-red-500/20 rounded-full flex items-center justify-center">
                                <svg className="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                </svg>
                            </div>
                            <h2 className="text-xl font-bold text-white mb-2">Delete Twin?</h2>
                            <p className="text-slate-400 text-sm">
                                This will permanently delete your twin and all associated data. This action cannot be undone.
                            </p>
                        </div>

                        <div className="flex gap-3">
                            <button
                                onClick={() => setShowDeleteConfirm(false)}
                                className="flex-1 py-2.5 text-sm font-medium text-slate-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-xl transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={() => { onDelete?.(); setShowDeleteConfirm(false); }}
                                className="flex-1 py-2.5 text-sm font-semibold text-white bg-red-500 hover:bg-red-600 rounded-xl transition-colors"
                            >
                                Delete Forever
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default SettingsTab;
