'use client';

import React from 'react';

interface PublicChatTabProps {
    twinId: string;
    shareToken?: string | null;
    isPublic?: boolean;
}

export function PublicChatTab({ twinId, shareToken, isPublic }: PublicChatTabProps) {
    const sharePath = shareToken ? `/share/${twinId}/${shareToken}` : null;

    return (
        <div className="p-6 space-y-6">
            <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-white mb-2">Public Chat Preview</h3>
                {!isPublic || !sharePath ? (
                    <div className="text-sm text-slate-400">
                        Public sharing is disabled or no share link exists. Enable sharing in the Publish tab to preview the public chat.
                    </div>
                ) : (
                    <div className="space-y-3">
                        <div className="text-xs text-slate-400">Share link</div>
                        <div className="flex items-center gap-2">
                            <input
                                type="text"
                                readOnly
                                value={sharePath}
                                className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-xs text-slate-200"
                            />
                            <a
                                href={sharePath}
                                target="_blank"
                                className="px-3 py-2 text-[10px] uppercase tracking-wider font-bold bg-indigo-500 text-white rounded-lg"
                            >
                                Open
                            </a>
                        </div>
                    </div>
                )}
            </div>

            {isPublic && sharePath && (
                <div className="bg-black/30 border border-white/10 rounded-2xl overflow-hidden">
                    <iframe
                        src={sharePath}
                        title="Public chat preview"
                        className="w-full h-[70vh] bg-black"
                    />
                </div>
            )}
        </div>
    );
}

export default PublicChatTab;
