'use client';

import React, { useState, useCallback } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface ExtractedNode {
    id: string;
    name: string;
    type: string;
    description?: string;
}

interface IngestionResult {
    source_id: string;
    status: string;
    nodes_created?: number;
    edges_created?: number;
    extracted_nodes?: ExtractedNode[];
}

type SourceType = 'youtube' | 'podcast' | 'twitter' | 'url' | 'file' | 'unknown';
type IngestionStage = 'idle' | 'detecting' | 'ingesting' | 'extracting' | 'complete' | 'error';

interface UnifiedIngestionProps {
    twinId: string;
    onComplete?: (result: IngestionResult) => void;
    onError?: (error: string) => void;
}

// Auto-detect source type from URL
function detectSourceType(input: string): SourceType {
    const url = input.trim().toLowerCase();

    if (url.includes('youtube.com') || url.includes('youtu.be')) {
        return 'youtube';
    }
    if (url.includes('x.com') || url.includes('twitter.com')) {
        return 'twitter';
    }
    if (url.includes('.rss') || url.includes('/feed') || url.includes('anchor.fm') || url.includes('podbean')) {
        return 'podcast';
    }
    if (url.startsWith('http://') || url.startsWith('https://')) {
        return 'url';
    }
    return 'unknown';
}

// Source type config
const sourceConfig: Record<SourceType, { icon: string; color: string; label: string; endpoint: string }> = {
    youtube: { icon: '📹', color: 'red', label: 'YouTube Video', endpoint: '/ingest/youtube' },
    podcast: { icon: '🎙️', color: 'purple', label: 'Podcast RSS', endpoint: '/ingest/podcast' },
    twitter: { icon: '𝕏', color: 'slate', label: 'X Thread', endpoint: '/ingest/x' },
    url: { icon: '🌐', color: 'blue', label: 'Web Page', endpoint: '/ingest/url' },
    file: { icon: '📄', color: 'indigo', label: 'File Upload', endpoint: '/ingest/file' },
    unknown: { icon: '❓', color: 'gray', label: 'Unknown', endpoint: '' },
};

