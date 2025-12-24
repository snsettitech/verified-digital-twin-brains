'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { Card, CardHeader, CardContent, Badge, Modal, Toggle, useToast } from '@/components/ui';

interface Trigger {
    id: string;
    name: string;
    description?: string;
    event_type: string;
    conditions: Record<string, any>;
    action_type: string;
    action_config: Record<string, any>;
    requires_approval: boolean;
    is_active: boolean;
    priority: number;
    created_at: string;
}

const EVENT_TYPES = [
    { value: 'message_received', label: 'Message Received', icon: '💬' },
    { value: 'answer_sent', label: 'Answer Sent', icon: '📤' },
    { value: 'escalation_created', label: 'Escalation Created', icon: '⚠️' },
    { value: 'confidence_low', label: 'Low Confidence Response', icon: '📉' },
    { value: 'idle_timeout', label: 'Idle Timeout', icon: '⏱️' },
];

const ACTION_TYPES = [
    { value: 'draft_email', label: 'Draft Email', icon: '📧' },
    { value: 'draft_calendar_event', label: 'Draft Calendar Event', icon: '📅' },
    { value: 'notify_owner', label: 'Notify Owner', icon: '🔔' },
    { value: 'escalate', label: 'Create Escalation', icon: '⚡' },
    { value: 'webhook', label: 'Call Webhook', icon: '🔗' },
];

