'use client';

import React, { useState, useRef } from 'react';

interface Step2KnowledgeProps {
  uploadedFiles: Array<{ file: File; label: 'identity' | 'knowledge' | 'policies'; identityConfirmed?: boolean }>;
  pendingUrls: Array<{ url: string; label: 'identity' | 'knowledge' | 'policies'; identityConfirmed?: boolean }>;
  faqs: { question: string; answer: string }[];
  onFileUpload: (files: Array<{ file: File; label: 'identity' | 'knowledge' | 'policies'; identityConfirmed?: boolean }>) => void;
  onUrlSubmit: (url: { url: string; label: 'identity' | 'knowledge' | 'policies'; identityConfirmed?: boolean }) => void;
  onFaqsChange: (faqs: { question: string; answer: string }[]) => void;
  onRemoveFile: (index: number) => void;
  onRemoveUrl: (index: number) => void;
}

const SUGGESTED_FAQS = [
  'What are your top 3 productivity tips?',
  'How do you handle difficult decisions?',
  'What advice would you give to someone starting out?',
  'What are your core values?',
];

export default function Step2Knowledge({
  uploadedFiles,
  pendingUrls,
  faqs,
  onFileUpload,
  onUrlSubmit,
  onFaqsChange,
  onRemoveFile,
  onRemoveUrl,
}: Step2KnowledgeProps) {
  const [urlInput, setUrlInput] = useState('');
  const [activeTab, setActiveTab] = useState<'upload' | 'faqs'>('upload');
  const [newQuestion, setNewQuestion] = useState('');
  const [newAnswer, setNewAnswer] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [sourceLabel, setSourceLabel] = useState<'identity' | 'knowledge' | 'policies'>('knowledge');
  const [identityConfirmed, setIdentityConfirmed] = useState(false);
  const [labelError, setLabelError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const canUseIdentityLabel = sourceLabel !== 'identity' || identityConfirmed;

  const ensureLabelReady = (): boolean => {
    if (!canUseIdentityLabel) {
      setLabelError('Identity label requires confirmation before upload.');
      return false;
    }
    setLabelError(null);
    return true;
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (!ensureLabelReady()) return;
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      onFileUpload(files.map((file) => ({ file, label: sourceLabel, identityConfirmed })));
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!ensureLabelReady()) return;
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      onFileUpload(files.map((file) => ({ file, label: sourceLabel, identityConfirmed })));
    }
  };

  const handleUrlAdd = () => {
    if (!ensureLabelReady()) return;
    if (urlInput && !pendingUrls.some((entry) => entry.url === urlInput)) {
      onUrlSubmit({ url: urlInput, label: sourceLabel, identityConfirmed });
      setUrlInput('');
    }
  };

  const handleAddFaq = () => {
    if (newQuestion && newAnswer) {
      onFaqsChange([...faqs, { question: newQuestion, answer: newAnswer }]);
      setNewQuestion('');
      setNewAnswer('');
    }
  };

  const handleRemoveFaq = (index: number) => {
    onFaqsChange(faqs.filter((_, i) => i !== index));
  };

  const addSuggestedFaq = (question: string) => {
    setNewQuestion(question);
  };

  const totalItems = uploadedFiles.length + pendingUrls.length + faqs.length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center mb-8">
        <h2 className="text-3xl font-bold text-white mb-2">Add Knowledge</h2>
        <p className="text-slate-400">Feed your twin with content and seed Q&As</p>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 p-1 bg-white/5 rounded-xl mb-6">
        <button
          onClick={() => setActiveTab('upload')}
          className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all ${
            activeTab === 'upload'
              ? 'bg-indigo-600 text-white'
              : 'text-slate-400 hover:text-white hover:bg-white/5'
          }`}
        >
          📚 Content ({uploadedFiles.length + pendingUrls.length})
        </button>
        <button
          onClick={() => setActiveTab('faqs')}
          className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all ${
            activeTab === 'faqs'
              ? 'bg-indigo-600 text-white'
              : 'text-slate-400 hover:text-white hover:bg-white/5'
          }`}
        >
          ❓ Q&A ({faqs.length})
        </button>
      </div>

      {/* Upload Tab */}
      {activeTab === 'upload' && (
        <div className="space-y-6 animate-fadeIn">
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <label className="block text-sm font-medium text-slate-300 mb-2">Required label</label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { value: 'identity', label: 'Identity' },
                { value: 'knowledge', label: 'Knowledge' },
                { value: 'policies', label: 'Policies' },
              ].map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => {
                    setSourceLabel(opt.value as 'identity' | 'knowledge' | 'policies');
                    if (opt.value !== 'identity') setIdentityConfirmed(false);
                    setLabelError(null);
                  }}
                  className={`rounded-lg border px-3 py-2 text-xs font-semibold transition-all ${
                    sourceLabel === opt.value
                      ? 'border-indigo-500 bg-indigo-500/10 text-white'
                      : 'border-white/10 bg-white/5 text-slate-300 hover:bg-white/10'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            {sourceLabel === 'identity' && (
              <label className="mt-3 flex items-start gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={identityConfirmed}
                  onChange={(e) => setIdentityConfirmed(e.target.checked)}
                  className="mt-0.5"
                />
                <span>
                  I confirm this source can define identity answers and has no confidential or private-only data.
                </span>
              </label>
            )}
            {labelError ? <p className="mt-2 text-xs text-rose-400">{labelError}</p> : null}
          </div>

          {/* File Drop Zone */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
              isDragging
                ? 'border-indigo-500 bg-indigo-500/10'
                : 'border-white/20 hover:border-white/40 bg-white/5'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              onChange={handleFileSelect}
              className="hidden"
              accept=".pdf,.txt,.md,.doc,.docx"
            />
            <div className="w-16 h-16 mx-auto mb-4 bg-white/10 rounded-2xl flex items-center justify-center">
              <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            <p className="text-white font-medium mb-1">Drop files or click to upload</p>
            <p className="text-slate-500 text-sm">PDF, TXT, MD, DOC up to 10MB each</p>
          </div>

          {/* File List */}
          {uploadedFiles.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-slate-300">Files to upload ({uploadedFiles.length})</p>
              <div className="space-y-2 max-h-32 overflow-y-auto">
                {uploadedFiles.map((entry, index) => (
                  <div key={index} className="flex items-center gap-3 p-3 bg-white/5 rounded-xl">
                    <span className="text-xl">📄</span>
                    <span className="flex-1 text-sm text-white truncate">{entry.file.name}</span>
                    <span className="rounded-full bg-indigo-500/20 px-2 py-0.5 text-[10px] font-bold uppercase text-indigo-200">
                      {entry.label}
                    </span>
                    <span className="text-xs text-slate-500">{(entry.file.size / 1024 / 1024).toFixed(1)} MB</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onRemoveFile(index);
                      }}
                      className="p-1 text-slate-500 hover:text-red-400 transition-colors"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* URL Input */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Or add URLs</label>
            <div className="flex gap-2">
              <input
                type="url"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleUrlAdd()}
                placeholder="https://example.com/article"
                className="flex-1 px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
              <button
                onClick={handleUrlAdd}
                disabled={!urlInput}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-medium transition-colors"
              >
                Add
              </button>
            </div>
          </div>

          {/* URL List */}
          {pendingUrls.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-slate-300">URLs to ingest ({pendingUrls.length})</p>
              <div className="space-y-2">
                {pendingUrls.map((entry, index) => (
                  <div key={index} className="flex items-center gap-3 p-3 bg-white/5 rounded-xl">
                    <span className="text-xl">🔗</span>
                    <span className="flex-1 text-sm text-white truncate">{entry.url}</span>
                    <span className="rounded-full bg-indigo-500/20 px-2 py-0.5 text-[10px] font-bold uppercase text-indigo-200">
                      {entry.label}
                    </span>
                    <button
                      onClick={() => onRemoveUrl(index)}
                      className="p-1 text-slate-500 hover:text-red-400 transition-colors"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* FAQs Tab */}
      {activeTab === 'faqs' && (
        <div className="space-y-6 animate-fadeIn">
          {/* Suggested Questions */}
          {faqs.length === 0 && (
            <div>
              <p className="text-sm font-medium text-slate-300 mb-2">Quick start suggestions</p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTED_FAQS.map((q) => (
                  <button
                    key={q}
                    onClick={() => addSuggestedFaq(q)}
                    className="px-3 py-1.5 bg-white/5 hover:bg-white/10 text-slate-300 text-sm rounded-lg transition-colors text-left"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Add FAQ Form */}
          <div className="space-y-3">
            <input
              type="text"
              value={newQuestion}
              onChange={(e) => setNewQuestion(e.target.value)}
              placeholder="Question"
              className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
            <textarea
              value={newAnswer}
              onChange={(e) => setNewAnswer(e.target.value)}
              placeholder="Answer"
              rows={3}
              className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 resize-none"
            />
            <button
              onClick={handleAddFaq}
              disabled={!newQuestion || !newAnswer}
              className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-medium transition-colors"
            >
              Add Q&A Pair
            </button>
          </div>

          {/* FAQ List */}
          {faqs.length > 0 && (
            <div className="space-y-3 max-h-64 overflow-y-auto">
              <p className="text-sm font-medium text-slate-300">Added Q&A ({faqs.length})</p>
              {faqs.map((faq, index) => (
                <div key={index} className="p-4 bg-white/5 rounded-xl border border-white/10">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-medium text-white text-sm">{faq.question}</p>
                    <button
                      onClick={() => handleRemoveFaq(index)}
                      className="p-1 text-slate-500 hover:text-red-400 transition-colors shrink-0"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                  <p className="text-slate-400 text-sm mt-1 line-clamp-2">{faq.answer}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Summary */}
      <div className="pt-4 border-t border-white/10">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-slate-400 text-sm">Knowledge items added</p>
            <p className="text-white font-medium">{totalItems} items</p>
          </div>
          {totalItems > 0 && (
            <span className="text-emerald-400 text-sm">✓ Ready to train</span>
          )}
        </div>
      </div>
    </div>
  );
}
