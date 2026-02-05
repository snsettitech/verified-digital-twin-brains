'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { Card, CardHeader, CardContent, Modal, useToast } from '@/components/ui';
import { useTwin } from '@/lib/context/TwinContext';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';

interface Connector {
    id: string;
    connector_type: string;
    name: string;
    config: Record<string, any>;
    is_active: boolean;
    last_used_at?: string;
    last_error?: string;
    created_at: string;
}

const CONNECTOR_TYPES = [
    { value: 'gmail', label: 'Gmail', icon: '📧', description: 'Read emails and create drafts' },
    { value: 'google_calendar', label: 'Google Calendar', icon: '📅', description: 'Read events and create drafts' },
    { value: 'slack', label: 'Slack', icon: '💬', description: 'Send messages to channels' },
    { value: 'webhook', label: 'Webhook', icon: '🔗', description: 'Call external HTTP endpoints' },
    { value: 'notion', label: 'Notion', icon: '📝', description: 'Read and create pages' },
];

export default function ConnectorsPage() {
    const { showToast } = useToast();
    const { activeTwin, isLoading: twinLoading } = useTwin();
    const { get, post, del } = useAuthFetch();
    const [connectors, setConnectors] = useState<Connector[]>([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [selectedType, setSelectedType] = useState('');
    const [connectorName, setConnectorName] = useState('');
    const [testingId, setTestingId] = useState<string | null>(null);

    const twinId = activeTwin?.id;

    const fetchConnectors = useCallback(async () => {
        if (!twinId) return;
        try {
            const res = await get(`/twins/${twinId}/connectors`);
            if (res.ok) setConnectors(await res.json());
        } catch (err) {
            console.error('Fetch error:', err);
        } finally {
            setLoading(false);
        }
    }, [twinId, get]);

    useEffect(() => {
        if (twinId) {
            fetchConnectors();
        } else if (!twinLoading) {
            setLoading(false);
        }
    }, [twinId, twinLoading, fetchConnectors]);

    const handleCreate = async () => {
        if (!selectedType || !connectorName || !twinId) return;
        try {
            const res = await post(`/twins/${twinId}/connectors`, {
                connector_type: selectedType,
                name: connectorName,
                config: {}
            });
            if (res.ok) {
                showToast('Connector added successfully', 'success');
                setShowModal(false);
                setSelectedType('');
                setConnectorName('');
                fetchConnectors();
            }
        } catch (err) {
            showToast('Failed to add connector', 'error');
        }
    };

    const handleTest = async (id: string) => {
        if (!twinId) return;
        setTestingId(id);
        try {
            const res = await post(`/twins/${twinId}/connectors/${id}/test`, {});
            const data = await res.json();
            if (data.success) {
                showToast('Connection verified successfully', 'success');
            } else {
                showToast(data.error || 'Connection test failed', 'error');
            }
            fetchConnectors();
        } catch (err) {
            showToast('Connection test failed', 'error');
        } finally {
            setTestingId(null);
        }
    };

    const handleDelete = async (id: string) => {
        if (!twinId) return;
        if (!confirm('Are you sure you want to remove this connector?')) return;
        try {
            await del(`/twins/${twinId}/connectors/${id}`);
            showToast('Connector removed', 'success');
            fetchConnectors();
        } catch (err) {
            showToast('Failed to remove connector', 'error');
        }
    };

    const getConnectorInfo = (type: string) => {
        return CONNECTOR_TYPES.find(c => c.value === type) || { icon: '🔌', label: type, description: '' };
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
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z" />
                        </svg>
                    </div>
                    <h2 className="text-2xl font-bold text-white mb-3">No Twin Found</h2>
                    <p className="text-slate-400 mb-6">Create a digital twin first to configure connectors.</p>
                    <a href="/dashboard/right-brain" className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition-colors">
                        Create Your Twin
                    </a>
                </div>
            </div>
        );
    }

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
                        <h1 className="text-4xl font-black tracking-tight text-white mb-2">Connectors</h1>
                        <p className="text-slate-400 font-medium">Connect external tools and services for action execution.</p>
                    </div>
                    <button
                        onClick={() => setShowModal(true)}
                        className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-black transition-all shadow-lg shadow-indigo-500/20"
                    >
                        + Add Connector
                    </button>
                </div>
            </div>

            {/* Connected */}
            <Card glass>
                <CardHeader>
                    <h3 className="text-lg font-black text-white">Connected Services</h3>
                </CardHeader>
                <CardContent className="p-0">
                    {connectors.length === 0 ? (
                        <div className="p-10 text-center">
                            <div className="text-4xl mb-3">🔌</div>
                            <p className="text-slate-500 text-sm font-medium">No connectors configured</p>
                            <p className="text-slate-600 text-xs mt-1">Add a connector to enable external integrations</p>
                        </div>
                    ) : (
                        <div className="divide-y divide-white/5">
                            {connectors.map((connector) => {
                                const info = getConnectorInfo(connector.connector_type);
                                return (
                                    <div key={connector.id} className="p-5 hover:bg-white/5 transition-colors">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-4">
                                                <div className="w-12 h-12 rounded-2xl bg-slate-800 flex items-center justify-center text-2xl">
                                                    {info.icon}
                                                </div>
                                                <div>
                                                    <div className="font-bold text-white">{connector.name}</div>
                                                    <div className="text-xs text-slate-500 mt-0.5">{info.label}</div>
                                                    {connector.last_error && (
                                                        <div className="text-xs text-rose-400 mt-1">⚠️ {connector.last_error}</div>
                                                    )}
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <button
                                                    onClick={() => handleTest(connector.id)}
                                                    disabled={testingId === connector.id}
                                                    className="px-3 py-1.5 bg-white/5 hover:bg-white/10 text-white rounded-lg text-xs font-bold transition-all disabled:opacity-50"
                                                >
                                                    {testingId === connector.id ? '...' : 'Test'}
                                                </button>
                                                <button
                                                    onClick={() => handleDelete(connector.id)}
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

            {/* Available */}
            <div>
                <h3 className="text-sm font-black text-slate-500 uppercase tracking-widest mb-4">Available Integrations</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {CONNECTOR_TYPES.map((type) => {
                        const hasConnector = connectors.some(c => c.connector_type === type.value);
                        return (
                            <div
                                key={type.value}
                                className={`${hasConnector ? 'opacity-50' : 'cursor-pointer'}`}
                                onClick={() => {
                                    if (!hasConnector) {
                                        setSelectedType(type.value);
                                        setConnectorName(type.label);
                                        setShowModal(true);
                                    }
                                }}
                            >
                                <Card
                                    glass
                                    className={`p-5 ${!hasConnector && 'hover:border-indigo-500/30'}`}
                                >
                                    <div className="flex items-center gap-4">
                                        <div className="w-12 h-12 rounded-2xl bg-slate-800 flex items-center justify-center text-2xl">
                                            {type.icon}
                                        </div>
                                        <div className="flex-1">
                                            <div className="font-bold text-white">{type.label}</div>
                                            <div className="text-xs text-slate-500 mt-0.5">{type.description}</div>
                                        </div>
                                        {hasConnector ? (
                                            <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 text-[10px] font-black rounded-lg">
                                                Connected
                                            </span>
                                        ) : (
                                            <span className="text-indigo-400 text-sm">+</span>
                                        )}
                                    </div>
                                </Card>
                            </div>
                        );
                    })}
                </div>
            </div>

            <Modal isOpen={showModal} onClose={() => setShowModal(false)} title="Add Connector">
                <div className="space-y-5 pt-4">
                    {!selectedType ? (
                        <div className="space-y-3">
                            <p className="text-sm text-slate-400 mb-4">Select a service to connect:</p>
                            {CONNECTOR_TYPES.map((type) => (
                                <div
                                    key={type.value}
                                    onClick={() => {
                                        setSelectedType(type.value);
                                        setConnectorName(type.label);
                                    }}
                                    className="p-4 bg-slate-800/50 hover:bg-slate-800 rounded-xl cursor-pointer transition-colors flex items-center gap-4"
                                >
                                    <span className="text-2xl">{type.icon}</span>
                                    <div>
                                        <div className="font-bold text-white">{type.label}</div>
                                        <div className="text-xs text-slate-500">{type.description}</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <>
                            <div className="p-4 bg-slate-800/50 rounded-xl flex items-center gap-4">
                                <span className="text-3xl">{getConnectorInfo(selectedType).icon}</span>
                                <div>
                                    <div className="font-bold text-white">{getConnectorInfo(selectedType).label}</div>
                                    <div className="text-xs text-slate-500">{getConnectorInfo(selectedType).description}</div>
                                </div>
                            </div>
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">Connection Name</label>
                                <input
                                    type="text"
                                    value={connectorName}
                                    onChange={(e) => setConnectorName(e.target.value)}
                                    placeholder="e.g., Work Gmail"
                                    className="w-full px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-white text-sm outline-none focus:ring-2 focus:ring-indigo-500"
                                />
                            </div>
                            <div className="p-4 bg-amber-950/30 border border-amber-500/20 rounded-xl">
                                <p className="text-xs text-amber-400 font-bold">⚠️ OAuth Coming Soon</p>
                                <p className="text-xs text-amber-300/70 mt-1">
                                    Full OAuth authentication will be available in the next update. For now, connectors are added as placeholders.
                                </p>
                            </div>
                            <button
                                onClick={handleCreate}
                                disabled={!connectorName}
                                className="w-full py-4 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-xl text-sm font-black transition-all"
                            >
                                Add Connector
                            </button>
                        </>
                    )}
                </div>
            </Modal>
        </div>
    );
}
