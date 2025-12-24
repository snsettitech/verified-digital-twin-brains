'use client';

import React, { useState } from 'react';

interface PublishTabProps {
    twinId: string;
    twinName: string;
    isPublic?: boolean;
    shareLink?: string;
    onTogglePublic?: (isPublic: boolean) => void;
    onRegenerateLink?: () => void;
}

export function PublishTab({
    twinId,
    twinName,
    isPublic = false,
    shareLink,
    onTogglePublic,
    onRegenerateLink
}: PublishTabProps) {
    const [copied, setCopied] = useState(false);
    const [embedCopied, setEmbedCopied] = useState(false);

    const defaultShareLink = shareLink || `${typeof window !== 'undefined' ? window.location.origin : ''}/share/${twinId}`;

    const embedCode = `<iframe 
  src="${defaultShareLink}/embed" 
  width="400" 
  height="600" 
  frameborder="0"
  style="border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);"
></iframe>`;

    const handleCopyLink = async () => {
        await navigator.clipboard.writeText(defaultShareLink);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const handleCopyEmbed = async () => {
        await navigator.clipboard.writeText(embedCode);
        setEmbedCopied(true);
        setTimeout(() => setEmbedCopied(false), 2000);
    };

    return (
        <div className="p-6 space-y-6 max-w-3xl">
            {/* Sharing Toggle */}
            <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h3 className="text-lg font-semibold text-white mb-1">Public Sharing</h3>
                        <p className="text-slate-400 text-sm">Allow anyone with the link to chat with your twin</p>
                    </div>
                    <button
                        onClick={() => onTogglePublic?.(!isPublic)}
                        className={`relative w-14 h-7 rounded-full transition-colors ${isPublic ? 'bg-emerald-500' : 'bg-slate-600'
                            }`}
                    >
                        <span className={`absolute top-1 w-5 h-5 bg-white rounded-full shadow transition-transform ${isPublic ? 'left-8' : 'left-1'
                            }`} />
                    </button>
                </div>

                {isPublic && (
                    <div className="mt-6 pt-6 border-t border-white/10">
                        <label className="block text-sm font-medium text-slate-300 mb-2">Share Link</label>
                        <div className="flex gap-2">
                            <input
                                type="text"
                                value={defaultShareLink}
                                readOnly
                                className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white text-sm"
                            />
                            <button
                                onClick={handleCopyLink}
                                className={`px-4 py-3 text-sm font-medium rounded-xl transition-colors ${copied
                                        ? 'bg-emerald-500/20 text-emerald-400'
                                        : 'bg-white/10 text-white hover:bg-white/15'
                                    }`}
                            >
                                {copied ? '✓ Copied' : 'Copy'}
                            </button>
                        </div>
                        <button
                            onClick={onRegenerateLink}
                            className="mt-2 text-xs text-slate-500 hover:text-slate-300 transition-colors"
                        >
                            Regenerate link
                        </button>
                    </div>
                )}
            </div>

            {/* Embed Code */}
            <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-white mb-1">Embed Widget</h3>
                <p className="text-slate-400 text-sm mb-4">Add a chat widget to your website</p>

                <div className="relative">
                    <pre className="p-4 bg-slate-900 border border-white/10 rounded-xl text-xs text-slate-300 overflow-x-auto">
                        {embedCode}
                    </pre>
                    <button
                        onClick={handleCopyEmbed}
                        className={`absolute top-2 right-2 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${embedCopied
                                ? 'bg-emerald-500/20 text-emerald-400'
                                : 'bg-white/10 text-white hover:bg-white/15'
                            }`}
                    >
                        {embedCopied ? '✓ Copied' : 'Copy'}
                    </button>
                </div>
            </div>

            {/* Integration Options */}
            <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Integrations</h3>

                <div className="grid grid-cols-2 gap-4">
                    {[
                        { name: 'Slack', icon: '💬', status: 'coming' },
                        { name: 'Discord', icon: '🎮', status: 'coming' },
                        { name: 'WhatsApp', icon: '📱', status: 'coming' },
                        { name: 'API Access', icon: '🔗', status: 'available' }
                    ].map((integration) => (
                        <div
                            key={integration.name}
                            className={`p-4 border rounded-xl ${integration.status === 'available'
                                    ? 'bg-white/5 border-white/10 hover:bg-white/10'
                                    : 'bg-white/[0.02] border-white/5'
                                } transition-colors`}
                        >
                            <div className="flex items-center gap-3">
                                <span className="text-2xl">{integration.icon}</span>
                                <div>
                                    <p className="font-medium text-white">{integration.name}</p>
                                    <p className="text-xs text-slate-500">
                                        {integration.status === 'available' ? 'Available' : 'Coming soon'}
                                    </p>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Preview */}
            <div className="bg-gradient-to-br from-indigo-500/10 to-purple-500/10 border border-indigo-500/20 rounded-2xl p-6">
                <div className="flex items-center gap-4">
                    <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xl font-bold">
                        {twinName.charAt(0)}
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold text-white">{twinName}</h3>
                        <p className="text-slate-400 text-sm">Your digital twin is ready to share</p>
                    </div>
                </div>
                <a
                    href={`/share/${twinId}`}
                    target="_blank"
                    className="mt-4 inline-flex items-center gap-2 text-sm text-indigo-400 hover:text-indigo-300"
                >
                    Preview public page
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                </a>
            </div>
        </div>
    );
}

export default PublishTab;
