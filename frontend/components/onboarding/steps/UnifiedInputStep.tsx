'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { getConnectedAccounts } from '@/lib/api/auth';
import { getSupabaseClient } from '@/lib/supabase/client';

export interface UnifiedInputData {
  fullName: string;
  headline?: string;
  location?: string;
  linkedInUrl?: string;
  consent: boolean;
  /** Optional: user-provided sources */
  sources?: {
    type: 'export' | 'link' | 'paste';
    value: string;
    category?: string;
    file?: File;
  }[];
}

interface UnifiedInputStepProps {
  onSubmit: (data: UnifiedInputData) => void;
}

export function UnifiedInputStep({ onSubmit }: UnifiedInputStepProps) {
  const [fullName, setFullName] = useState('');
  const [headline, setHeadline] = useState('');
  const [location, setLocation] = useState('');
  const [linkedInUrl, setLinkedInUrl] = useState('');
  const [consent, setConsent] = useState(false);
  const [showOptionalSources, setShowOptionalSources] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Optional sources (collapsible)
  const [files, setFiles] = useState<File[]>([]);
  const [links, setLinks] = useState<{ url: string }[]>([]);
  const [pasteContent, setPasteContent] = useState('');
  const [pasteTitle, setPasteTitle] = useState('');
  const [linkedInConnected, setLinkedInConnected] = useState(false);
  const [linkedInProfileUrl, setLinkedInProfileUrl] = useState<string | null>(null);

  useEffect(() => {
    getConnectedAccounts().then(({ accounts }) => {
      const linkedIn = accounts.find(a => a.provider === 'linkedin');
      if (linkedIn?.profile_snapshot?.profile_url) {
        setLinkedInConnected(true);
        const url = linkedIn.profile_snapshot.profile_url;
        setLinkedInProfileUrl(url);
        setLinkedInUrl(url);
        setLinks(prev => (prev.some(l => l.url === url) ? prev : [{ url }, ...prev]));
      }
    });
  }, []);

  const handleConnectLinkedIn = async () => {
    const supabase = getSupabaseClient();
    await supabase.auth.signInWithOAuth({
      provider: 'linkedin',
      options: { redirectTo: typeof window !== 'undefined' ? `${window.location.origin}/onboarding` : '/onboarding' },
    });
  };

  const handleAddLink = () => setLinks([...links, { url: '' }]);
  const handleUpdateLink = (i: number, url: string) => {
    const next = [...links];
    next[i] = { url };
    setLinks(next);
  };
  const handleRemoveLink = (i: number) => setLinks(links.filter((_, idx) => idx !== i));
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) setFiles([...files, ...Array.from(e.target.files)]);
  };
  const handleRemoveFile = (i: number) => setFiles(files.filter((_, idx) => idx !== i));

  const handleSubmit = async () => {
    if (!fullName.trim() || !consent) return;
    setIsSubmitting(true);

    const sources: UnifiedInputData['sources'] = [];
    files.forEach(f => sources.push({ type: 'export', value: f.name, file: f }));
    links.filter(l => l.url.trim() && l.url.startsWith('http')).forEach(l => sources.push({ type: 'link', value: l.url }));
    if (pasteContent.trim()) {
      sources.push({ type: 'paste', value: pasteContent, category: pasteTitle || 'Pasted Content' });
    }

    // If user entered LinkedIn URL manually, add as link
    const manualLinkedIn = linkedInUrl.trim();
    if (manualLinkedIn && manualLinkedIn.startsWith('http') && !sources.some(s => s.type === 'link' && s.value === manualLinkedIn)) {
      sources.push({ type: 'link', value: manualLinkedIn });
    }

    await onSubmit({
      fullName: fullName.trim(),
      headline: headline.trim() || undefined,
      location: location.trim() || undefined,
      linkedInUrl: linkedInUrl.trim() || undefined,
      consent,
      sources: sources.length > 0 ? sources : undefined,
    });
    setIsSubmitting(false);
  };

  const hasOptionalContent = files.length > 0 || links.some(l => l.url.trim()) || pasteContent.trim();
  const isValid = fullName.trim().length >= 2 && consent;

  return (
    <div className="space-y-8">
      <div className="text-center">
        <h2 className="text-3xl font-bold text-white mb-3">Create Your Digital Twin</h2>
        <p className="text-slate-400 max-w-md mx-auto">
          Enter your name and we&apos;ll search the web for your public content. More context helps us find better matches.
        </p>
      </div>

      <Card className="p-8 bg-slate-900 border-slate-700">
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Full Name <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g., Sarah Chen"
              className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Headline / Role <span className="text-slate-500">(optional)</span>
            </label>
            <input
              type="text"
              value={headline}
              onChange={(e) => setHeadline(e.target.value)}
              placeholder="e.g., Founder at Acme"
              className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Location <span className="text-slate-500">(optional)</span>
            </label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g., San Francisco, CA"
              className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              LinkedIn <span className="text-slate-500">(optional)</span>
            </label>
            {linkedInConnected ? (
              <p className="text-sm text-green-400">Connected: {linkedInProfileUrl}</p>
            ) : (
              <div className="flex gap-2">
                <input
                  type="url"
                  value={linkedInUrl}
                  onChange={(e) => setLinkedInUrl(e.target.value)}
                  placeholder="https://linkedin.com/in/yourprofile"
                  className="flex-1 px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
                />
                <button
                  type="button"
                  onClick={handleConnectLinkedIn}
                  className="px-4 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium"
                >
                  Connect
                </button>
              </div>
            )}
          </div>

          {/* Collapsible: I have files or links */}
          <div className="border-t border-slate-800 pt-6">
            <button
              type="button"
              onClick={() => setShowOptionalSources(!showOptionalSources)}
              className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
            >
              <span className="text-lg">{showOptionalSources ? '−' : '+'}</span>
              I have files or links to add
              {hasOptionalContent && (
                <span className="text-xs bg-indigo-500/20 text-indigo-400 px-2 py-0.5 rounded">
                  {files.length + links.filter(l => l.url.trim()).length + (pasteContent.trim() ? 1 : 0)} added
                </span>
              )}
            </button>
            {showOptionalSources && (
              <div className="mt-4 space-y-4 pl-6 border-l-2 border-slate-700">
                <div>
                  <label className="block text-xs text-slate-500 mb-2">Files (exports, PDFs)</label>
                  <input
                    type="file"
                    multiple
                    accept=".zip,.pdf,.html,.csv,.json"
                    onChange={handleFileChange}
                    className="block w-full text-sm text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:bg-indigo-500/20 file:text-indigo-400"
                  />
                  {files.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {files.map((f, i) => (
                        <li key={i} className="flex items-center justify-between text-sm text-slate-300">
                          <span>{f.name}</span>
                          <button type="button" onClick={() => handleRemoveFile(i)} className="text-red-400 hover:text-red-300">×</button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-2">URLs</label>
                  {links.map((l, i) => (
                    <div key={i} className="flex gap-2 mb-2">
                      <input
                        type="url"
                        value={l.url}
                        onChange={(e) => handleUpdateLink(i, e.target.value)}
                        placeholder="https://..."
                        className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white text-sm"
                      />
                      <button type="button" onClick={() => handleRemoveLink(i)} className="text-slate-500 hover:text-red-400">×</button>
                    </div>
                  ))}
                  <button type="button" onClick={handleAddLink} className="text-sm text-indigo-400 hover:text-indigo-300">+ Add URL</button>
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-2">Paste content</label>
                  <input
                    type="text"
                    value={pasteTitle}
                    onChange={(e) => setPasteTitle(e.target.value)}
                    placeholder="Title (optional)"
                    className="w-full px-3 py-2 mb-2 bg-slate-800 border border-slate-700 rounded text-white text-sm"
                  />
                  <textarea
                    value={pasteContent}
                    onChange={(e) => setPasteContent(e.target.value)}
                    placeholder="Paste text here..."
                    rows={3}
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white text-sm placeholder-slate-500"
                  />
                </div>
              </div>
            )}
          </div>

          <div className="pt-4 border-t border-slate-800">
            <label className="flex items-start gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-1 w-5 h-5 rounded border-slate-600 bg-slate-800 text-indigo-500 focus:ring-indigo-500/20"
              />
              <span className="text-sm text-slate-300">
                Search the public web for content that looks like me. I control what gets added and can change it anytime.
              </span>
            </label>
          </div>
        </div>
      </Card>

      <button
        onClick={handleSubmit}
        disabled={!isValid || isSubmitting}
        className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-semibold text-lg transition-colors flex items-center justify-center gap-2"
      >
        {isSubmitting ? (
          <>
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Creating...
          </>
        ) : (
          <>Create My Digital Twin</>
        )}
      </button>
    </div>
  );
}
