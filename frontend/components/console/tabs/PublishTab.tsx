'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';

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
    last_verified_at?: string | null;
    last_verified_status?: string;
    vectors_count?: number;
    graph_nodes?: number;
}

interface QualityTestResult {
    test_name: string;
    passed: boolean;
    has_answer: boolean;
    has_citations: boolean;
    confidence_score: number;
    answer_preview: string;
    issues: string[];
}

interface QualityVerificationResult {
    status: 'PASS' | 'FAIL';
    overall_score: number;
    tests_run: number;
    tests_passed: number;
    test_results: QualityTestResult[];
    issues: string[];
    verified_at: string;
}

export function PublishTab({
    twinId,
    twinName,
    isPublic = false,
    shareLink,
    onTogglePublic,
    onRegenerateLink
}: PublishTabProps) {
    const { get, post } = useAuthFetch();
    const [copied, setCopied] = useState(false);
    const [embedCopied, setEmbedCopied] = useState(false);
    const [verificationStatus, setVerificationStatus] = useState<VerificationStatus | null>(null);
    const [qualityResult, setQualityResult] = useState<QualityVerificationResult | null>(null);
    const [loadingStatus, setLoadingStatus] = useState(true);
    const [runningQualitySuite, setRunningQualitySuite] = useState(false);
    const [qualityError, setQualityError] = useState<string | null>(null);

    const fetchStatus = useCallback(async () => {
        setLoadingStatus(true);
        try {
            const res = await get(`/twins/${twinId}/verification-status`);
            if (!res.ok) {
                throw new Error(`Failed to fetch verification status (${res.status})`);
            }
            const data = await res.json();
            setVerificationStatus(data);
        } catch (err) {
            console.error('Failed to fetch verification status', err);
        } finally {
            setLoadingStatus(false);
        }
    }, [get, twinId]);

    useEffect(() => {
        void fetchStatus();
    }, [fetchStatus]);

    const runQualitySuite = useCallback(async () => {
        setRunningQualitySuite(true);
        setQualityError(null);
        try {
            const res = await post(`/verify/twins/${twinId}/quality-suite`);
            const data = await res.json();
            if (!res.ok) {
                throw new Error(data?.detail || `Quality verification failed (${res.status})`);
            }
            setQualityResult(data as QualityVerificationResult);
            await fetchStatus();
        } catch (err: any) {
            console.error('Failed to run quality suite', err);
            setQualityError(err?.message || 'Failed to run quality verification suite.');
        } finally {
            setRunningQualitySuite(false);
        }
    }, [fetchStatus, post, twinId]);

    const defaultShareLink = shareLink || '';
    const canShare = Boolean(defaultShareLink);

    const embedCode = canShare ? `<iframe 
  src="${defaultShareLink}/embed" 
  width="400" 
  height="600" 
  frameborder="0"
  style="border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);"
></iframe>` : '<!-- Enable sharing to generate embed code -->';

    const handleCopyLink = async () => {
        if (!canShare) return;
        await navigator.clipboard.writeText(defaultShareLink);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const handleCopyEmbed = async () => {
        if (!canShare) return;
        await navigator.clipboard.writeText(embedCode);
        setEmbedCopied(true);
        setTimeout(() => setEmbedCopied(false), 2000);
    };

    const qualityPass = qualityResult?.status === 'PASS';

    return (
        <div className="p-6 space-y-6 max-w-3xl">
            <div className={`border rounded-2xl p-6 transition-colors ${
                loadingStatus
                    ? 'bg-white/5 border-white/10'
                    : verificationStatus?.is_ready
                        ? 'bg-gradient-to-br from-green-500/10 to-emerald-500/10 border-green-500/20'
                        : 'bg-gradient-to-br from-yellow-500/10 to-orange-500/10 border-yellow-500/20'
            }`}>
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <h3 className="text-lg font-semibold text-white">Verification Status</h3>
                            {verificationStatus?.is_ready ? (
                                <span className="bg-green-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
                                    VERIFIED
                                </span>
                            ) : (
                                <span className="bg-yellow-500 text-black text-[10px] font-bold px-2 py-0.5 rounded-full">
                                    VERIFICATION REQUIRED
                                </span>
                            )}
                        </div>
                        <p className="text-slate-300 text-sm">
                            {verificationStatus?.is_ready
                                ? 'Your twin is ready for public access.'
                                : 'Run quality verification before publishing.'}
                        </p>
                        {verificationStatus && (
                            <div className="mt-2 text-xs text-slate-300">
                                Vectors: {verificationStatus.vectors_count ?? 0} | Graph nodes: {verificationStatus.graph_nodes ?? 0}
                            </div>
                        )}
                        {!verificationStatus?.is_ready && verificationStatus?.issues?.length ? (
                            <ul className="mt-2 text-xs text-yellow-200/80 list-disc list-inside">
                                {verificationStatus.issues.map((issue, i) => (
                                    <li key={i}>{issue}</li>
                                ))}
                            </ul>
                        ) : null}
                    </div>
                    <button
                        onClick={() => void runQualitySuite()}
                        disabled={runningQualitySuite}
                        className="px-4 py-2 text-xs font-bold rounded-xl bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-60"
                    >
                        {runningQualitySuite ? 'Running...' : 'Run Quality Suite'}
                    </button>
                </div>
                {qualityError ? (
                    <div className="mt-3 text-xs text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-lg px-3 py-2">
                        {qualityError}
                    </div>
                ) : null}
                {qualityResult ? (
                    <div className="mt-4 border-t border-white/10 pt-4 space-y-3">
                        <div className="flex items-center gap-2 text-sm">
                            <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${qualityPass ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'}`}>
                                {qualityResult.status}
                            </span>
                            <span className="text-slate-300">
                                {qualityResult.tests_passed}/{qualityResult.tests_run} tests passed
                            </span>
                            <span className="text-slate-400 text-xs">
                                ({(qualityResult.overall_score * 100).toFixed(0)}%)
                            </span>
                        </div>
                        <div className="space-y-2">
                            {qualityResult.test_results.map((test, idx) => (
                                <div key={idx} className="rounded-xl border border-white/10 bg-white/5 p-3">
                                    <div className="flex items-center justify-between gap-2">
                                        <div className="text-sm text-white font-medium">{test.test_name}</div>
                                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${test.passed ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'}`}>
                                            {test.passed ? 'PASS' : 'FAIL'}
                                        </span>
                                    </div>
                                    <div className="mt-1 text-xs text-slate-300">
                                        Confidence: {(test.confidence_score * 100).toFixed(0)}% | Citations: {test.has_citations ? 'Yes' : 'No'} | Answer: {test.has_answer ? 'Yes' : 'No'}
                                    </div>
                                    {!test.passed && test.issues?.length ? (
                                        <ul className="mt-1 text-xs text-rose-200 list-disc list-inside">
                                            {test.issues.map((issue, i) => (
                                                <li key={i}>{issue}</li>
                                            ))}
                                        </ul>
                                    ) : null}
                                </div>
                            ))}
                        </div>
                    </div>
                ) : null}
            </div>

            <div className={`bg-white/5 border border-white/10 rounded-2xl p-6 ${!verificationStatus?.is_ready && 'opacity-50 grayscale-[0.5]'}`}>
                <div className="flex items-center justify-between">
                    <div>
                        <h3 className="text-lg font-semibold text-white mb-1">Public Sharing</h3>
                        <p className="text-slate-400 text-sm">Allow anyone with the link to chat with your twin.</p>
                    </div>
                    <button
                        onClick={() => {
                            if (verificationStatus?.is_ready) {
                                onTogglePublic?.(!isPublic);
                            }
                        }}
                        disabled={!verificationStatus?.is_ready}
                        className={`relative w-14 h-7 rounded-full transition-colors ${
                            !verificationStatus?.is_ready ? 'bg-slate-700 cursor-not-allowed' : isPublic ? 'bg-emerald-500' : 'bg-slate-600'
                        }`}
                    >
                        <span className={`absolute top-1 w-5 h-5 bg-white rounded-full shadow transition-transform ${isPublic ? 'left-8' : 'left-1'}`} />
                    </button>
                </div>

                {isPublic ? (
                    <div className="mt-6 pt-6 border-t border-white/10">
                        <label className="block text-sm font-medium text-slate-300 mb-2">Share Link</label>
                        <div className="flex gap-2">
                            <input
                                type="text"
                                value={defaultShareLink || 'Share link not generated yet'}
                                readOnly
                                className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white text-sm"
                            />
                            <button
                                onClick={handleCopyLink}
                                disabled={!canShare}
                                className={`px-4 py-3 text-sm font-medium rounded-xl transition-colors ${
                                    copied ? 'bg-emerald-500/20 text-emerald-400' : 'bg-white/10 text-white hover:bg-white/15'
                                }`}
                            >
                                {copied ? 'Copied' : 'Copy'}
                            </button>
                        </div>
                        <button
                            onClick={onRegenerateLink}
                            className="mt-2 text-xs text-slate-500 hover:text-slate-300 transition-colors"
                        >
                            Regenerate link
                        </button>
                    </div>
                ) : null}
            </div>

            <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-white mb-1">Embed Widget</h3>
                <p className="text-slate-400 text-sm mb-4">Add a chat widget to your website.</p>

                <div className="relative">
                    <pre className="p-4 bg-slate-900 border border-white/10 rounded-xl text-xs text-slate-300 overflow-x-auto">
                        {embedCode}
                    </pre>
                    <button
                        onClick={handleCopyEmbed}
                        className={`absolute top-2 right-2 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                            embedCopied ? 'bg-emerald-500/20 text-emerald-400' : 'bg-white/10 text-white hover:bg-white/15'
                        }`}
                    >
                        {embedCopied ? 'Copied' : 'Copy'}
                    </button>
                </div>
            </div>

            <div className="bg-gradient-to-br from-indigo-500/10 to-purple-500/10 border border-indigo-500/20 rounded-2xl p-6">
                <div className="flex items-center gap-4">
                    <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xl font-bold">
                        {twinName.charAt(0)}
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold text-white">{twinName}</h3>
                        <p className="text-slate-400 text-sm">Preview your public twin page.</p>
                    </div>
                </div>
                <a
                    href={`/share/${twinId}`}
                    target="_blank"
                    className="mt-4 inline-flex items-center gap-2 text-sm text-indigo-400 hover:text-indigo-300"
                >
                    Preview public page
                </a>
            </div>
        </div>
    );
}

export default PublishTab;
