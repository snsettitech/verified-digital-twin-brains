'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useSpecialization } from '@/contexts/SpecializationContext';
import { useTwin } from '@/lib/context/TwinContext';
import { getSupabaseClient } from '@/lib/supabase/client';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface Node {
    id: string;
    name: string;
    type: string;
    description: string;
    properties: any;
}

interface Edge {
    id: string;
    from_node_id: string;
    to_node_id: string;
    type: string;
}

interface GraphData {
    nodes: Node[];
    edges: Edge[];
    stats: {
        node_count: number;
        edge_count: number;
    };
}

export default function BrainGraphPage() {
    const { config } = useSpecialization();
    const { activeTwin, isLoading: twinLoading } = useTwin();
    const supabase = getSupabaseClient();
    const [data, setData] = useState<GraphData | null>(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState<'visual' | 'data'>('data');
    const [selectedNode, setSelectedNode] = useState<Node | null>(null);

    // Version state
    const [currentVersion, setCurrentVersion] = useState<number>(0);
    const [versions, setVersions] = useState<any[]>([]);
    const [approving, setApproving] = useState(false);
    const [showVersions, setShowVersions] = useState(false);

    // Use active twin from context
    const twinId = activeTwin?.id;

    useEffect(() => {
        if (twinId) {
            fetchGraph();
            fetchVersions();
        }
    }, [twinId]);

    const fetchGraph = async () => {
        try {
            setLoading(true);
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) return;

            const res = await fetch(`${API_BASE_URL}/twins/${twinId}/graph?limit=100`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const json = await res.json();
                setData(json);
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const fetchVersions = async () => {
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) return;

            const res = await fetch(`${API_BASE_URL}/cognitive/profiles/${twinId}/versions`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const json = await res.json();
                setVersions(json.versions || []);
                if (json.versions?.length > 0) {
                    setCurrentVersion(json.versions[0].version);
                }
            }
        } catch (e) {
            console.error('Failed to fetch versions:', e);
        }
    };

    const handleApprove = async () => {
        if (approving) return;
        setApproving(true);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) {
                alert('Not authenticated');
                return;
            }

            const res = await fetch(`${API_BASE_URL}/cognitive/profiles/${twinId}/approve`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ notes: 'Approved via Brain Explorer' })
            });
            if (res.ok) {
                const result = await res.json();
                alert(`✓ Profile approved! Version ${result.version} created with ${result.node_count} nodes.`);
                fetchVersions();
            } else {
                const err = await res.json();
                alert(`Failed: ${err.detail || 'Unknown error'}`);
            }
        } catch (e) {
            console.error('Approval failed:', e);
            alert('Approval failed. See console for details.');
        } finally {
            setApproving(false);
        }
    };

    // Group nodes by type
    const nodesByType = data?.nodes.reduce((acc, node) => {
        const t = node.type || 'Unknown';
        if (!acc[t]) acc[t] = [];
        acc[t].push(node);
        return acc;
    }, {} as Record<string, Node[]>) || {};

    // Loading state
    if (twinLoading) {
        return (
            <div className="flex items-center justify-center h-[calc(100vh-theme(spacing.16))]">
                <div className="text-center">
                    <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                    <p className="text-slate-500">Loading your twin...</p>
                </div>
            </div>
        );
    }

    // No twin state
    if (!twinId) {
        return (
            <div className="flex items-center justify-center h-[calc(100vh-theme(spacing.16))] bg-slate-50">
                <div className="text-center max-w-md p-8">
                    <div className="w-16 h-16 bg-indigo-100 rounded-2xl flex items-center justify-center mx-auto mb-6">
                        <svg className="w-8 h-8 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                        </svg>
                    </div>
                    <h2 className="text-2xl font-bold text-slate-900 mb-3">No Twin Found</h2>
                    <p className="text-slate-500 mb-6">
                        Create a digital twin first to explore your brain graph.
                    </p>
                    <Link
                        href="/dashboard/right-brain"
                        className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition-colors"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                        </svg>
                        Create Your Twin
                    </Link>
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-[calc(100vh-theme(spacing.16))] bg-white">
            {/* Header */}
            <header className="px-8 py-6 border-b border-slate-100 flex justify-between items-center bg-white sticky top-0 z-10">
                <div>
                    <h1 className="text-2xl font-black tracking-tight text-slate-800 flex items-center gap-3">
                        <span className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
                            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" /></svg>
                        </span>
                        Brain Graph Explorer
                        <span className="text-xs font-mono bg-slate-100 text-slate-500 px-2 py-1 rounded ml-2">BETA</span>
                        {currentVersion > 0 && (
                            <span className="text-xs font-mono bg-green-100 text-green-700 px-2 py-1 rounded ml-1">
                                v{currentVersion}
                            </span>
                        )}
                    </h1>
                    <p className="text-sm text-slate-400 mt-1 ml-14">
                        Visualizing {data?.stats.node_count || 0} entities and {data?.stats.edge_count || 0} relationships
                    </p>
                </div>

                <div className="flex items-center gap-4">
                    {/* Approve Button */}
                    <button
                        onClick={handleApprove}
                        disabled={approving || !data?.stats.node_count}
                        className={`px-4 py-2 rounded-lg font-bold text-sm flex items-center gap-2 transition-all ${approving
                            ? 'bg-gray-200 text-gray-400 cursor-wait'
                            : data?.stats.node_count
                                ? 'bg-green-600 text-white hover:bg-green-700 shadow-lg shadow-green-200'
                                : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                            }`}
                    >
                        {approving ? (
                            <>
                                <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>
                                Approving...
                            </>
                        ) : (
                            <>
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                </svg>
                                Approve Profile
                            </>
                        )}
                    </button>

                    {/* Version History Toggle */}
                    {versions.length > 0 && (
                        <button
                            onClick={() => setShowVersions(!showVersions)}
                            className="px-3 py-2 text-xs font-bold text-slate-500 hover:text-indigo-600 border border-slate-200 rounded-lg"
                        >
                            📜 {versions.length} version{versions.length > 1 ? 's' : ''}
                        </button>
                    )}

                    {/* View Mode Tabs */}
                    <div className="flex gap-2 bg-slate-100 p-1 rounded-lg">
                        <button
                            onClick={() => setActiveTab('data')}
                            className={`px-4 py-2 text-xs font-bold rounded-md transition-all ${activeTab === 'data' ? 'bg-white shadow-sm text-indigo-600' : 'text-slate-500 hover:text-slate-700'}`}
                        >
                            DATA VIEW
                        </button>
                        <button
                            onClick={() => setActiveTab('visual')}
                            className={`px-4 py-2 text-xs font-bold rounded-md transition-all ${activeTab === 'visual' ? 'bg-white shadow-sm text-indigo-600' : 'text-slate-500 hover:text-slate-700'}`}
                        >
                            VISUALIZATION
                        </button>
                    </div>
                </div>
            </header>

            {/* Version History Panel */}
            {showVersions && versions.length > 0 && (
                <div className="bg-slate-50 border-b border-slate-200 px-8 py-4">
                    <h3 className="text-xs font-bold text-slate-400 uppercase mb-3">Version History</h3>
                    <div className="flex gap-4 overflow-x-auto pb-2">
                        {versions.map((v: any) => (
                            <div key={v.version} className="bg-white rounded-lg border border-slate-200 px-4 py-3 min-w-[200px]">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="font-bold text-indigo-600">v{v.version}</span>
                                    <span className="text-xs text-slate-400">{new Date(v.approved_at).toLocaleDateString()}</span>
                                </div>
                                <div className="text-xs text-slate-500">
                                    {v.node_count} nodes, {v.edge_count} edges
                                </div>
                                <div className="text-xs text-green-600 mt-1">{v.diff_summary}</div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Content */}
            <div className="flex-1 overflow-auto bg-slate-50 p-8">
                {loading ? (
                    <div className="flex justify-center items-center h-64">
                        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
                    </div>
                ) : (
                    <>
                        {/* DATA VIEW */}
                        {activeTab === 'data' && (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                                {Object.keys(nodesByType).length === 0 && (
                                    <div className="col-span-full text-center py-20 bg-white rounded-3xl border border-dashed border-slate-300">
                                        <p className="text-slate-400 font-medium">No nodes found in the graph.</p>
                                        <button className="mt-4 text-indigo-600 text-sm font-bold hover:underline">Import Data</button>
                                    </div>
                                )}

                                {Object.entries(nodesByType).map(([type, nodes]) => (
                                    <div key={type} className="space-y-4">
                                        <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                            {type} <span className="bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded text-[10px]">{nodes.length}</span>
                                        </h3>
                                        <div className="grid gap-3">
                                            {nodes.map(node => (
                                                <div
                                                    key={node.id}
                                                    onClick={() => setSelectedNode(node)}
                                                    className="bg-white p-4 rounded-xl border border-slate-200 hover:border-indigo-400 hover:shadow-md transition-all cursor-pointer group"
                                                >
                                                    <h4 className="font-bold text-slate-800 text-sm group-hover:text-indigo-600">{node.name}</h4>
                                                    <p className="text-xs text-slate-400 mt-1 line-clamp-2">{node.description || 'No description'}</p>

                                                    {/* Mini edges indication */}
                                                    <div className="mt-3 flex items-center gap-2">
                                                        <span className="text-[10px] bg-slate-50 text-slate-400 px-2 py-1 rounded">
                                                            ID: {node.id.slice(0, 8)}
                                                        </span>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* VISUAL VIEW (Simplified SVG Implementation for Premium Feel) */}
                        {activeTab === 'visual' && (
                            <div className="bg-slate-900 rounded-3xl overflow-hidden shadow-2xl h-full relative flex items-center justify-center border border-slate-800">
                                <style jsx>{`
                                    @keyframes spin-slow {
                                        from { transform: rotate(0deg); }
                                        to { transform: rotate(360deg); }
                                    }
                                    .animate-spin-slow {
                                        animation: spin-slow 20s linear infinite;
                                    }
                                `}</style>
                                {/* Background Grid */}
                                <div className="absolute inset-0 opacity-10 pointer-events-none"
                                    style={{ backgroundImage: 'radial-gradient(#6366f1 1px, transparent 1px)', backgroundSize: '40px 40px' }}>
                                </div>

                                {data?.nodes.length === 0 ? (
                                    <div className="text-center">
                                        <p className="text-slate-500 font-mono text-sm">GRAPH_EMPTY</p>
                                        <p className="text-indigo-400 text-xs mt-2">Ingest data to generate neural connections</p>
                                    </div>
                                ) : (
                                    <div className="relative w-full h-full p-10 flex items-center justify-center">
                                        {/* Mock Visualization Placeholder until D3 is integrated */}
                                        <div className="relative w-[500px] h-[500px] animate-spin-slow">
                                            {data?.nodes.map((node, i) => {
                                                const angle = (i / data.nodes.length) * 2 * Math.PI;
                                                const radius = 200;
                                                const x = Math.cos(angle) * radius + 250;
                                                const y = Math.sin(angle) * radius + 250;

                                                return (
                                                    <div key={node.id}
                                                        className="absolute w-4 h-4 rounded-full bg-indigo-500 shadow-[0_0_15px_rgba(99,102,241,0.5)] transform -translate-x-1/2 -translate-y-1/2 transition-all hover:scale-150 cursor-pointer text-white text-[10px] flex items-center justify-center"
                                                        style={{ left: x, top: y }}
                                                        title={node.name}
                                                    >
                                                        <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 whitespace-nowrap bg-black/50 px-2 py-1 rounded text-xs opacity-0 hover:opacity-100 transition-opacity">
                                                            {node.name}
                                                        </div>
                                                    </div>
                                                );
                                            })}

                                            {/* Connect center to all */}
                                            <div className="absolute left-1/2 top-1/2 w-8 h-8 bg-white rounded-full -translate-x-1/2 -translate-y-1/2 shadow-[0_0_30px_white] z-10 grid place-items-center">
                                                <span className="text-[10px] font-black">AI</span>
                                            </div>
                                        </div>

                                        <div className="absolute bottom-8 right-8 text-right">
                                            <p className="text-slate-500 text-xs font-mono">RENDER_MODE: CIRCULAR_FORCE</p>
                                            <p className="text-indigo-400 text-xs font-mono animate-pulse">LIVE_CONNECTION</p>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </>
                )}
            </div>

            {/* Inspector Sidebar */}
            {selectedNode && (
                <div className="fixed inset-y-0 right-0 w-80 bg-white border-l border-slate-200 shadow-2xl p-6 overflow-auto z-50 transform transition-transform">
                    <div className="flex justify-between items-start mb-6">
                        <h2 className="text-lg font-bold text-slate-800 break-words">{selectedNode.name}</h2>
                        <button onClick={() => setSelectedNode(null)} className="text-slate-400 hover:text-slate-600">
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                        </button>
                    </div>

                    <div className="space-y-6">
                        <div>
                            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-1">Type</label>
                            <span className="inline-block bg-indigo-50 text-indigo-700 px-2 py-1 rounded text-xs font-bold ring-1 ring-indigo-100">
                                {selectedNode.type}
                            </span>
                        </div>

                        <div>
                            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-1">Description</label>
                            <p className="text-sm text-slate-600 leading-relaxed">
                                {selectedNode.description || 'No description provided.'}
                            </p>
                        </div>

                        <div>
                            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-1">Properties</label>
                            <pre className="bg-slate-50 p-3 rounded-lg text-[10px] text-slate-500 overflow-x-auto border border-slate-100 font-mono">
                                {JSON.stringify(selectedNode.properties, null, 2)}
                            </pre>
                        </div>

                        <div className="pt-6 mt-6 border-t border-slate-100">
                            <button className="w-full py-2 bg-slate-900 text-white rounded-lg text-xs font-bold hover:bg-slate-800 transition-colors">
                                Edit Entity
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