export default function UnifiedIngestion({ twinId, onComplete, onError }: UnifiedIngestionProps) {
    const supabase = getSupabaseClient();
    const [input, setInput] = useState('');
    const [detectedType, setDetectedType] = useState<SourceType>('unknown');
    const [stage, setStage] = useState<IngestionStage>('idle');
    const [progress, setProgress] = useState(0);
    const [statusText, setStatusText] = useState('');
    const [extractedNodes, setExtractedNodes] = useState<ExtractedNode[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [dragActive, setDragActive] = useState(false);
    const fileInputRef = React.useRef<HTMLInputElement>(null);

    // Get auth token
    const getAuthToken = useCallback(async () => {
        const { data: { session } } = await supabase.auth.getSession();
        return session?.access_token;
    }, [supabase]);

    const resetState = () => {
        setInput('');
        setDetectedType('unknown');
        setStage('idle');
        setProgress(0);
        setExtractedNodes([]);
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    // Handle input change with auto-detection
    const handleInputChange = (value: string) => {
        setInput(value);
        setError(null);
        if (value.trim()) {
            const type = detectSourceType(value);
            setDetectedType(type);
        } else {
            setDetectedType('unknown');
        }
    };

    // Main ingestion flow
    const handleIngest = async () => {
        if (!input.trim() || detectedType === 'unknown') return;

        const token = await getAuthToken();
        if (!token) {
            setError('Not authenticated');
            return;
        }

        setStage('ingesting');
        setProgress(20);
        setStatusText(`Fetching ${sourceConfig[detectedType].label}...`);
        setExtractedNodes([]);

        try {
            // Step 1: Ingest content
            const endpoint = `${API_BASE_URL}${sourceConfig[detectedType].endpoint}/${twinId}`;
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: input.trim() }),
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || 'Ingestion failed');
            }

            const result = await response.json();
            setProgress(50);
            setStatusText('Content ingested. Extracting knowledge...');
            setStage('extracting');

            // Step 2: Extract nodes from the source
            const extractResponse = await fetch(`${API_BASE_URL}/ingest/extract-nodes/${result.source_id}`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ max_chunks: 5 }),
            });

            setProgress(80);

            if (extractResponse.ok) {
                const extractResult = await extractResponse.json();
                setExtractedNodes(extractResult.nodes || []);
                setProgress(100);
                setStatusText(`Done! ${extractResult.nodes_created || 0} nodes, ${extractResult.edges_created || 0} edges`);
                setStage('complete');

                onComplete?.({
                    source_id: result.source_id,
                    status: 'complete',
                    nodes_created: extractResult.nodes_created,
                    edges_created: extractResult.edges_created,
                });
            } else {
                // Extraction failed but ingestion succeeded
                setProgress(100);
                setStatusText('Content saved (extraction pending)');
                setStage('complete');
                onComplete?.({ source_id: result.source_id, status: 'live' });
            }

            // Reset input after success
            setTimeout(() => {
                resetState();
            }, 3000);

        } catch (err: any) {
            setError(err.message || 'Something went wrong');
            setStage('error');
            onError?.(err.message);
        }
    };

    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        const token = await getAuthToken();
        if (!token) {
            setError('Not authenticated');
            return;
        }

        setDetectedType('file');
        setStage('ingesting');
        setProgress(20);
        setStatusText(`Uploading ${file.name}...`);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch(`${API_BASE_URL}/ingest/file/${twinId}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData,
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || 'Upload failed');
            }

            const result = await response.json();
            setProgress(100);
            setStatusText('File uploaded and indexed!');
            setStage('complete');
            onComplete?.({ source_id: result.source_id, status: 'live' });

            setTimeout(() => {
                resetState();
            }, 2000);

        } catch (err: any) {
            setError(err.message);
            setStage('error');
            resetState(); // Reset on error too so user can try again
        }
    };

    // File drop handling
    const handleDrop = async (e: React.DragEvent) => {
        e.preventDefault();
        setDragActive(false);

        const file = e.dataTransfer.files[0];
        if (!file) return;

        const token = await getAuthToken();
        if (!token) {
            setError('Not authenticated');
            return;
        }

        setDetectedType('file');
        setStage('ingesting');
        setProgress(20);
        setStatusText(`Uploading ${file.name}...`);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch(`${API_BASE_URL}/ingest/file/${twinId}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData,
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || 'Upload failed');
            }

            const result = await response.json();
            setProgress(100);
            setStatusText('File uploaded and indexed!');
            setStage('complete');
            onComplete?.({ source_id: result.source_id, status: 'live' });

            setTimeout(() => {
                setStage('idle');
                setProgress(0);
                setDetectedType('unknown');
            }, 2000);

        } catch (err: any) {
            setError(err.message);
            setStage('error');
        }
    };

    const config = sourceConfig[detectedType];
    const isProcessing = stage === 'ingesting' || stage === 'extracting' || stage === 'detecting';

    return (
        <div className="bg-white rounded-[2rem] border border-slate-200 shadow-sm overflow-hidden">
            {/* Header */}
            <div className="p-6 border-b border-slate-100">
                <h3 className="text-lg font-black text-slate-800">Train Your Twin</h3>
                <p className="text-sm text-slate-500 mt-1">Paste a URL or drop a file to add knowledge</p>
            </div>

            {/* Input Zone */}
            <div
                className={`p-6 transition-colors ${dragActive ? 'bg-indigo-50' : 'bg-slate-50/50'}`}
                onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
                onDragLeave={() => setDragActive(false)}
                onDrop={handleDrop}
            >
                <div className="flex gap-3">
                    {/* Hidden file input */}
                    <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileSelect}
                        className="hidden"
                        accept=".pdf,.docx,.doc,.xlsx,.xls,.txt"
                    />

                    {/* Type indicator */}
                    {detectedType !== 'unknown' && (
                        <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-xl bg-${config.color}-100`}>
                            {config.icon}
                        </div>
                    )}

                    {/* Input field */}
                    <div className="flex-1 relative">
                        <input
                            type="text"
                            value={input}
                            onChange={(e) => handleInputChange(e.target.value)}
                            placeholder="Paste YouTube, podcast, X thread, or any URL..."
                            disabled={isProcessing}
                            className="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-sm font-medium outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 transition-all"
                        />
                        {detectedType !== 'unknown' && (
                            <span className={`absolute right-3 top-1/2 -translate-y-1/2 text-xs font-bold px-2 py-1 rounded-lg bg-${config.color}-100 text-${config.color}-700`}>
                                {config.label}
                            </span>
                        )}
                    </div>

                    {/* Upload File Button */}
                    <button
                        onClick={() => fileInputRef.current?.click()}
                        disabled={isProcessing || !!input}
                        className="px-4 py-3 bg-white border border-slate-200 text-slate-600 rounded-xl text-sm font-bold hover:bg-slate-50 hover:text-slate-900 disabled:opacity-50 transition-all flex items-center gap-2"
                        title="Upload PDF, Docx, Excel"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path></svg>
                        <span className="hidden sm:inline">Upload</span>
                    </button>

                    {/* Action button */}
                    <button
                        onClick={handleIngest}
                        disabled={isProcessing || detectedType === 'unknown'}
                        className="px-6 py-3 bg-indigo-600 text-white rounded-xl text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-indigo-200"
                    >
                        {isProcessing ? (
                            <span className="flex items-center gap-2">
                                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                                Processing
                            </span>
                        ) : (
                            'Add'
                        )}
                    </button>
                </div>

                {/* Drop zone hint */}
                {dragActive && (
                    <div className="mt-4 p-4 border-2 border-dashed border-indigo-300 rounded-xl text-center text-indigo-600 font-bold">
                        Drop file here to upload
                    </div>
                )}

                {/* Supported sources hint */}
                {stage === 'idle' && !input && (
                    <div className="mt-4 flex items-center gap-4 text-xs text-slate-400">
                        <span>Supports:</span>
                        <span className="flex items-center gap-1">📹 YouTube</span>
                        <span className="flex items-center gap-1">🎙️ Podcasts</span>
                        <span className="flex items-center gap-1">𝕏 Threads</span>
                        <span className="flex items-center gap-1">📄 PDFs</span>
                        <span className="flex items-center gap-1">🌐 Web pages</span>
                    </div>
                )}
            </div>

            {/* Progress Section */}
            {(isProcessing || stage === 'complete') && (
                <div className="px-6 pb-6">
                    {/* Progress bar */}
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div
                            className={`h-full transition-all duration-500 ${stage === 'complete' ? 'bg-green-500' : 'bg-indigo-500'}`}
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                    <p className="text-xs font-bold text-slate-500 mt-2">{statusText}</p>
                </div>
            )}

            {/* Extracted Nodes Preview */}
            {extractedNodes.length > 0 && (
                <div className="px-6 pb-6">
                    <h4 className="text-xs font-black text-slate-400 uppercase tracking-wider mb-3">Extracted Knowledge</h4>
                    <div className="flex flex-wrap gap-2">
                        {extractedNodes.slice(0, 8).map((node, i) => (
                            <div
                                key={node.id || i}
                                className="px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-lg text-xs font-bold flex items-center gap-1"
                            >
                                <span className="w-2 h-2 bg-indigo-400 rounded-full"></span>
                                {node.name}
                                <span className="text-indigo-400 font-normal">({node.type})</span>
                            </div>
                        ))}
                        {extractedNodes.length > 8 && (
                            <span className="px-3 py-1.5 text-xs text-slate-400">+{extractedNodes.length - 8} more</span>
                        )}
                    </div>
                </div>
            )}

            {/* Error display */}
            {error && (
                <div className="px-6 pb-6">
                    <div className="p-4 bg-red-50 border border-red-100 rounded-xl text-red-600 text-sm font-medium flex items-center gap-3">
                        <span className="text-lg">⚠️</span>
                        {error}
                        <button
                            onClick={() => { setError(null); setStage('idle'); }}
                            className="ml-auto text-red-400 hover:text-red-600"
                        >
                            ✕
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
