'use client';

import React, { useState, useEffect } from 'react';
import { useFeatureFlag } from '@/lib/features/FeatureFlags';

interface KnowledgeNode {
    id: string;
    type: string;
    label: string;
    value?: string;
    status: 'filled' | 'pending' | 'empty';
}

interface SplitBrainLayoutProps {
    twinName: string;
    chatContent: React.ReactNode;
    nodes?: KnowledgeNode[];
    currentCluster?: string;
}

export function SplitBrainLayout({
    twinName,
    chatContent,
    nodes = [],
    currentCluster
}: SplitBrainLayoutProps) {
    const showGraph = useFeatureFlag('knowledgeGraphPreview');
    const [isCollapsed, setIsCollapsed] = useState(false);

    // Group nodes by cluster
    const clusters = [
        { id: 'profile', label: 'Your Profile', icon: '👤', color: 'indigo' },
        { id: 'knowledge', label: 'Your Knowledge', icon: '📚', color: 'emerald' },
        { id: 'style', label: 'Your Style', icon: '💬', color: 'purple' }
    ];

    const getNodesByCluster = (clusterId: string) => {
        return nodes.filter(n => n.type.startsWith(clusterId));
    };

    const getClusterProgress = (clusterId: string) => {
        const clusterNodes = getNodesByCluster(clusterId);
        if (clusterNodes.length === 0) return 0;
        const filled = clusterNodes.filter(n => n.status === 'filled').length;
        return Math.round((filled / clusterNodes.length) * 100);
    };

    return (
        <div className="flex h-full">
            {/* Chat Panel */}
            <div className={`flex-1 transition-all duration-300 ${!isCollapsed && showGraph ? 'pr-0' : ''}`}>
                {chatContent}
            </div>

            {/* Knowledge Preview Panel */}
            {showGraph && (
                <div className={`
          relative transition-all duration-300 border-l border-white/10 bg-[#0a0a0f]
          ${isCollapsed ? 'w-12' : 'w-80'}
        `}>
                    {/* Collapse Toggle */}
                    <button
                        onClick={() => setIsCollapsed(!isCollapsed)}
                        className="absolute -left-3 top-4 w-6 h-6 bg-slate-800 border border-white/10 rounded-full flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-700 transition-colors z-10"
                    >
                        <svg
                            className={`w-3 h-3 transition-transform ${isCollapsed ? 'rotate-180' : ''}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                        </svg>
                    </button>

                    {!isCollapsed ? (
                        <div className="p-4 h-full overflow-y-auto scrollbar-thin">
                            {/* Header */}
                            <div className="mb-6">
                                <h3 className="text-sm font-semibold text-white mb-1">Knowledge Building</h3>
                                <p className="text-xs text-slate-500">{twinName}'s mind is forming...</p>
                            </div>

                            {/* Brain Visualization Mini */}
                            <div className="relative w-full aspect-square mb-6 bg-gradient-to-br from-indigo-500/10 to-purple-500/10 rounded-2xl flex items-center justify-center">
                                <div className="relative w-24 h-24">
                                    {/* Central Node */}
                                    <div className="absolute inset-0 flex items-center justify-center">
                                        <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full flex items-center justify-center text-white text-lg font-bold shadow-lg shadow-indigo-500/30">
                                            {twinName.charAt(0)}
                                        </div>
                                    </div>

                                    {/* Orbiting Cluster Indicators */}
                                    {clusters.map((cluster, idx) => {
                                        const angle = (idx * 120 - 90) * (Math.PI / 180);
                                        const progress = getClusterProgress(cluster.id);
                                        const isActive = currentCluster === cluster.id;

                                        return (
                                            <div
                                                key={cluster.id}
                                                className={`
                          absolute w-8 h-8 rounded-lg flex items-center justify-center text-sm
                          transition-all
                          ${isActive ? 'scale-125 animate-pulse' : ''}
                          ${progress > 0 ? 'bg-white/10' : 'bg-white/5'}
                        `}
                                                style={{
                                                    left: `calc(50% + ${Math.cos(angle) * 40}px - 16px)`,
                                                    top: `calc(50% + ${Math.sin(angle) * 40}px - 16px)`,
                                                }}
                                            >
                                                {cluster.icon}
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>

                            {/* Cluster Progress */}
                            <div className="space-y-3">
                                {clusters.map(cluster => {
                                    const progress = getClusterProgress(cluster.id);
                                    const clusterNodes = getNodesByCluster(cluster.id);
                                    const isActive = currentCluster === cluster.id;

                                    return (
                                        <div
                                            key={cluster.id}
                                            className={`p-3 rounded-xl border transition-all ${isActive
                                                    ? 'bg-indigo-500/10 border-indigo-500/30'
                                                    : 'bg-white/5 border-white/10'
                                                }`}
                                        >
                                            <div className="flex items-center justify-between mb-2">
                                                <div className="flex items-center gap-2">
                                                    <span>{cluster.icon}</span>
                                                    <span className="text-sm font-medium text-white">{cluster.label}</span>
                                                </div>
                                                <span className="text-xs text-slate-400">{progress}%</span>
                                            </div>
                                            <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                                                <div
                                                    className={`h-full rounded-full transition-all duration-500 bg-gradient-to-r 
                            ${cluster.color === 'indigo' ? 'from-indigo-500 to-purple-500' : ''}
                            ${cluster.color === 'emerald' ? 'from-emerald-500 to-teal-500' : ''}
                            ${cluster.color === 'purple' ? 'from-purple-500 to-pink-500' : ''}
                          `}
                                                    style={{ width: `${progress}%` }}
                                                />
                                            </div>

                                            {/* Node Chips */}
                                            {clusterNodes.length > 0 && (
                                                <div className="flex flex-wrap gap-1 mt-2">
                                                    {clusterNodes.slice(0, 4).map(node => (
                                                        <span
                                                            key={node.id}
                                                            className={`px-2 py-0.5 text-[10px] rounded-full ${node.status === 'filled'
                                                                    ? 'bg-emerald-500/20 text-emerald-400'
                                                                    : node.status === 'pending'
                                                                        ? 'bg-amber-500/20 text-amber-400'
                                                                        : 'bg-white/10 text-slate-500'
                                                                }`}
                                                        >
                                                            {node.label}
                                                        </span>
                                                    ))}
                                                    {clusterNodes.length > 4 && (
                                                        <span className="px-2 py-0.5 text-[10px] text-slate-500">
                                                            +{clusterNodes.length - 4} more
                                                        </span>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Tips */}
                            <div className="mt-6 p-3 bg-indigo-500/10 border border-indigo-500/20 rounded-xl">
                                <p className="text-xs text-indigo-300">
                                    💡 As you answer questions, watch your twin's knowledge grow in real-time!
                                </p>
                            </div>
                        </div>
                    ) : (
                        /* Collapsed State */
                        <div className="flex flex-col items-center py-4 gap-4">
                            {clusters.map(cluster => {
                                const progress = getClusterProgress(cluster.id);
                                const isActive = currentCluster === cluster.id;

                                return (
                                    <div
                                        key={cluster.id}
                                        className={`
                      w-8 h-8 rounded-lg flex items-center justify-center text-sm
                      ${isActive ? 'bg-indigo-500/30 ring-2 ring-indigo-500' : 'bg-white/10'}
                    `}
                                        title={`${cluster.label}: ${progress}%`}
                                    >
                                        {cluster.icon}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export default SplitBrainLayout;
