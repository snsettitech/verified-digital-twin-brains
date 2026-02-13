'use client';

import React, { useState, useRef } from 'react';
import { WizardStep } from '../Wizard';

interface AddContentStepProps {
    onFileUpload?: (files: File[]) => void;
    onUrlSubmit?: (url: string) => void;
    uploadedFiles: File[];
    pendingUrls: string[];
}

export function AddContentStep({
    onFileUpload,
    onUrlSubmit,
    uploadedFiles = [],
    pendingUrls = []
}: AddContentStepProps) {
    const [activeTab, setActiveTab] = useState<'upload' | 'url'>('upload');
    const [url, setUrl] = useState('');
    const [dragActive, setDragActive] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleDrag = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === "dragenter" || e.type === "dragover") {
            setDragActive(true);
        } else if (e.type === "dragleave") {
            setDragActive(false);
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);

        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            const files = Array.from(e.dataTransfer.files);
            onFileUpload?.(files);
        }
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const files = Array.from(e.target.files);
            onFileUpload?.(files);
        }
    };

    const handleUrlSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (url.trim()) {
            onUrlSubmit?.(url.trim());
            setUrl('');
        }
    };

    return (
        <WizardStep
            title="Add Your Content"
            description="Upload documents or add web content to build your twin knowledge"
        >
            <div className="max-w-xl mx-auto">
                {/* Tab Switcher */}
                <div className="flex bg-white/5 rounded-xl p-1 mb-6">
                    <button
                        onClick={() => setActiveTab('upload')}
                        className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 ${activeTab === 'upload'
                                ? 'bg-white/10 text-white'
                                : 'text-slate-400 hover:text-white'
                            }`}
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                        Upload Files
                    </button>
                    <button
                        onClick={() => setActiveTab('url')}
                        className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 ${activeTab === 'url'
                                ? 'bg-white/10 text-white'
                                : 'text-slate-400 hover:text-white'
                            }`}
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                        </svg>
                        Add URL
                    </button>
                </div>

                {/* Upload Tab */}
                {activeTab === 'upload' && (
                    <div
                        onDragEnter={handleDrag}
                        onDragLeave={handleDrag}
                        onDragOver={handleDrag}
                        onDrop={handleDrop}
                        className={`
              relative border-2 border-dashed rounded-2xl p-12 text-center transition-all
              ${dragActive
                                ? 'border-indigo-500 bg-indigo-500/10'
                                : 'border-white/20 hover:border-white/30 bg-white/5'}
            `}
                    >
                        <input
                            ref={fileInputRef}
                            type="file"
                            multiple
                            accept=".pdf,.doc,.docx,.txt,.md"
                            onChange={handleFileChange}
                            className="hidden"
                        />

                        <div className="w-16 h-16 mx-auto mb-4 bg-white/10 rounded-xl flex items-center justify-center">
                            <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                            </svg>
                        </div>

                        <p className="text-white font-medium mb-1">
                            Drag and drop your files here
                        </p>
                        <p className="text-slate-400 text-sm mb-4">
                            or click to browse
                        </p>

                        <button
                            onClick={() => fileInputRef.current?.click()}
                            className="px-4 py-2 bg-white/10 hover:bg-white/20 text-white text-sm font-medium rounded-lg transition-colors"
                        >
                            Browse Files
                        </button>

                        <p className="mt-4 text-slate-500 text-xs">
                            Supports PDF, DOC, DOCX, TXT, MD • Max 50MB per file
                        </p>
                    </div>
                )}

                {/* URL Tab */}
                {activeTab === 'url' && (
                    <form onSubmit={handleUrlSubmit} className="space-y-4">
                        <div className="flex gap-3">
                            <input
                                type="url"
                                value={url}
                                onChange={(e) => setUrl(e.target.value)}
                                placeholder="https://example.com/article"
                                className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                            />
                            <button
                                type="submit"
                                className="px-6 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold rounded-xl transition-all"
                            >
                                Add
                            </button>
                        </div>

                        <div className="grid grid-cols-3 gap-3">
                            {['YouTube', 'Blog Post', 'Twitter/X'].map((type) => (
                                <div key={type} className="p-3 bg-white/5 border border-white/10 rounded-xl text-center">
                                    <span className="text-slate-400 text-sm">{type}</span>
                                </div>
                            ))}
                        </div>
                    </form>
                )}

                {/* Uploaded Items List */}
                {(uploadedFiles.length > 0 || pendingUrls.length > 0) && (
                    <div className="mt-6 space-y-2">
                        <div className="text-sm font-medium text-slate-300 mb-2">Added Content</div>
                        {uploadedFiles.map((file, index) => (
                            <div key={index} className="flex items-center gap-3 p-3 bg-white/5 rounded-xl">
                                <div className="w-8 h-8 bg-emerald-500/20 rounded-lg flex items-center justify-center">
                                    <svg className="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                    </svg>
                                </div>
                                <div className="flex-1">
                                    <div className="text-white text-sm font-medium">{file.name}</div>
                                    <div className="text-slate-500 text-xs">{(file.size / 1024 / 1024).toFixed(2)} MB</div>
                                </div>
                                <svg className="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                </svg>
                            </div>
                        ))}
                        {pendingUrls.map((pendingUrl, index) => (
                            <div key={index} className="flex items-center gap-3 p-3 bg-white/5 rounded-xl">
                                <div className="w-8 h-8 bg-blue-500/20 rounded-lg flex items-center justify-center">
                                    <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                                    </svg>
                                </div>
                                <div className="flex-1 truncate">
                                    <div className="text-white text-sm font-medium truncate">{pendingUrl}</div>
                                </div>
                                <svg className="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                </svg>
                            </div>
                        ))}
                    </div>
                )}

                {/* Skip note */}
                <p className="text-center text-slate-500 text-sm mt-6">
                    You can always add more content later from your dashboard
                </p>
            </div>
        </WizardStep>
    );
}

export default AddContentStep;
