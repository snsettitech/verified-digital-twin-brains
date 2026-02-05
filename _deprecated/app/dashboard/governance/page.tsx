'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
    Card, CardHeader, CardContent,
    Badge, Modal, Toggle,
    VerificationBadge, useToast
} from '@/components/ui';
import { useTwin } from '@/lib/context/TwinContext';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';

interface AuditLog {
    id: string;
    event_type: string;
    action: string;
    actor_id?: string;
    metadata: any;
    created_at: string;
}

interface Policy {
    id: string;
    policy_type: 'refusal_rule' | 'guardrail' | 'tool_restriction';
    name: string;
    content: string;
    is_active: boolean;
}

interface Source {
    id: string;
    filename: string;
    status: string;
}

export default function GovernancePage() {
    const { showToast } = useToast();
    const { activeTwin, isLoading: twinLoading } = useTwin();
    const { get, getTenant, postTenant, getTwin, postTwin, delTwin } = useAuthFetch();
    const [logs, setLogs] = useState<AuditLog[]>([]);
    const [policies, setPolicies] = useState<Policy[]>([]);
    const [sources, setSources] = useState<Source[]>([]);
    const [vStatus, setVStatus] = useState<'unverified' | 'pending' | 'verified' | 'rejected'>('unverified');
    const [loading, setLoading] = useState(true);
    const [showPolicyModal, setShowPolicyModal] = useState(false);
    const [showVerifyModal, setShowVerifyModal] = useState(false);
    const [newPolicy, setNewPolicy] = useState({ name: '', type: 'refusal_rule', content: '' });
    const [selectedSourceId, setSelectedSourceId] = useState('');

    // CORRECTION 4: Deep scrub safety states
    const [deepScrubInProgress, setDeepScrubInProgress] = useState(false);
    const [deepScrubConfirmText, setDeepScrubConfirmText] = useState('');
    const [verifyInProgress, setVerifyInProgress] = useState(false);

    // Guardrail toggle states
    const [promptShieldEnabled, setPromptShieldEnabled] = useState(true);
    const [consentLayerEnabled, setConsentLayerEnabled] = useState(true);

    const twinId = activeTwin?.id;

    const fetchData = useCallback(async () => {
        try {
            // Mock empty response for when twinId is not available
            const emptyResponse = { ok: false, json: async () => null } as Response;

            // Parallel fetch: tenant-scoped for policies/logs, twin-scoped for twin/sources
            const [logsRes, policiesRes, twinRes, sourcesRes] = await Promise.all([
                // TENANT-SCOPED: Audit logs are tenant-wide (optionally filter by twin_id)
                getTenant(twinId ? `/governance/audit-logs?twin_id=${twinId}` : '/governance/audit-logs'),
                // TENANT-SCOPED: Policies are tenant-wide
                getTenant('/governance/policies'),
                // TWIN-SCOPED: Get twin status
                twinId ? getTwin(twinId, `/twins/{twinId}`) : emptyResponse,
                // TWIN-SCOPED: Sources belong to a specific twin
                twinId ? getTwin(twinId, `/twins/{twinId}/sources`) : emptyResponse
            ]);

            if (logsRes.ok) setLogs(await logsRes.json());
            if (policiesRes.ok) setPolicies(await policiesRes.json());
            if (twinRes.ok) {
                const twinData = await twinRes.json();
                setVStatus(twinData.verification_status || 'unverified');
            }
            if (sourcesRes.ok) setSources(await sourcesRes.json());
        } catch (err) {
            console.error('Fetch error:', err);
        } finally {
            setLoading(false);
        }
    }, [twinId, getTenant, getTwin]);

    useEffect(() => {
        // Fetch tenant-scoped data immediately, some fetches need twinId for context
        if (!twinLoading) {
            fetchData();
        }
    }, [twinId, twinLoading, fetchData]);

    const handleRequestVerification = async () => {
        if (!twinId || verifyInProgress) return;

        setVerifyInProgress(true);
        console.log('[GOVERNANCE] Verify request initiated:', { twinId, action: 'request_verification' });

        try {
            // TWIN-SCOPED: Verification is per-twin
            // Endpoint: POST /twins/{twinId}/governance/verify
            const res = await postTwin(twinId, `/twins/{twinId}/governance/verify`, { verification_method: 'MANUAL_REVIEW' });

            if (res.ok) {
                setVStatus('pending');
                setShowVerifyModal(false);
                showToast('Verification request submitted! Our team will review within 48 hours.', 'success');
            } else if (res.status === 409) {
                showToast('Verification request already pending', 'warning');
            } else if (res.status === 429) {
                showToast('Too many requests. Please try again later.', 'error');
            } else {
                const data = await res.json().catch(() => ({}));
                showToast(data.detail || 'Failed to submit request', 'error');
            }
        } catch (err) {
            console.error('[GOVERNANCE] Verify request failed:', err);
            showToast('Failed to submit request', 'error');
        } finally {
            setVerifyInProgress(false);
        }
    };

    const handleCreatePolicy = async () => {
        try {
            // TENANT-SCOPED: Policies are tenant-wide
            const res = await postTenant('/governance/policies', {
                policy_type: newPolicy.type,
                name: newPolicy.name,
                content: newPolicy.content
            });
            if (res.ok) {
                setShowPolicyModal(false);
                setNewPolicy({ name: '', type: 'refusal_rule', content: '' });
                fetchData();
                showToast('Policy created successfully', 'success');
            }
        } catch (err) {
            showToast('Failed to create policy', 'error');
        }
    };

    const handleDeepScrub = async () => {
        if (!selectedSourceId || !twinId || deepScrubInProgress) return;

        // SAFETY: Require typing "DELETE" to confirm
        if (deepScrubConfirmText !== 'DELETE') {
            showToast('You must type DELETE to confirm', 'error');
            return;
        }

        const source = sources.find(s => s.id === selectedSourceId);
        console.log('[GOVERNANCE] Deep scrub initiated:', { twinId, sourceId: selectedSourceId, filename: source?.filename });

        setDeepScrubInProgress(true);
        try {
            // TWIN-SCOPED: Sources belong to a specific twin
            // Endpoint: DELETE /twins/{twinId}/sources/{sourceId}/deep-scrub
            const res = await delTwin(twinId, `/twins/{twinId}/sources/${selectedSourceId}/deep-scrub`);

            if (res.ok) {
                showToast('Deep scrub completed successfully', 'success');
                setSelectedSourceId('');
                setDeepScrubConfirmText('');
                fetchData();
            } else if (res.status === 409) {
                showToast('Source is currently being processed. Try again later.', 'warning');
            } else if (res.status === 429) {
                showToast('Too many requests. Please wait before trying again.', 'error');
            } else {
                const data = await res.json().catch(() => ({}));
                showToast(data.detail || 'Deep scrub failed', 'error');
            }
        } catch (err) {
            console.error('[GOVERNANCE] Deep scrub failed:', err);
            showToast('Connection error', 'error');
        } finally {
            setDeepScrubInProgress(false);
        }
    };

    const handleGuardrailToggle = (type: 'prompt' | 'consent', value: boolean) => {
        if (type === 'prompt') {
            setPromptShieldEnabled(value);
            showToast(value ? 'Prompt Injection Shield enabled' : 'Prompt Injection Shield disabled', value ? 'success' : 'warning');
        } else {
            setConsentLayerEnabled(value);
            showToast(value ? 'Consent Layer enabled' : 'Consent Layer disabled', value ? 'success' : 'warning');
        }
    };

    if (twinLoading) {
        return (
            <div className="flex justify-center p-20">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600"></div>
            </div>
        );
    }

    if (!twinId) {
        return (
            <div className="flex items-center justify-center h-96">
                <div className="text-center max-w-md p-8">
                    <div className="w-16 h-16 bg-indigo-900/50 rounded-2xl flex items-center justify-center mx-auto mb-6">
                        <svg className="w-8 h-8 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                        </svg>
                    </div>
                    <h2 className="text-2xl font-bold text-white mb-3">No Twin Found</h2>
                    <p className="text-slate-400 mb-6">Create a digital twin first to access governance features.</p>
                    <a href="/dashboard/right-brain" className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition-colors">
                        Create Your Twin
                    </a>
                </div>
            </div>
        );
    }

    return (
        <div className="max-w-6xl mx-auto space-y-8 pb-20">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-4xl font-black tracking-tight text-white mb-2">Governance Portal</h1>
                    <p className="text-slate-400 font-medium">Manage trust, safety, and operational transparency.</p>
                </div>
                <div className="flex items-center gap-4">
                    <VerificationBadge status={vStatus} />
                    {vStatus === 'unverified' && (
                        <button
                            onClick={() => setShowVerifyModal(true)}
                            className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-black transition-all shadow-lg shadow-indigo-500/20"
                        >
                            Verify Identity
                        </button>
                    )}
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Verification Card */}
                <Card glass className="lg:col-span-1">
                    <CardHeader>
                        <h3 className="text-lg font-black text-white">Trust Posture</h3>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div className="p-4 bg-slate-800/50 rounded-2xl border border-slate-700/50">
                            <div className="flex items-center gap-3 mb-3">
                                <div className={`w-3 h-3 rounded-full ${vStatus === 'verified' ? 'bg-emerald-500 animate-pulse' : vStatus === 'pending' ? 'bg-amber-500 animate-pulse' : 'bg-slate-600'}`}></div>
                                <span className="text-xs font-black text-slate-300 uppercase tracking-widest">Verification Status</span>
                            </div>
                            <p className="text-sm text-slate-400 font-medium leading-relaxed">
                                {vStatus === 'verified'
                                    ? 'Your twin is officially verified. Responses will display the trust badge.'
                                    : vStatus === 'pending'
                                        ? 'Verification is currently under review by our governance team. You will be notified within 48 hours.'
                                        : 'Verify your persona to unlock premium distribution channels and trust badges.'}
                            </p>
                        </div>

                        <div className="space-y-4">
                            <h4 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Safety Guardrails</h4>
                            <div className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/10">
                                <div>
                                    <span className="text-sm font-bold text-slate-300">Prompt Injection Shield</span>
                                    <p className="text-[10px] text-slate-500 mt-0.5">Blocks malicious prompt manipulation</p>
                                </div>
                                <Toggle checked={promptShieldEnabled} label="" onChange={(v) => handleGuardrailToggle('prompt', v)} />
                            </div>
                            <div className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/10">
                                <div>
                                    <span className="text-sm font-bold text-slate-300">Implicit Consent Layer</span>
                                    <p className="text-[10px] text-slate-500 mt-0.5">Respects user data permissions</p>
                                </div>
                                <Toggle checked={consentLayerEnabled} label="" onChange={(v) => handleGuardrailToggle('consent', v)} />
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Audit Log Card */}
                <Card glass className="lg:col-span-2">
                    <CardHeader className="flex flex-row items-center justify-between border-b border-white/5">
                        <h3 className="text-lg font-black text-white">Immutable Audit Trail</h3>
                        <button onClick={fetchData} className="text-slate-500 hover:text-white transition-colors">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                        </button>
                    </CardHeader>
                    <CardContent className="p-0">
                        <div className="max-h-[400px] overflow-y-auto">
                            <table className="w-full text-left">
                                <thead className="sticky top-0 bg-slate-900 z-10">
                                    <tr className="border-b border-white/5">
                                        <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Event</th>
                                        <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Action</th>
                                        <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Time</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-white/5">
                                    {logs.length === 0 ? (
                                        <tr>
                                            <td colSpan={3} className="px-6 py-20 text-center text-slate-500 font-medium">No audit events recorded yet.</td>
                                        </tr>
                                    ) : logs.map((log) => (
                                        <tr key={log.id} className="hover:bg-white/5 transition-colors group">
                                            <td className="px-6 py-4">
                                                <span className="px-2 py-0.5 bg-indigo-500/10 text-indigo-400 text-[10px] font-black rounded-lg border border-indigo-500/20">
                                                    {log.event_type}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4">
                                                <div className="text-xs font-bold text-slate-300">{log.action}</div>
                                                {log.metadata && Object.keys(log.metadata).length > 0 && (
                                                    <div className="text-[10px] text-slate-500 mt-0.5 truncate max-w-[200px]">
                                                        {JSON.stringify(log.metadata)}
                                                    </div>
                                                )}
                                            </td>
                                            <td className="px-6 py-4 text-[10px] font-bold text-slate-500">
                                                {new Date(log.created_at).toLocaleString()}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </CardContent>
                </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Safety Policies */}
                <Card glass>
                    <CardHeader className="flex flex-row items-center justify-between">
                        <h3 className="text-lg font-black text-white">Refusal Rules</h3>
                        <button
                            onClick={() => setShowPolicyModal(true)}
                            className="p-2 bg-white/5 hover:bg-white/10 rounded-xl text-white transition-all"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4"></path></svg>
                        </button>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {policies.length === 0 ? (
                            <div className="p-10 text-center border-2 border-dashed border-white/5 rounded-3xl">
                                <p className="text-slate-500 text-sm font-medium">No custom refusal rules defined.</p>
                            </div>
                        ) : policies.map((policy) => (
                            <div key={policy.id} className="p-4 bg-slate-800/50 rounded-2xl border border-slate-700/50 flex items-center justify-between">
                                <div>
                                    <div className="font-bold text-white text-sm">{policy.name}</div>
                                    <div className="text-xs text-slate-500 mt-1">Refusal Pattern: {policy.content}</div>
                                </div>
                                <Toggle checked={policy.is_active} label="" onChange={() => { }} />
                            </div>
                        ))}
                    </CardContent>
                </Card>

                {/* Data Purge / Deep Scrub */}
                <Card glass className="border-red-500/20 shadow-rose-900/10">
                    <CardHeader>
                        <h3 className="text-lg font-black text-rose-500">Deep Scrub Purge</h3>
                    </CardHeader>
                    <CardContent>
                        <p className="text-xs text-slate-400 mb-6 leading-relaxed">
                            Permanently purge a source from both the database and the vector index.
                            This action is <span className="text-rose-500 font-bold uppercase">irreversible</span>.
                        </p>
                        <div className="space-y-4">
                            <select
                                value={selectedSourceId}
                                onChange={(e) => setSelectedSourceId(e.target.value)}
                                className="w-full px-5 py-3.5 bg-slate-950 border border-white/5 rounded-2xl text-sm font-medium text-white outline-none focus:ring-2 focus:ring-rose-500 transition-all appearance-none cursor-pointer"
                            >
                                <option value="" className="bg-slate-900">Select a source to delete...</option>
                                {sources.map((source) => (
                                    <option key={source.id} value={source.id} className="bg-slate-900">
                                        {source.filename} ({source.status})
                                    </option>
                                ))}
                            </select>
                            {selectedSourceId && (
                                <div className="p-4 bg-rose-950/30 border border-rose-500/20 rounded-2xl">
                                    <p className="text-xs text-rose-400 font-bold">⚠️ Danger Zone</p>
                                    <p className="text-xs text-rose-300/70 mt-1">
                                        This will permanently delete the selected file and all associated vector embeddings.
                                        The data cannot be recovered after deletion.
                                    </p>
                                    <p className="text-xs text-rose-300 font-bold mt-3">
                                        Type <span className="font-mono bg-rose-950 px-1 rounded">DELETE</span> to confirm:
                                    </p>
                                    <input
                                        type="text"
                                        value={deepScrubConfirmText}
                                        onChange={(e) => setDeepScrubConfirmText(e.target.value.toUpperCase())}
                                        placeholder="DELETE"
                                        className="mt-2 w-full px-4 py-2 bg-slate-900 border border-rose-500/30 rounded-xl text-rose-400 text-sm font-mono outline-none focus:ring-2 focus:ring-rose-500 transition-all"
                                        disabled={deepScrubInProgress}
                                    />
                                </div>
                            )}
                            <button
                                onClick={handleDeepScrub}
                                disabled={!selectedSourceId || deepScrubConfirmText !== 'DELETE' || deepScrubInProgress}
                                className="w-full px-6 py-3.5 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-2xl text-xs font-black transition-all shadow-lg shadow-rose-900/20"
                            >
                                {deepScrubInProgress ? (
                                    <>
                                        <span className="animate-pulse">🗑️ DELETING...</span>
                                    </>
                                ) : (
                                    '🗑️ PERMANENTLY DELETE SELECTED SOURCE'
                                )}
                            </button>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* New Policy Modal */}
            <Modal
                isOpen={showPolicyModal}
                onClose={() => setShowPolicyModal(false)}
                title="Add Refusal Rule"
            >
                <div className="space-y-6 pt-4">
                    <div>
                        <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-3">Rule Name</label>
                        <input
                            type="text"
                            placeholder="e.g., Medical Advice Refusal"
                            value={newPolicy.name}
                            onChange={(e) => setNewPolicy({ ...newPolicy, name: e.target.value })}
                            className="w-full px-5 py-3.5 bg-slate-900 border border-slate-800 rounded-2xl text-white text-sm font-medium outline-none focus:ring-2 focus:ring-indigo-500 transition-all"
                        />
                    </div>
                    <div>
                        <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-3">Refusal Keyword/Pattern</label>
                        <input
                            type="text"
                            placeholder="e.g., prescription|diagnosis|medical"
                            value={newPolicy.content}
                            onChange={(e) => setNewPolicy({ ...newPolicy, content: e.target.value })}
                            className="w-full px-5 py-3.5 bg-slate-900 border border-slate-800 rounded-2xl text-white text-sm font-medium outline-none focus:ring-2 focus:ring-indigo-500 transition-all"
                        />
                    </div>
                    <button
                        onClick={handleCreatePolicy}
                        className="w-full py-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-2xl text-sm font-black transition-all shadow-lg shadow-indigo-500/20"
                    >
                        Create Rule
                    </button>
                </div>
            </Modal>

            {/* Verification Modal */}
            <Modal
                isOpen={showVerifyModal}
                onClose={() => setShowVerifyModal(false)}
                title="Identity Verification"
            >
                <div className="space-y-6 pt-4">
                    <div className="p-4 bg-indigo-950/30 border border-indigo-500/20 rounded-2xl">
                        <h4 className="text-sm font-bold text-indigo-300 mb-2">What is Identity Verification?</h4>
                        <p className="text-xs text-slate-400 leading-relaxed">
                            Verification confirms that this Digital Twin authentically represents you.
                            Once verified, your twin will display a trust badge on all responses,
                            increasing credibility with users who interact with it.
                        </p>
                    </div>

                    <div className="space-y-3">
                        <h4 className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Verification Process</h4>
                        <div className="flex items-start gap-3 p-3 bg-white/5 rounded-xl">
                            <div className="w-6 h-6 rounded-full bg-indigo-500/20 flex items-center justify-center text-indigo-400 text-xs font-black">1</div>
                            <div>
                                <p className="text-sm font-bold text-slate-300">Submit Request</p>
                                <p className="text-xs text-slate-500">Click the button below to start the process</p>
                            </div>
                        </div>
                        <div className="flex items-start gap-3 p-3 bg-white/5 rounded-xl">
                            <div className="w-6 h-6 rounded-full bg-indigo-500/20 flex items-center justify-center text-indigo-400 text-xs font-black">2</div>
                            <div>
                                <p className="text-sm font-bold text-slate-300">Manual Review</p>
                                <p className="text-xs text-slate-500">Our team will review your twin within 48 hours</p>
                            </div>
                        </div>
                        <div className="flex items-start gap-3 p-3 bg-white/5 rounded-xl">
                            <div className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center text-emerald-400 text-xs font-black">3</div>
                            <div>
                                <p className="text-sm font-bold text-slate-300">Get Verified</p>
                                <p className="text-xs text-slate-500">Receive your trust badge and unlock premium features</p>
                            </div>
                        </div>
                    </div>

                    <button
                        onClick={handleRequestVerification}
                        className="w-full py-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-2xl text-sm font-black transition-all shadow-lg shadow-indigo-500/20"
                    >
                        🛡️ Submit Verification Request
                    </button>
                </div>
            </Modal>
        </div>
    );
}
