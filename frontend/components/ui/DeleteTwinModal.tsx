'use client';

import React, { useState } from 'react';

interface DeleteTwinModalProps {
    isOpen: boolean;
    onClose: () => void;
    onDelete: (permanent: boolean) => Promise<void>;
    twinName: string;
    twinHandle?: string;
    twinId: string;
}

export default function DeleteTwinModal({
    isOpen,
    onClose,
    onDelete,
    twinName,
    twinHandle,
    twinId
}: DeleteTwinModalProps) {
    const [step, setStep] = useState<'choose' | 'confirm'>('choose');
    const [deleteType, setDeleteType] = useState<'archive' | 'permanent'>('archive');
    const [confirmText, setConfirmText] = useState('');
    const [isDeleting, setIsDeleting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Reset state when modal opens/closes
    React.useEffect(() => {
        if (isOpen) {
            setStep('choose');
            setDeleteType('archive');
            setConfirmText('');
            setError(null);
        }
    }, [isOpen]);

    if (!isOpen) return null;

    const handleProceed = () => {
        setStep('confirm');
        setConfirmText('');
        setError(null);
    };

    const handleBack = () => {
        setStep('choose');
        setError(null);
    };

    const handleDelete = async () => {
        const normalized = confirmText.trim();
        const nameMatch = normalized === twinName;
        const handleMatch = twinHandle ? normalized === twinHandle : false;
        if (!nameMatch && !handleMatch) {
            setError('Confirmation does not match twin name or handle');
            return;
        }

        setIsDeleting(true);
        setError(null);

        try {
            await onDelete(deleteType === 'permanent');
            onClose();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to delete twin');
        } finally {
            setIsDeleting(false);
        }
    };

    const isConfirmValid = confirmText.trim() === twinName || (twinHandle ? confirmText.trim() === twinHandle : false);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/50 backdrop-blur-sm"
                onClick={onClose}
            />

            {/* Modal */}
            <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
                {/* Header */}
                <div className="px-6 py-4 border-b border-slate-200 bg-slate-50">
                    <div className="flex items-center justify-between">
                        <h2 className="text-lg font-bold text-slate-900">
                            {step === 'choose' ? 'Delete Twin' : 'Confirm Deletion'}
                        </h2>
                        <button
                            onClick={onClose}
                            className="p-2 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="p-6">
                    {step === 'choose' ? (
                        <>
                            {/* Warning */}
                            <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl">
                                <div className="flex gap-3">
                                    <span className="text-2xl">⚠️</span>
                                    <div>
                                        <p className="font-semibold text-amber-800">You are about to delete "{twinName}"</p>
                                        <p className="text-sm text-amber-700 mt-1">This will affect all knowledge, conversations, and API integrations.</p>
                                    </div>
                                </div>
                            </div>

                            {/* Options */}
                            <div className="space-y-3">
                                <button
                                    onClick={() => setDeleteType('archive')}
                                    className={`w-full p-4 rounded-xl border-2 text-left transition-all ${deleteType === 'archive'
                                            ? 'border-indigo-500 bg-indigo-50'
                                            : 'border-slate-200 hover:border-slate-300'
                                        }`}
                                >
                                    <div className="flex items-start gap-3">
                                        <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${deleteType === 'archive' ? 'border-indigo-500 bg-indigo-500' : 'border-slate-300'
                                            }`}>
                                            {deleteType === 'archive' && (
                                                <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                                                    <path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" />
                                                </svg>
                                            )}
                                        </div>
                                        <div>
                                            <p className="font-semibold text-slate-900">Archive (Recommended)</p>
                                            <p className="text-sm text-slate-500 mt-1">
                                                Hide the twin and disable access. Data is preserved and can be recovered.
                                            </p>
                                        </div>
                                    </div>
                                </button>

                                <button
                                    onClick={() => setDeleteType('permanent')}
                                    className={`w-full p-4 rounded-xl border-2 text-left transition-all ${deleteType === 'permanent'
                                            ? 'border-red-500 bg-red-50'
                                            : 'border-slate-200 hover:border-slate-300'
                                        }`}
                                >
                                    <div className="flex items-start gap-3">
                                        <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${deleteType === 'permanent' ? 'border-red-500 bg-red-500' : 'border-slate-300'
                                            }`}>
                                            {deleteType === 'permanent' && (
                                                <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                                                    <path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" />
                                                </svg>
                                            )}
                                        </div>
                                        <div>
                                            <p className="font-semibold text-slate-900">Permanent Delete</p>
                                            <p className="text-sm text-slate-500 mt-1">
                                                Permanently delete all data including knowledge, graphs, and API keys. <span className="text-red-600 font-medium">Cannot be undone.</span>
                                            </p>
                                        </div>
                                    </div>
                                </button>
                            </div>

                            {/* What will be affected */}
                            <div className="mt-6 p-4 bg-slate-50 rounded-xl">
                                <p className="font-medium text-slate-700 mb-2">What will be affected:</p>
                                <ul className="text-sm text-slate-600 space-y-1">
                                    <li className="flex items-center gap-2">
                                        <span>📚</span> All knowledge sources and embeddings
                                    </li>
                                    <li className="flex items-center gap-2">
                                        <span>💬</span> Conversation history
                                    </li>
                                    <li className="flex items-center gap-2">
                                        <span>🔑</span> API keys and integrations
                                    </li>
                                    <li className="flex items-center gap-2">
                                        <span>🌐</span> Published share links
                                    </li>
                                </ul>
                            </div>
                        </>
                    ) : (
                        <>
                            {/* Confirm step */}
                            <div className={`mb-6 p-4 rounded-xl ${deleteType === 'permanent'
                                    ? 'bg-red-50 border border-red-200'
                                    : 'bg-amber-50 border border-amber-200'
                                }`}>
                                <p className={`font-semibold ${deleteType === 'permanent' ? 'text-red-800' : 'text-amber-800'
                                    }`}>
                                    {deleteType === 'permanent'
                                        ? '⚠️ This action is irreversible!'
                                        : '📦 You are archiving this twin'
                                    }
                                </p>
                                <p className={`text-sm mt-1 ${deleteType === 'permanent' ? 'text-red-700' : 'text-amber-700'
                                    }`}>
                                    {deleteType === 'permanent'
                                        ? 'All data will be permanently deleted and cannot be recovered.'
                                        : 'The twin will be hidden but data will be preserved.'
                                    }
                                </p>
                            </div>

                            {/* Confirmation input */}
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-2">
                                    Type <span className="font-bold text-slate-900">"{twinName}"</span>
                                    {twinHandle ? <span> or <span className="font-bold text-slate-900">"{twinHandle}"</span></span> : null}
                                    {" "}to confirm:
                                </label>
                                <input
                                    type="text"
                                    value={confirmText}
                                    onChange={(e) => setConfirmText(e.target.value)}
                                    placeholder={twinHandle ? `${twinName} or ${twinHandle}` : twinName}
                                    className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
                                    autoFocus
                                />
                            </div>

                            {error && (
                                <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                                    {error}
                                </div>
                            )}
                        </>
                    )}
                </div>

                {/* Footer */}
                <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex justify-between">
                    {step === 'confirm' && (
                        <button
                            onClick={handleBack}
                            className="px-4 py-2 text-slate-600 font-medium rounded-lg hover:bg-slate-200 transition-colors"
                        >
                            ← Back
                        </button>
                    )}
                    <div className={`flex gap-3 ${step === 'choose' ? 'w-full justify-end' : 'ml-auto'}`}>
                        <button
                            onClick={onClose}
                            className="px-4 py-2 text-slate-600 font-medium rounded-lg hover:bg-slate-200 transition-colors"
                        >
                            Cancel
                        </button>
                        {step === 'choose' ? (
                            <button
                                onClick={handleProceed}
                                className={`px-6 py-2 font-semibold rounded-xl transition-colors ${deleteType === 'permanent'
                                        ? 'bg-red-500 text-white hover:bg-red-600'
                                        : 'bg-amber-500 text-white hover:bg-amber-600'
                                    }`}
                            >
                                Continue
                            </button>
                        ) : (
                            <button
                                onClick={handleDelete}
                                disabled={!isConfirmValid || isDeleting}
                                className={`px-6 py-2 font-semibold rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${deleteType === 'permanent'
                                        ? 'bg-red-500 text-white hover:bg-red-600'
                                        : 'bg-amber-500 text-white hover:bg-amber-600'
                                    }`}
                            >
                                {isDeleting ? 'Deleting...' : deleteType === 'permanent' ? 'Delete Forever' : 'Archive'}
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
