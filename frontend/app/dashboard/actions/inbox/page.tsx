'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { Card, CardHeader, CardContent, Modal, Toggle, useToast } from '@/components/ui';

interface ActionDraft {
    id: string;
    trigger_id: string;
    proposed_action: {
        action_type: string;
        config: Record<string, any>;
    };
    context: {
        trigger_name?: string;
        user_message?: string;
        event_type?: string;
    };
    expires_at?: string;
    created_at: string;
    action_triggers?: {
        name: string;
        action_type: string;
    };
}

export default function InboxPage() {
    const { showToast } = useToast();
    const [drafts, setDrafts] = useState<ActionDraft[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedDraft, setSelectedDraft] = useState<ActionDraft | null>(null);
    const [activeTab, setActiveTab] = useState<'respond' | 'approve' | 'reject'>('respond');
    const [responseMessage, setResponseMessage] = useState('');
    const [saveAsVerified, setSaveAsVerified] = useState(false);
    const [approvalNote, setApprovalNote] = useState('');

    const twinId = "eeeed554-9180-4229-a9af-0f8dd2c69e9b";

    const fetchDrafts = async () => {
        try {
            const res = await fetch(`http://localhost:8000/twins/${twinId}/action-drafts`, {
                headers: { 'Authorization': 'Bearer development_token' }
            });
            if (res.ok) setDrafts(await res.json());
        } catch (err) {
            console.error('Fetch error:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchDrafts(); }, []);

    const handleRespond = async (id: string) => {
        if (!responseMessage.trim()) {
            showToast('Please enter a response message', 'error');
            return;
        }
        try {
            const res = await fetch(`http://localhost:8000/twins/${twinId}/action-drafts/${id}/respond`, {
                method: 'POST',
                headers: {
                    'Authorization': 'Bearer development_token',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    response_message: responseMessage,
                    save_as_verified: saveAsVerified
                })
            });
            if (res.ok) {
                const data = await res.json();
                showToast(data.message || 'Response saved', 'success');
                setSelectedDraft(null);
                setResponseMessage('');
                setSaveAsVerified(false);
                fetchDrafts();
            }
        } catch (err) {
            showToast('Failed to send response', 'error');
        }
    };

    const handleApprove = async (id: string) => {
        try {
            const res = await fetch(`http://localhost:8000/twins/${twinId}/action-drafts/${id}/approve`, {
                method: 'POST',
                headers: {
                    'Authorization': 'Bearer development_token',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ approval_note: approvalNote })
            });
            if (res.ok) {
                showToast('Action approved and executed', 'success');
                setSelectedDraft(null);
                fetchDrafts();
            }
        } catch (err) {
            showToast('Failed to approve action', 'error');
        }
    };

    const handleReject = async (id: string) => {
        try {
            const res = await fetch(`http://localhost:8000/twins/${twinId}/action-drafts/${id}/reject`, {
                method: 'POST',
                headers: {
                    'Authorization': 'Bearer development_token',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ rejection_note: approvalNote })
            });
            if (res.ok) {
                showToast('Action rejected', 'success');
                setSelectedDraft(null);
                fetchDrafts();
            }
        } catch (err) {
            showToast('Failed to reject action', 'error');
        }
    };

    const getActionIcon = (type: string) => {
        switch (type) {
            case 'draft_email': return '📧';
            case 'draft_calendar_event': return '📅';
            case 'notify_owner': return '🔔';
            case 'escalate': return '⚠️';
            case 'webhook': return '🔗';
            default: return '⚡';
        }
    };

    const getTimeRemaining = (expiresAt?: string) => {
        if (!expiresAt) return null;
        const remaining = new Date(expiresAt).getTime() - Date.now();
        if (remaining <= 0) return 'Expired';
        const hours = Math.floor(remaining / (1000 * 60 * 60));
        if (hours > 24) return `${Math.floor(hours / 24)}d remaining`;
        return `${hours}h remaining`;
    };

    return (
        <div className="max-w-4xl mx-auto space-y-8 pb-20">
            <div>
                <div className="flex items-center gap-3 mb-2">
                    <Link href="/dashboard/actions" className="text-slate-500 hover:text-white transition-colors">
                        ← Actions Hub
                    </Link>
                </div>
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-4xl font-black tracking-tight text-white mb-2">Approval Inbox</h1>
                        <p className="text-slate-400 font-medium">Review triggered actions and respond to user requests.</p>
                    </div>
                    {drafts.length > 0 && (
                        <span className="px-4 py-2 bg-amber-500/20 text-amber-400 rounded-xl text-sm font-black">
                            {drafts.length} Pending
                        </span>
                    )}
                </div>
            </div>

            <Card glass>
                <CardContent className="p-0">
                    {drafts.length === 0 ? (
                        <div className="p-16 text-center">
                            <div className="text-5xl mb-4">✅</div>
                            <h3 className="text-xl font-bold text-white mb-2">All Clear!</h3>
                            <p className="text-slate-500 text-sm max-w-md mx-auto">
                                No pending approvals. When triggers match, actions requiring approval will appear here.
                            </p>
                        </div>
                    ) : (
                        <div className="divide-y divide-white/5">
                            {drafts.map((draft) => (
                                <div key={draft.id} className="p-5 hover:bg-white/5 transition-colors">
                                    <div className="flex items-start justify-between">
                                        <div className="flex items-start gap-4">
                                            <div className="w-12 h-12 rounded-2xl bg-amber-500/10 flex items-center justify-center text-2xl">
                                                {getActionIcon(draft.proposed_action.action_type)}
                                            </div>
                                            <div>
                                                <div className="font-bold text-white">
                                                    {draft.context.trigger_name || draft.action_triggers?.name || 'Triggered Action'}
                                                </div>
                                                <div className="text-sm text-slate-400 mt-1">
                                                    {draft.proposed_action.action_type.replace(/_/g, ' ')}
                                                </div>
                                                {draft.context.user_message && (
                                                    <div className="mt-2 p-3 bg-indigo-500/10 border border-indigo-500/20 rounded-lg text-sm text-indigo-200 max-w-lg">
                                                        💬 "{draft.context.user_message}"
                                                    </div>
                                                )}
                                                <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
                                                    <span>{new Date(draft.created_at).toLocaleString()}</span>
                                                    {draft.expires_at && (
                                                        <span className="px-2 py-0.5 bg-rose-500/10 text-rose-400 rounded-lg">
                                                            {getTimeRemaining(draft.expires_at)}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                        <button
                                            onClick={() => {
                                                setSelectedDraft(draft);
                                                setActiveTab('respond');
                                                setResponseMessage('');
                                                setApprovalNote('');
                                            }}
                                            className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-bold transition-all"
                                        >
                                            Respond
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            <Modal isOpen={!!selectedDraft} onClose={() => setSelectedDraft(null)} title="Respond to Request">
                {selectedDraft && (
                    <div className="space-y-5 pt-4">
                        {/* User's message */}
                        {selectedDraft.context.user_message && (
                            <div className="p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-2xl">
                                <div className="text-[10px] font-black text-indigo-400 uppercase tracking-widest mb-2">User Said</div>
                                <div className="text-white">"{selectedDraft.context.user_message}"</div>
                            </div>
                        )}

                        {/* Tabs */}
                        <div className="flex gap-1 p-1 bg-slate-800/50 rounded-xl">
                            <button
                                onClick={() => setActiveTab('respond')}
                                className={`flex-1 py-2 px-4 rounded-lg text-sm font-bold transition-all ${activeTab === 'respond'
                                        ? 'bg-indigo-600 text-white'
                                        : 'text-slate-400 hover:text-white'
                                    }`}
                            >
                                💬 Respond
                            </button>
                            <button
                                onClick={() => setActiveTab('approve')}
                                className={`flex-1 py-2 px-4 rounded-lg text-sm font-bold transition-all ${activeTab === 'approve'
                                        ? 'bg-emerald-600 text-white'
                                        : 'text-slate-400 hover:text-white'
                                    }`}
                            >
                                ✓ Approve
                            </button>
                            <button
                                onClick={() => setActiveTab('reject')}
                                className={`flex-1 py-2 px-4 rounded-lg text-sm font-bold transition-all ${activeTab === 'reject'
                                        ? 'bg-rose-600 text-white'
                                        : 'text-slate-400 hover:text-white'
                                    }`}
                            >
                                ✕ Reject
                            </button>
                        </div>

                        {/* Respond Tab */}
                        {activeTab === 'respond' && (
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">
                                        Your Response
                                    </label>
                                    <textarea
                                        value={responseMessage}
                                        onChange={(e) => setResponseMessage(e.target.value)}
                                        placeholder="Type your response to the user..."
                                        rows={4}
                                        className="w-full px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-white text-sm outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                                    />
                                </div>

                                <div className="flex items-center justify-between p-3 bg-purple-500/10 border border-purple-500/20 rounded-xl">
                                    <div>
                                        <span className="text-sm font-bold text-purple-300">Save to Knowledge Base</span>
                                        <p className="text-[10px] text-purple-400/70">Your response will be remembered for future similar questions</p>
                                    </div>
                                    <Toggle
                                        checked={saveAsVerified}
                                        label=""
                                        onChange={setSaveAsVerified}
                                    />
                                </div>

                                <button
                                    onClick={() => handleRespond(selectedDraft.id)}
                                    disabled={!responseMessage.trim()}
                                    className="w-full py-4 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-xl text-sm font-black transition-all"
                                >
                                    Send Response
                                </button>
                            </div>
                        )}

                        {/* Approve Tab */}
                        {activeTab === 'approve' && (
                            <div className="space-y-4">
                                <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
                                    <p className="text-sm text-emerald-300">
                                        This will execute the <strong>{selectedDraft.proposed_action.action_type.replace(/_/g, ' ')}</strong> action.
                                    </p>
                                </div>
                                <div>
                                    <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">
                                        Note (Optional)
                                    </label>
                                    <input
                                        type="text"
                                        value={approvalNote}
                                        onChange={(e) => setApprovalNote(e.target.value)}
                                        placeholder="Optional note for audit log..."
                                        className="w-full px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-white text-sm outline-none focus:ring-2 focus:ring-emerald-500"
                                    />
                                </div>
                                <button
                                    onClick={() => handleApprove(selectedDraft.id)}
                                    className="w-full py-4 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-sm font-black transition-all"
                                >
                                    ✓ Approve & Execute
                                </button>
                            </div>
                        )}

                        {/* Reject Tab */}
                        {activeTab === 'reject' && (
                            <div className="space-y-4">
                                <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl">
                                    <p className="text-sm text-rose-300">
                                        This will dismiss the action without executing it.
                                    </p>
                                </div>
                                <div>
                                    <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">
                                        Reason (Optional)
                                    </label>
                                    <input
                                        type="text"
                                        value={approvalNote}
                                        onChange={(e) => setApprovalNote(e.target.value)}
                                        placeholder="Why are you rejecting this?"
                                        className="w-full px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-white text-sm outline-none focus:ring-2 focus:ring-rose-500"
                                    />
                                </div>
                                <button
                                    onClick={() => handleReject(selectedDraft.id)}
                                    className="w-full py-4 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-sm font-black transition-all"
                                >
                                    ✕ Reject Action
                                </button>
                            </div>
                        )}
                    </div>
                )}
            </Modal>
        </div>
    );
}
