'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';
import { API_ENDPOINTS } from '@/lib/constants';
import { resolveApiBaseUrl } from '@/lib/api';
import { ingestUrlWithFallback, uploadFileWithFallback } from '@/lib/ingestionApi';
import { useJobPoller } from '@/lib/hooks/useJobPoller';

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
type IngestionStage = 'idle' | 'detecting' | 'ingesting' | 'polling' | 'extracting' | 'complete' | 'error';
type SourceLabel = 'identity' | 'knowledge' | 'policies';

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

// Polling stage progress mapping
const POLLING_PROGRESS = {
    queued: 30,
    processing: 50,
    complete: 75,
    failed: 0,
    needs_attention: 40,
};

export default function UnifiedIngestion({ twinId, onComplete, onError }: UnifiedIngestionProps) {
    const supabase = getSupabaseClient();
    const backendUrl = resolveApiBaseUrl();
    const [input, setInput] = useState('');
    const [detectedType, setDetectedType] = useState<SourceType>('unknown');
    const [stage, setStage] = useState<IngestionStage>('idle');
    const [progress, setProgress] = useState(0);
    const [statusText, setStatusText] = useState('');
    const [extractedNodes, setExtractedNodes] = useState<ExtractedNode[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [dragActive, setDragActive] = useState(false);
    const [currentJobId, setCurrentJobId] = useState<string | null>(null);
    const [currentSourceId, setCurrentSourceId] = useState<string | null>(null);
    const [sourceLabel, setSourceLabel] = useState<SourceLabel>('knowledge');
    const [identityConfirmed, setIdentityConfirmed] = useState(false);
    const [labelError, setLabelError] = useState<string | null>(null);
    const fileInputRef = React.useRef<HTMLInputElement>(null);

    // Get auth token
    const getAuthToken = useCallback(async () => {
        const { data: { session } } = await supabase.auth.getSession();
        return session?.access_token || null;
    }, [supabase]);

    // Job poller for URL ingestion
    const [token, setToken] = useState<string | null>(null);
    const { 
        job, 
        isPolling, 
        error: pollError, 
        isComplete, 
        isSuccessful,
        startPolling,
        stopPolling,
        retryJob,
    } = useJobPoller({
        jobId: currentJobId,
        token,
        debug: process.env.NODE_ENV === 'development',
    });

    // Update token on mount
    useEffect(() => {
        getAuthToken().then(setToken);
    }, [getAuthToken]);

    // Handle job status changes
    useEffect(() => {
        if (!job) return;

        // Update progress based on job status
        const jobProgress = POLLING_PROGRESS[job.status] || 30;
        setProgress(jobProgress);
        
        // Update status text
        const statusMessages: Record<string, string> = {
            queued: `Queued for processing...`,
            processing: `Processing content (${job.metadata?.provider || detectedType})...`,
            complete: `Processing complete! Extracting knowledge...`,
            failed: `Processing failed: ${job.error_message || 'Unknown error'}`,
            needs_attention: `Processing needs attention...`,
        };
        setStatusText(statusMessages[job.status] || `Status: ${job.status}`);

        // When job completes, trigger extraction
        if (isComplete) {
            if (isSuccessful && currentSourceId) {
                setStage('extracting');
                extractNodes(currentSourceId);
            } else {
                setStage('error');
                setError(job?.error_message || 'Job processing failed');
                onError?.(job?.error_message || 'Job processing failed');
            }
        }
    }, [job, isComplete, isSuccessful, currentSourceId, detectedType, onError]);

    // Handle polling errors
    useEffect(() => {
        if (pollError) {
            setError(pollError);
            setStage('error');
            onError?.(pollError);
        }
    }, [pollError, onError]);

    const resetState = () => {
        setInput('');
        setDetectedType('unknown');
        setStage('idle');
        setProgress(0);
        setExtractedNodes([]);
        setCurrentJobId(null);
        setCurrentSourceId(null);
        setError(null);
        setLabelError(null);
        setSourceLabel('knowledge');
        setIdentityConfirmed(false);
        stopPolling();
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    const canUseIdentityLabel = sourceLabel !== 'identity' || identityConfirmed;

    const ensureLabelReady = (): boolean => {
        if (!canUseIdentityLabel) {
            setLabelError('Identity label requires explicit confirmation.');
            return false;
        }
        setLabelError(null);
        return true;
    };

    // Extract nodes from processed source
    const extractNodes = async (sourceId: string) => {
        if (!token) return;

        try {
            setStage('extracting');
            setProgress(80);

            const extractResponse = await fetch(
                `${backendUrl}${API_ENDPOINTS.INGEST_EXTRACT_NODES(sourceId)}`,
                {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ max_chunks: 5 }),
                }
            );

            if (extractResponse.ok) {
                const extractResult = await extractResponse.json();
                setExtractedNodes(extractResult.nodes || []);
                setProgress(100);
                setStatusText(`Done! ${extractResult.nodes_created || 0} nodes, ${extractResult.edges_created || 0} edges extracted`);
                setStage('complete');

                onComplete?.({
                    source_id: sourceId,
                    status: 'complete',
                    nodes_created: extractResult.nodes_created,
                    edges_created: extractResult.edges_created,
                });
            } else {
                // Extraction failed but ingestion succeeded
                setProgress(100);
                setStatusText('Content saved (extraction pending)');
                setStage('complete');
                onComplete?.({ source_id: sourceId, status: 'live' });
            }

            // Reset input after success
            setTimeout(() => {
                resetState();
            }, 3000);
        } catch (err: any) {
            setError(err.message || 'Extraction failed');
            setStage('error');
            onError?.(err.message);
        }
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

    // Main URL ingestion flow with polling
    const handleIngest = async () => {
        if (!input.trim() || detectedType === 'unknown') return;
        if (!ensureLabelReady()) return;

        const currentToken = await getAuthToken();
        if (!currentToken) {
            setError('Not authenticated');
            return;
        }
        setToken(currentToken);

        setStage('ingesting');
        setProgress(20);
        setStatusText(`Submitting ${sourceConfig[detectedType].label}...`);
        setExtractedNodes([]);

        try {
            // Step 1: Submit ingestion request
            const result =
                detectedType === 'url'
                    ? await ingestUrlWithFallback({
                          backendUrl,
                          twinId,
                          url: input.trim(),
                          label: sourceLabel,
                          identityConfirmed,
                          headers: { 'Authorization': `Bearer ${currentToken}` },
                      })
                    : await (async () => {
                          const endpoint = `${backendUrl}${sourceConfig[detectedType].endpoint}/${twinId}`;
                          const response = await fetch(endpoint, {
                              method: 'POST',
                              headers: {
                                  'Authorization': `Bearer ${currentToken}`,
                                  'Content-Type': 'application/json',
                              },
                              body: JSON.stringify({ url: input.trim() }),
                          });

                          if (!response.ok) {
                              const data = await response.json();
                              throw new Error(data.detail || 'Ingestion failed');
                          }

                          return response.json();
                      })();
            const jobId = typeof result.job_id === 'string' ? result.job_id : null;
            const sourceId = typeof result.source_id === 'string' ? result.source_id : null;
            if (!jobId || !sourceId) {
                throw new Error('Ingestion response missing job details');
            }

            setCurrentJobId(jobId);
            setCurrentSourceId(sourceId);
            
            // Step 2: Start polling for job completion
            setStage('polling');
            setProgress(30);
            setStatusText('Waiting for processing to complete...');
            startPolling(jobId);

        } catch (err: any) {
            setError(err.message || 'Something went wrong');
            setStage('error');
            onError?.(err.message);
        }
    };

    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        if (!ensureLabelReady()) return;

        const currentToken = await getAuthToken();
        if (!currentToken) {
            setError('Not authenticated');
            return;
        }

        setDetectedType('file');
        setStage('ingesting');
        setProgress(20);
        setStatusText(`Uploading ${file.name}... (this may take up to 2 minutes)`);

        // 3-minute timeout for large files
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 180000);

        try {
            const result = await uploadFileWithFallback({
                backendUrl,
                twinId,
                file,
                label: sourceLabel,
                identityConfirmed,
                headers: { 'Authorization': `Bearer ${currentToken}` },
                signal: controller.signal,
            });
            clearTimeout(timeoutId);
            const sourceId = typeof result.source_id === 'string' ? result.source_id : '';
            const statusValue = typeof result.status === 'string' ? result.status : 'live';
            const messageValue = typeof result.message === 'string' ? result.message : 'File already exists';
            
            // Handle duplicate detection
            if (result.duplicate) {
                setProgress(100);
                setStatusText(messageValue);
                setStage('complete');
                onComplete?.({ source_id: sourceId, status: statusValue });
                
                setTimeout(() => resetState(), 2000);
                return;
            }
            
            // For files, processing is synchronous in the endpoint
            // But we still poll to ensure indexing is complete
            if (typeof result.job_id === 'string') {
                setCurrentJobId(result.job_id);
                setCurrentSourceId(sourceId || null);
                setToken(currentToken);
                setStage('polling');
                startPolling(result.job_id);
            } else {
                // Fallback: direct extraction
                setProgress(100);
                setStatusText('File uploaded and indexed!');
                setStage('complete');
                onComplete?.({ source_id: sourceId, status: 'live' });
                
                setTimeout(() => resetState(), 2000);
            }

        } catch (err: any) {
            setError(err.message);
            setStage('error');
            resetState();
        } finally {
            clearTimeout(timeoutId);
        }
    };

    // File drop handling
    const handleDrop = async (e: React.DragEvent) => {
        e.preventDefault();
        setDragActive(false);

        const file = e.dataTransfer.files[0];
        if (!file) return;
        if (!ensureLabelReady()) return;

        const currentToken = await getAuthToken();
        if (!currentToken) {
            setError('Not authenticated');
            return;
        }

        setDetectedType('file');
        setStage('ingesting');
        setProgress(20);
        setStatusText(`Uploading ${file.name}... (this may take up to 2 minutes)`);

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 180000);

        try {
            const result = await uploadFileWithFallback({
                backendUrl,
                twinId,
                file,
                label: sourceLabel,
                identityConfirmed,
                headers: { 'Authorization': `Bearer ${currentToken}` },
                signal: controller.signal,
            });
            clearTimeout(timeoutId);
            const sourceId = typeof result.source_id === 'string' ? result.source_id : '';
            const statusValue = typeof result.status === 'string' ? result.status : 'live';
            const messageValue = typeof result.message === 'string' ? result.message : 'File already exists';
            
            // Handle duplicate detection
            if (result.duplicate) {
                setProgress(100);
                setStatusText(messageValue);
                setStage('complete');
                onComplete?.({ source_id: sourceId, status: statusValue });
                
                setTimeout(() => resetState(), 2000);
                return;
            }
            
            // For files, poll if job_id returned
            if (typeof result.job_id === 'string') {
                setCurrentJobId(result.job_id);
                setCurrentSourceId(sourceId || null);
                setToken(currentToken);
                setStage('polling');
                startPolling(result.job_id);
            } else {
                setProgress(100);
                setStatusText('File uploaded and indexed!');
                setStage('complete');
                onComplete?.({ source_id: sourceId, status: 'live' });
                
                setTimeout(() => resetState(), 2000);
            }

        } catch (err: any) {
            setError(err.message);
            setStage('error');
        } finally {
            clearTimeout(timeoutId);
        }
    };

    // Cancel ongoing ingestion
    const handleCancel = () => {
        stopPolling();
        resetState();
    };

    // Retry failed job
    const handleRetry = async () => {
        if (currentJobId) {
            setStage('polling');
            setError(null);
            const success = await retryJob();
            if (!success) {
                setError('Failed to retry job');
                setStage('error');
            }
        }
    };

    const config = sourceConfig[detectedType];
    const isProcessing = stage === 'ingesting' || stage === 'polling' || stage === 'extracting' || stage === 'detecting';

    return (
        <div className="bg-white rounded-[2rem] border border-slate-200 shadow-sm overflow-hidden">
            {/* Header */}
            <div className="p-6 border-b border-slate-100">
                <h3 className="text-lg font-black text-slate-800">Add Knowledge</h3>
                <p className="text-sm text-slate-500 mt-1">Paste a URL or drop a file to ingest and index knowledge</p>
            </div>

            {/* Input Zone */}
            <div
                className={`p-6 transition-colors ${dragActive ? 'bg-indigo-50' : 'bg-slate-50/50'}`}
                onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
                onDragLeave={() => setDragActive(false)}
                onDrop={handleDrop}
            >
                <div className="mb-4 rounded-xl border border-slate-200 bg-white p-3">
                    <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Required Label</div>
                    <div className="mt-2 grid grid-cols-3 gap-2">
                        {([
                            { value: 'identity', label: 'Identity' },
                            { value: 'knowledge', label: 'Knowledge' },
                            { value: 'policies', label: 'Policies' },
                        ] as const).map((opt) => (
                            <button
                                key={opt.value}
                                onClick={() => {
                                    setSourceLabel(opt.value);
                                    if (opt.value !== 'identity') setIdentityConfirmed(false);
                                    setLabelError(null);
                                }}
                                className={`rounded-lg border px-3 py-2 text-xs font-semibold transition-all ${
                                    sourceLabel === opt.value
                                        ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                                        : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                                }`}
                            >
                                {opt.label}
                            </button>
                        ))}
                    </div>
                    {sourceLabel === 'identity' && (
                        <label className="mt-2 flex items-start gap-2 text-xs text-slate-600">
                            <input
                                type="checkbox"
                                checked={identityConfirmed}
                                onChange={(e) => setIdentityConfirmed(e.target.checked)}
                                className="mt-0.5"
                            />
                            <span>
                                I confirm this source is safe for identity answers and does not include confidential data.
                            </span>
                        </label>
                    )}
                    {labelError ? <div className="mt-2 text-xs text-rose-600">{labelError}</div> : null}
                </div>

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
                                {stage === 'polling' ? 'Waiting...' : 'Processing'}
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
            {(isProcessing || stage === 'complete' || stage === 'error') && (
                <div className="px-6 pb-6">
                    {/* Progress bar */}
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div
                            className={`h-full transition-all duration-500 ${stage === 'complete' ? 'bg-green-500' : stage === 'error' ? 'bg-red-500' : 'bg-indigo-500'}`}
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                    <div className="flex items-center justify-between mt-2">
                        <p className="text-xs font-bold text-slate-500">{statusText}</p>
                        {isPolling && (
                            <button
                                onClick={handleCancel}
                                className="text-xs text-slate-400 hover:text-slate-600 underline"
                            >
                                Cancel
                            </button>
                        )}
                    </div>
                    
                    {/* Job status details */}
                    {stage === 'polling' && job && (
                        <div className="mt-2 text-xs text-slate-400">
                            Status: <span className="capitalize">{job.status}</span>
                            {job.metadata?.chunks_created && (
                                <span className="ml-2">• {job.metadata.chunks_created} chunks indexed</span>
                            )}
                        </div>
                    )}
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
                    <div className="p-4 bg-red-50 border border-red-100 rounded-xl text-red-600 text-sm font-medium">
                        <div className="flex items-center gap-3">
                            <span className="text-lg">⚠️</span>
                            <span className="flex-1">{error}</span>
                        </div>
                        {currentJobId && stage === 'error' && (
                            <div className="mt-3 flex gap-2">
                                <button
                                    onClick={handleRetry}
                                    className="px-3 py-1.5 bg-red-100 text-red-700 rounded-lg text-xs font-bold hover:bg-red-200"
                                >
                                    Retry Job
                                </button>
                                <button
                                    onClick={() => { setError(null); setStage('idle'); }}
                                    className="px-3 py-1.5 text-red-400 hover:text-red-600 text-xs"
                                >
                                    Dismiss
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