export default function TriggersPage() {
    const { showToast } = useToast();
    const [triggers, setTriggers] = useState<Trigger[]>([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [formData, setFormData] = useState({
        name: '',
        description: '',
        event_type: 'message_received',
        action_type: 'notify_owner',
        keywords: '',
        requires_approval: true
    });

    const twinId = "eeeed554-9180-4229-a9af-0f8dd2c69e9b";

    const fetchTriggers = async () => {
        try {
            const res = await fetch(`http://localhost:8000/twins/${twinId}/triggers?include_inactive=true`, {
                headers: { 'Authorization': 'Bearer development_token' }
            });
            if (res.ok) setTriggers(await res.json());
        } catch (err) {
            console.error('Fetch error:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchTriggers(); }, []);

    const handleCreate = async () => {
        try {
            const res = await fetch(`http://localhost:8000/twins/${twinId}/triggers`, {
                method: 'POST',
                headers: {
                    'Authorization': 'Bearer development_token',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name: formData.name,
                    description: formData.description,
                    event_type: formData.event_type,
                    action_type: formData.action_type,
                    conditions: formData.keywords ? { keywords: formData.keywords.split(',').map(k => k.trim()) } : {},
                    requires_approval: formData.requires_approval
                })
            });
            if (res.ok) {
                showToast('Trigger created successfully', 'success');
                setShowModal(false);
                setFormData({ name: '', description: '', event_type: 'message_received', action_type: 'notify_owner', keywords: '', requires_approval: true });
                fetchTriggers();
            }
        } catch (err) {
            showToast('Failed to create trigger', 'error');
        }
    };

    const handleToggle = async (id: string, isActive: boolean) => {
        try {
            await fetch(`http://localhost:8000/twins/${twinId}/triggers/${id}`, {
                method: 'PUT',
                headers: {
                    'Authorization': 'Bearer development_token',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ is_active: !isActive })
            });
            fetchTriggers();
        } catch (err) {
            showToast('Failed to update trigger', 'error');
        }
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Are you sure you want to delete this trigger?')) return;
        try {
            await fetch(`http://localhost:8000/twins/${twinId}/triggers/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': 'Bearer development_token' }
            });
            showToast('Trigger deleted', 'success');
            fetchTriggers();
        } catch (err) {
            showToast('Failed to delete trigger', 'error');
        }
    };

    return (
        <div className="max-w-5xl mx-auto space-y-8 pb-20">
            <div className="flex items-center justify-between">
                <div>
                    <div className="flex items-center gap-3 mb-2">
                        <Link href="/dashboard/actions" className="text-slate-500 hover:text-white transition-colors">
                            ← Actions Hub
                        </Link>
                    </div>
                    <h1 className="text-4xl font-black tracking-tight text-white mb-2">Action Triggers</h1>
                    <p className="text-slate-400 font-medium">Configure rules that automatically trigger actions based on events.</p>
                </div>
                <button
                    onClick={() => setShowModal(true)}
                    className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-black transition-all shadow-lg shadow-indigo-500/20"
                >
                    + New Trigger
                </button>
            </div>

            <Card glass>
                <CardContent className="p-0">
                    {triggers.length === 0 ? (
                        <div className="p-16 text-center">
                            <div className="text-5xl mb-4">⚡</div>
                            <h3 className="text-xl font-bold text-white mb-2">No Triggers Configured</h3>
                            <p className="text-slate-500 text-sm max-w-md mx-auto">
                                Create your first trigger to automate actions. Triggers watch for specific events and execute actions when conditions match.
                            </p>
                            <button
                                onClick={() => setShowModal(true)}
                                className="mt-6 px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-black transition-all"
                            >
                                Create First Trigger
                            </button>
                        </div>
                    ) : (
                        <div className="divide-y divide-white/5">
                            {triggers.map((trigger) => {
                                const eventInfo = EVENT_TYPES.find(e => e.value === trigger.event_type);
                                const actionInfo = ACTION_TYPES.find(a => a.value === trigger.action_type);
                                const keywords = trigger.conditions?.keywords || [];

                                return (
                                    <div key={trigger.id} className="p-5 hover:bg-white/5 transition-colors">
                                        <div className="flex items-start justify-between">
                                            <div className="flex items-start gap-4">
                                                <div className={`w-3 h-3 rounded-full mt-1.5 ${trigger.is_active ? 'bg-emerald-500 animate-pulse' : 'bg-slate-600'}`}></div>
                                                <div className="space-y-2">
                                                    <div className="font-bold text-white text-lg">{trigger.name}</div>

                                                    {/* Flow visualization */}
                                                    <div className="flex items-center gap-2 flex-wrap">
                                                        <span className="text-slate-500 text-xs">When</span>
                                                        <span className="px-2.5 py-1 bg-indigo-500/20 text-indigo-300 rounded-lg text-xs font-bold flex items-center gap-1">
                                                            <span>{eventInfo?.icon}</span>
                                                            {eventInfo?.label || trigger.event_type}
                                                        </span>
                                                        {keywords.length > 0 && (
                                                            <>
                                                                <span className="text-slate-500 text-xs">contains</span>
                                                                <div className="flex gap-1 flex-wrap">
                                                                    {keywords.map((kw: string, i: number) => (
                                                                        <span key={i} className="px-2 py-0.5 bg-rose-500/20 text-rose-300 rounded text-xs font-mono">
                                                                            "{kw}"
                                                                        </span>
                                                                    ))}
                                                                </div>
                                                            </>
                                                        )}
                                                    </div>

                                                    <div className="flex items-center gap-2">
                                                        <span className="text-slate-500 text-xs">Then</span>
                                                        <span className="px-2.5 py-1 bg-purple-500/20 text-purple-300 rounded-lg text-xs font-bold flex items-center gap-1">
                                                            <span>{actionInfo?.icon}</span>
                                                            {actionInfo?.label || trigger.action_type}
                                                        </span>
                                                        {trigger.requires_approval ? (
                                                            <span className="px-2 py-0.5 bg-amber-500/20 text-amber-400 rounded text-xs">
                                                                ⏳ Needs Approval
                                                            </span>
                                                        ) : (
                                                            <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 rounded text-xs">
                                                                ⚡ Auto-Execute
                                                            </span>
                                                        )}
                                                    </div>

                                                    {trigger.description && (
                                                        <p className="text-xs text-slate-500 mt-1">{trigger.description}</p>
                                                    )}
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-3">
                                                <Toggle
                                                    checked={trigger.is_active}
                                                    label=""
                                                    onChange={() => handleToggle(trigger.id, trigger.is_active)}
                                                />
                                                <button
                                                    onClick={() => handleDelete(trigger.id)}
                                                    className="p-2 text-slate-500 hover:text-rose-500 transition-colors"
                                                >
                                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                                                    </svg>
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </CardContent>
            </Card>

            <Modal isOpen={showModal} onClose={() => setShowModal(false)} title="Create New Trigger">
                <div className="space-y-5 pt-4">
                    <div>
                        <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">Trigger Name</label>
                        <input
                            type="text"
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            placeholder="e.g., Schedule Meeting Request"
                            className="w-full px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-white text-sm outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                    </div>
                    <div>
                        <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">When This Event Happens</label>
                        <select
                            value={formData.event_type}
                            onChange={(e) => setFormData({ ...formData, event_type: e.target.value })}
                            className="w-full px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-white text-sm outline-none focus:ring-2 focus:ring-indigo-500"
                        >
                            {EVENT_TYPES.map((e) => (
                                <option key={e.value} value={e.value}>{e.icon} {e.label}</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">Keywords (comma-separated)</label>
                        <input
                            type="text"
                            value={formData.keywords}
                            onChange={(e) => setFormData({ ...formData, keywords: e.target.value })}
                            placeholder="e.g., schedule, meeting, calendar"
                            className="w-full px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-white text-sm outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                    </div>
                    <div>
                        <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">Then Do This Action</label>
                        <select
                            value={formData.action_type}
                            onChange={(e) => setFormData({ ...formData, action_type: e.target.value })}
                            className="w-full px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-white text-sm outline-none focus:ring-2 focus:ring-indigo-500"
                        >
                            {ACTION_TYPES.map((a) => (
                                <option key={a.value} value={a.value}>{a.icon} {a.label}</option>
                            ))}
                        </select>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-white/5 rounded-xl">
                        <div>
                            <span className="text-sm font-bold text-slate-300">Require Approval</span>
                            <p className="text-[10px] text-slate-500">Actions will wait for your approval before executing</p>
                        </div>
                        <Toggle checked={formData.requires_approval} label="" onChange={(v) => setFormData({ ...formData, requires_approval: v })} />
                    </div>
                    <button
                        onClick={handleCreate}
                        disabled={!formData.name}
                        className="w-full py-4 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-xl text-sm font-black transition-all"
                    >
                        Create Trigger
                    </button>
                </div>
            </Modal>
        </div>
    );
}
