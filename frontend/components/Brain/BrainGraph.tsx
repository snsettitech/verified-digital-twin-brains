'use client';

import React, { useState, useEffect } from 'react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const AUTH_TOKEN = process.env.NEXT_PUBLIC_DEV_TOKEN || 'development_token';

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

export default function BrainGraph({
    twinId,
    refreshTrigger = 0
}: {
    twinId: string;
    refreshTrigger?: number;
}) {
    const [data, setData] = useState<GraphData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchGraph = async () => {
            try {
                // Determine Twin ID (Prop or Default for Dev)
                const tid = twinId || 'eeeed554-9180-4229-a9af-0f8dd2c69e9b';

                // Use the correct graph endpoint: /twins/{id}/graph
                const res = await fetch(`${API_BASE_URL}/twins/${tid}/graph?limit=100`, {
                    headers: { 'Authorization': `Bearer ${AUTH_TOKEN}` }
                });

                if (res.ok) {
                    const json = await res.json();
                    setData(json);
                }
            } catch (e) {
                console.error("Graph fetch failed:", e);
            } finally {
                setLoading(false);
            }
        };

        fetchGraph();
    }, [twinId, refreshTrigger]);

    // Simple Visualization Logic (Circular Layout)
    if (loading && !data) return (
        <div className="flex items-center justify-center h-full text-slate-500 text-xs">Loading Graph...</div>
    );

    if (!data || data.nodes.length === 0) return (
        <div className="flex flex-col items-center justify-center h-full text-slate-500 opacity-50">
            <svg className="w-12 h-12 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path></svg>
            <p className="text-xs font-bold uppercase tracking-widest">Graph Empty</p>
        </div>
    );

    return (
        <div className="w-full h-full relative overflow-hidden bg-slate-900 flex items-center justify-center">
            {/* Background Grid */}
            <div className="absolute inset-0 opacity-10 pointer-events-none"
                style={{ backgroundImage: 'radial-gradient(#6366f1 1px, transparent 1px)', backgroundSize: '30px 30px' }}>
            </div>

            <div className="relative w-[80%] h-[80%] animate-spin-slow" style={{ animationDuration: '60s' }}>
                <style jsx>{`
                    @keyframes spin-slow {
                        from { transform: rotate(0deg); }
                        to { transform: rotate(360deg); }
                    }
                    .animate-spin-slow {
                        animation: spin-slow linear infinite;
                    }
                `}</style>

                {data.nodes.map((node, i) => {
                    const angle = (i / data.nodes.length) * 2 * Math.PI;
                    // Distribute radius slightly randomly
                    const radius = 120 + (i % 3) * 40;
                    const x = Math.cos(angle) * radius;
                    const y = Math.sin(angle) * radius;

                    // Color by type
                    let color = 'bg-indigo-500';
                    if (node.type?.toLowerCase().includes('person')) color = 'bg-pink-500';
                    if (node.type?.toLowerCase().includes('company')) color = 'bg-blue-500';
                    if (node.type?.toLowerCase().includes('thesis')) color = 'bg-emerald-500';

                    return (
                        <div key={node.id}
                            className={`absolute w-3 h-3 rounded-full ${color} shadow-lg shadow-white/20 transform -translate-x-1/2 -translate-y-1/2 transition-all hover:scale-150 cursor-pointer group z-10`}
                            style={{
                                left: `calc(50% + ${x}px)`,
                                top: `calc(50% + ${y}px)`
                            }}
                        >
                            <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 whitespace-nowrap bg-black/80 text-white px-2 py-1 rounded text-[10px] font-bold opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-20">
                                {node.name}
                            </div>
                        </div>
                    );
                })}

                {/* Center Hub */}
                <div className="absolute left-1/2 top-1/2 w-6 h-6 bg-white rounded-full -translate-x-1/2 -translate-y-1/2 shadow-[0_0_20px_white] z-0 opacity-50"></div>
            </div>

            <div className="absolute bottom-4 right-4 text-right pointer-events-none">
                <p className="text-slate-600 text-[10px] font-mono">NODES: {data.stats.node_count}</p>
                <p className="text-emerald-500 text-[10px] font-mono animate-pulse">LIVE</p>
            </div>
        </div>
    );
}
