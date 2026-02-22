'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/Card';

interface LinkSubmissionProps {
  twinId: string | null;
  onSubmit: (urls: string[]) => void;
}

export function LinkSubmission({ twinId, onSubmit }: LinkSubmissionProps) {
  const [urls, setUrls] = useState<string[]>(['']);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [validatedUrls, setValidatedUrls] = useState<Set<number>>(new Set());

  const validateUrl = async (url: string, index: number) => {
    if (!url.trim() || !twinId) return;
    
    try {
      const response = await fetch('/api/persona/link-compile/validate-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      
      if (response.ok) {
        const result = await response.json();
        if (result.allowed) {
          setValidatedUrls(prev => new Set(prev).add(index));
        }
      }
    } catch (e) {
      console.error('URL validation failed:', e);
    }
  };

  const handleAddUrl = () => {
    setUrls([...urls, '']);
  };

  const handleUrlChange = (index: number, value: string) => {
    const newUrls = [...urls];
    newUrls[index] = value;
    setUrls(newUrls);
    
    // Remove from validated if changed
    if (validatedUrls.has(index)) {
      const newValidated = new Set(validatedUrls);
      newValidated.delete(index);
      setValidatedUrls(newValidated);
    }
  };

  const handleRemoveUrl = (index: number) => {
    setUrls(urls.filter((_, i) => i !== index));
    const newValidated = new Set(validatedUrls);
    newValidated.delete(index);
    setValidatedUrls(newValidated);
  };

  const handleSubmit = async () => {
    const validUrls = urls.filter(u => u.trim() && u.startsWith('http'));
    if (validUrls.length === 0 || !twinId) return;

    setIsSubmitting(true);
    
    try {
      const response = await fetch('/api/persona/link-compile/jobs/mode-c', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          twin_id: twinId,
          urls: validUrls,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        alert(error.detail || 'Failed to submit URLs');
        return;
      }

      onSubmit(validUrls);
    } catch (e) {
      alert('Submission failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const validUrlCount = urls.filter(u => u.trim() && u.startsWith('http')).length;

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2 text-white">Submit Your Links</h2>
        <p className="text-slate-400">
          Add URLs to your public content. We'll extract claims and build your persona.
        </p>
      </div>

      <Card className="p-6 bg-slate-900 border-slate-700">
        <div className="space-y-3">
          {urls.map((url, idx) => (
            <div key={idx} className="flex gap-2">
              <div className="flex-1 relative">
                <input
                  type="url"
                  value={url}
                  onChange={(e) => handleUrlChange(idx, e.target.value)}
                  onBlur={() => validateUrl(url, idx)}
                  placeholder="https://..."
                  className={`w-full px-4 py-2 bg-slate-800 border rounded-lg text-white placeholder-slate-500 focus:outline-none transition-colors ${
                    validatedUrls.has(idx) 
                      ? 'border-green-500/50 focus:border-green-500' 
                      : 'border-slate-700 focus:border-indigo-500'
                  }`}
                />
                {validatedUrls.has(idx) && (
                  <span className="absolute right-3 top-2.5 text-green-400 text-sm">✓</span>
                )}
              </div>
              {urls.length > 1 && (
                <button
                  onClick={() => handleRemoveUrl(idx)}
                  className="px-3 text-slate-500 hover:text-red-400 transition-colors"
                >
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>

        <button
          onClick={handleAddUrl}
          disabled={urls.length >= 10}
          className="mt-4 text-indigo-400 hover:text-indigo-300 text-sm font-medium disabled:opacity-50"
        >
          + Add another link (max 10)
        </button>

        <div className="mt-4 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
          <p className="text-sm text-amber-400">
            <span className="font-medium">Note:</span> LinkedIn and X/Twitter are blocked for direct fetching. 
            Please upload exports instead.
          </p>
        </div>
      </Card>

      <button
        onClick={handleSubmit}
        disabled={validUrlCount === 0 || !twinId || isSubmitting}
        className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-semibold transition-colors flex items-center justify-center gap-2"
      >
        {isSubmitting ? (
          <>
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Processing...
          </>
        ) : (
          <>
            <span>🚀</span>
            Submit {validUrlCount > 0 && `(${validUrlCount})`}
          </>
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
