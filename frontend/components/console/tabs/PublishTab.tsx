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

interface VerificationStatus {
    is_ready: boolean;
    issues: string[];
    last_verified_at: string | null;
    last_verified_status: string;
    counts: {
        vectors: number;
        chunks: number;
        live_sources: number;
    };
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
    const [verificationStatus, setVerificationStatus] = useState<VerificationStatus | null>(null);
    const [loadingStatus, setLoadingStatus] = React.useState(true);

    React.useEffect(() => {
        const fetchStatus = async () => {
            try {
                const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
                const res = await fetch(`${backendUrl}/twins/${twinId}/verification-status`);
                const data = await res.json();
                setVerificationStatus(data);
            } catch (err) {
                console.error("Failed to fetch verification status", err);
            } finally {
                setLoadingStatus(false);
            }
        };
        fetchStatus();
    }, [twinId]);

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
            {/* Verification Status Card */}
            <div className={`border rounded-2xl p-6 transition-colors ${loadingStatus ? 'bg-white/5 border-white/10' :
                    verificationStatus?.is_ready
                        ? 'bg-gradient-to-br from-green-500/10 to-emerald-500/10 border-green-500/20'
                        : 'bg-gradient-to-br from-yellow-500/10 to-orange-500/10 border-yellow-500/20'
                }`}>
                <div className="flex items-center justify-between">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <h3 className="text-lg font-semibold text-white">Verification Status</h3>
                            {verificationStatus?.is_ready ? (
                                <span className="bg-green-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
                                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7" /></svg>
                                    VERIFIED
                                </span>
                            ) : (
                                <span className="bg-yellow-500 text-black text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
                                    VERIFICATION REQUIRED
                                </span>
                            )}
                        </div>
                        <p className="text-slate-300 text-sm">
                            {verificationStatus?.is_ready
                                ? "Your twin is ready for public access."
                                : "You must run 'Verify Retrieval' in the Simulator before publishing."}
                        </p>
                        {!verificationStatus?.is_ready && verificationStatus?.issues && (
                            <ul className="mt-2 text-xs text-yellow-200/80 list-disc list-inside">
                                {verificationStatus.issues.map((issue, i) => (
                                    <li key={i}>{issue}</li>
                                ))}
                            </ul>
                        )}
                    </div>
                </div>
            </div>

            {/* Sharing Toggle */}
            <div className={`bg-white/5 border border-white/10 rounded-2xl p-6 ${!verificationStatus?.is_ready && 'opacity-50 grayscale-[0.5]'}`}>
                <div className="flex items-center justify-between">
                    <div>
                        <h3 className="text-lg font-semibold text-white mb-1">Public Sharing</h3>
                        <p className="text-slate-400 text-sm">Allow anyone with the link to chat with your twin</p>
                    </div>
                    <div className="relative group">
                        <button
                            onClick={() => {
                                if (verificationStatus?.is_ready) {
                                    onTogglePublic?.(!isPublic);
                                }
                            }}
                            disabled={!verificationStatus?.is_ready}
                            className={`relative w-14 h-7 rounded-full transition-colors ${!verificationStatus?.is_ready
                                    ? 'bg-slate-700 cursor-not-allowed'
                                    : isPublic ? 'bg-emerald-500' : 'bg-slate-600'
                                }`}
                        >
                            <span className={`absolute top-1 w-5 h-5 bg-white rounded-full shadow transition-transform ${isPublic ? 'left-8' : 'left-1'
                                }`} />
                        </button>
                        {!verificationStatus?.is_ready && (
                            <div className="absolute bottom-full right-0 mb-2 w-48 px-3 py-2 bg-black/90 text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                                Capability locked. Please verify your twin first.
                            </div>
                        )}
                    </div>
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
