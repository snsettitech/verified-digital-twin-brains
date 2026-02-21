'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/Card';

interface SourceItem {
  type: 'export' | 'link' | 'paste';
  value: string;
  category?: string;
  file?: File;
}

interface StepAddSourcesProps {
  twinId: string | null;
  initialUrls?: string[];
  onSubmit: (sources: SourceItem[]) => void;
  onBack: () => void;
}

const SOURCE_CATEGORIES = [
  { id: 'social', label: 'Social', examples: 'LinkedIn, X, YouTube', icon: '👥' },
  { id: 'dev', label: 'Dev/Portfolio', examples: 'GitHub, personal site', icon: '💻' },
  { id: 'writing', label: 'Writing', examples: 'Medium, Substack, blog', icon: '✍️' },
  { id: 'press', label: 'Press', examples: 'Articles, podcasts, interviews', icon: '📰' },
];

export function StepAddSources({ twinId, initialUrls = [], onSubmit, onBack }: StepAddSourcesProps) {
  const [activeTab, setActiveTab] = useState<'exports' | 'links' | 'paste'>('exports');
  const [files, setFiles] = useState<File[]>([]);
  const [links, setLinks] = useState<{ url: string; category: string }[]>(
    initialUrls.map(url => ({ url, category: 'social' }))
  );
  const [pasteContent, setPasteContent] = useState('');
  const [pasteTitle, setPasteTitle] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleAddLink = () => {
    setLinks([...links, { url: '', category: 'social' }]);
  };

  const handleUpdateLink = (index: number, field: 'url' | 'category', value: string) => {
    const newLinks = [...links];
    newLinks[index] = { ...newLinks[index], [field]: value };
    setLinks(newLinks);
  };

  const handleRemoveLink = (index: number) => {
    setLinks(links.filter((_, i) => i !== index));
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles([...files, ...Array.from(e.target.files)]);
    }
  };

  const handleRemoveFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    
    const sources: SourceItem[] = [];
    
    // Add files
    files.forEach(file => {
      sources.push({ type: 'export', value: file.name, file });
    });
    
    // Add links
    links.filter(l => l.url.trim()).forEach(link => {
      sources.push({ type: 'link', value: link.url, category: link.category });
    });
    
    // Add paste
    if (pasteContent.trim()) {
      sources.push({ type: 'paste', value: pasteContent, category: pasteTitle || 'Pasted Content' });
    }
    
    await onSubmit(sources);
    setIsSubmitting(false);
  };

  const hasContent = files.length > 0 || links.some(l => l.url.trim()) || pasteContent.trim();
  const validLinks = links.filter(l => l.url.trim() && l.url.startsWith('http')).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <h2 className="text-2xl font-bold text-white mb-2">Add Your Sources</h2>
        <p className="text-slate-400">
          Drop everything you have—exports, links, or paste text. We'll organize it.
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2">
        {(['exports', 'links', 'paste'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-3 rounded-xl font-medium transition-colors ${
              activeTab === tab
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
            }`}
          >
            {tab === 'exports' && '📁 Exports'}
            {tab === 'links' && '🔗 Links'}
            {tab === 'paste' && '📋 Paste'}
          </button>
        ))}
      </div>

      {/* Exports Tab */}
      {activeTab === 'exports' && (
        <Card className="p-6 bg-slate-900 border-slate-700">
          <div className="text-center py-8">
            <div className="w-16 h-16 bg-indigo-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-3xl">📁</span>
            </div>
            <h3 className="font-semibold text-white mb-2">Upload Exports</h3>
            <p className="text-sm text-slate-400 mb-4">
              LinkedIn archive, Twitter export, PDFs, or HTML files.<br />
              <span className="text-amber-400">Most reliable source type.</span>
            </p>
            <input
              type="file"
              multiple
              accept=".zip,.pdf,.html,.csv,.json"
              onChange={handleFileChange}
              className="hidden"
              id="file-upload"
            />
            <label
              htmlFor="file-upload"
              className="inline-block px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-medium cursor-pointer transition-colors"
            >
              Choose Files
            </label>
          </div>

          {files.length > 0 && (
            <div className="mt-6 space-y-2">
              <h4 className="text-sm font-medium text-slate-300 mb-3">Selected Files ({files.length})</h4>
              {files.map((file, idx) => (
                <div key={idx} className="flex items-center justify-between bg-slate-800 p-3 rounded-lg">
                  <div className="flex items-center gap-3">
                    <span className="text-xl">📄</span>
                    <div>
                      <p className="text-sm text-white">{file.name}</p>
                      <p className="text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB</p>
                    </div>
                  </div>
                  <button
                    onClick={() => handleRemoveFile(idx)}
                    className="text-slate-500 hover:text-red-400 transition-colors"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Links Tab */}
      {activeTab === 'links' && (
        <Card className="p-6 bg-slate-900 border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-white">Web Links</h3>
            <span className="text-sm text-slate-500">
              {validLinks} valid {validLinks === 1 ? 'link' : 'links'}
            </span>
          </div>

          {/* Category Quick Add */}
          <div className="grid grid-cols-2 gap-2 mb-4">
            {SOURCE_CATEGORIES.map((cat) => (
              <button
                key={cat.id}
                onClick={() => {
                  setLinks([...links, { url: '', category: cat.id }]);
                }}
                className="p-3 bg-slate-800 hover:bg-slate-700 rounded-lg text-left transition-colors"
              >
                <span className="text-lg mr-2">{cat.icon}</span>
                <span className="text-sm font-medium text-white">{cat.label}</span>
                <p className="text-xs text-slate-500 mt-0.5">{cat.examples}</p>
              </button>
            ))}
          </div>

          {/* Link Inputs */}
          <div className="space-y-3">
            {links.map((link, idx) => (
              <div key={idx} className="flex gap-2">
                <select
                  value={link.category}
                  onChange={(e) => handleUpdateLink(idx, 'category', e.target.value)}
                  className="w-32 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-indigo-500"
                >
                  {SOURCE_CATEGORIES.map((cat) => (
                    <option key={cat.id} value={cat.id}>{cat.label}</option>
                  ))}
                </select>
                <input
                  type="url"
                  value={link.url}
                  onChange={(e) => handleUpdateLink(idx, 'url', e.target.value)}
                  placeholder="https://..."
                  className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
                <button
                  onClick={() => handleRemoveLink(idx)}
                  className="px-3 text-slate-500 hover:text-red-400 transition-colors"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>

          <button
            onClick={handleAddLink}
            className="mt-4 text-indigo-400 hover:text-indigo-300 text-sm font-medium"
          >
            + Add another link
          </button>
        </Card>
      )}

      {/* Paste Tab */}
      {activeTab === 'paste' && (
        <Card className="p-6 bg-slate-900 border-slate-700">
          <div className="mb-4">
            <h3 className="font-semibold text-white mb-1">Paste Content</h3>
            <p className="text-sm text-slate-400">
              About page, resume, speaker bio, or any text that describes you.
            </p>
          </div>

          <input
            type="text"
            value={pasteTitle}
            onChange={(e) => setPasteTitle(e.target.value)}
            placeholder="Title (e.g., My LinkedIn About)"
            className="w-full mb-3 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />

          <textarea
            value={pasteContent}
            onChange={(e) => setPasteContent(e.target.value)}
            placeholder="Paste your content here..."
            rows={8}
            className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 resize-none"
          />

          <div className="mt-3 flex items-center justify-between text-sm">
            <span className="text-slate-500">
              {pasteContent.length.toLocaleString()} characters
            </span>
            <span className="text-slate-500">
              Max 100,000 characters
            </span>
          </div>
        </Card>
      )}

      {/* Privacy Controls */}
      <Card className="p-4 bg-slate-900/50 border-slate-700">
        <div className="flex items-start gap-3">
          <span className="text-amber-400 text-lg">🔒</span>
          <div>
            <h4 className="font-medium text-slate-300 text-sm">Privacy Controls</h4>
            <p className="text-xs text-slate-500 mt-1">
              Raw exports are processed and then deleted. Only extracted claims are stored.
              You can remove any source after upload.
            </p>
          </div>
        </div>
      </Card>

      {/* Actions */}
      <div className="flex gap-3 pt-4">
        <button
          onClick={onBack}
          className="px-6 py-3 border border-slate-700 hover:bg-slate-800 text-slate-300 rounded-xl font-medium transition-colors"
        >
          ← Back
        </button>
        
        <button
          onClick={handleSubmit}
          disabled={!hasContent || isSubmitting}
          className="flex-1 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-semibold transition-colors flex items-center justify-center gap-2"
        >
          {isSubmitting ? (
            <>
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <span>🚀</span>
              Build My Twin
            </>
          )}
        </button>
      </div>

      <p className="text-center text-sm text-slate-500">
        You can always add more sources later in your portal.
      </p>
    </div>
  );
}
