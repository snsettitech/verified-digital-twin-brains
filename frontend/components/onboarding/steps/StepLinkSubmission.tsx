'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/Card';

interface StepLinkSubmissionProps {
  twinId: string | null;
  onSubmit: (urls: string[], files: File[]) => void;
}

export function StepLinkSubmission({ twinId, onSubmit }: StepLinkSubmissionProps) {
  const [urls, setUrls] = useState<string[]>(['']);
  const [files, setFiles] = useState<File[]>([]);
  const [mode, setMode] = useState<'urls' | 'files'>('urls');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!twinId) return;
    
    setIsSubmitting(true);
    const validUrls = urls.filter(u => u.trim());
    
    try {
      if (mode === 'urls' && validUrls.length > 0) {
        // Mode C: Web fetch
        const response = await fetch('/api/persona/link-compile/jobs/mode-c', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            twin_id: twinId, 
            urls: validUrls 
          }),
        });
        
        if (!response.ok) {
          const error = await response.json();
          alert(error.detail || 'Failed to submit URLs');
          return;
        }
      } else if (mode === 'files' && files.length > 0) {
        // Mode A: File upload
        const formData = new FormData();
        formData.append('twin_id', twinId);
        files.forEach(f => formData.append('files', f));
        
        const response = await fetch('/api/persona/link-compile/jobs/mode-a', {
          method: 'POST',
          body: formData,
        });
        
        if (!response.ok) {
          const error = await response.json();
          alert(error.detail || 'Failed to upload files');
          return;
        }
      }
      
      onSubmit(validUrls, files);
    } catch (e) {
      alert('Submission failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const canSubmit = twinId && (
    (mode === 'urls' && urls.some(u => u.trim())) ||
    (mode === 'files' && files.length > 0)
  );

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2">Submit Your Content</h2>
        <p className="text-slate-400">
          Add links to your writing or upload exports to build your persona.
        </p>
      </div>

      {/* Mode Tabs */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setMode('urls')}
          className={`flex-1 py-2 rounded-lg font-medium transition-colors ${
            mode === 'urls' ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-400'
          }`}
        >
          Web Links
        </button>
        <button
          onClick={() => setMode('files')}
          className={`flex-1 py-2 rounded-lg font-medium transition-colors ${
            mode === 'files' ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-400'
          }`}
        >
          File Upload
        </button>
      </div>

      {mode === 'urls' ? (
        <Card className="p-6 bg-slate-900 border-slate-700">
          <h3 className="font-semibold mb-4 text-white">Public Links</h3>
          <p className="text-sm text-slate-400 mb-4">
            GitHub READMEs, blog posts, articles. <span className="text-amber-400">LinkedIn and Twitter are blocked for crawling.</span>
          </p>
          {urls.map((url, idx) => (
            <input
              key={idx}
              type="url"
              value={url}
              onChange={(e) => {
                const newUrls = [...urls];
                newUrls[idx] = e.target.value;
                setUrls(newUrls);
              }}
              placeholder="https://github.com/username/repo"
              className="w-full mb-3 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          ))}
          <button
            onClick={() => setUrls([...urls, ''])}
            className="text-indigo-400 text-sm hover:text-indigo-300"
          >
            + Add another link
          </button>
        </Card>
      ) : (
        <Card className="p-6 bg-slate-900 border-slate-700">
          <h3 className="font-semibold mb-4 text-white">File Upload</h3>
          <p className="text-sm text-slate-400 mb-4">
            LinkedIn exports, Twitter archives, PDFs, documents.
          </p>
          <input
            type="file"
            multiple
            accept=".zip,.pdf,.csv,.html,.json"
            onChange={(e) => setFiles(Array.from(e.target.files || []))}
            className="w-full text-slate-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-indigo-600 file:text-white hover:file:bg-indigo-500"
          />
          {files.length > 0 && (
            <div className="mt-4 space-y-2">
              {files.map((f, i) => (
                <div key={i} className="text-sm text-slate-300 flex items-center gap-2">
                  <span>📄</span> {f.name} ({Math.round(f.size / 1024)}KB)
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      <button
        onClick={handleSubmit}
        disabled={!canSubmit || isSubmitting}
        className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg font-semibold transition-colors flex items-center justify-center gap-2"
      >
        {isSubmitting ? (
          <>
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Processing...
          </>
        ) : (
          'Start Processing'
        )}
      </button>
      
      {!twinId && (
        <p className="text-center text-amber-400 text-sm">
          Creating twin draft... Please wait.
        </p>
      )}
    </div>
  );
}
