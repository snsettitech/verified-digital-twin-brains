'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { getConnectedAccounts } from '@/lib/api/auth';
import { getSupabaseClient } from '@/lib/supabase/client';

export interface LinkedInIdentity {
  displayName: string;
  location?: string;
  headline?: string;
  profileUrl?: string;
  imageUrl?: string;
}

export interface UnifiedInputData {
  fullName: string;
  headline?: string;
  location?: string;
  profileUrl?: string;       // LinkedIn URL or personal website — passed as hints.website
  resumeFile?: File;         // Single PDF for Mode A
  consent: boolean;
  linkedInIdentity?: LinkedInIdentity;
}

interface UnifiedInputStepProps {
  onSubmit: (data: UnifiedInputData) => void;
}

type UrlType = 'linkedin' | 'website' | 'unknown';

function detectUrlType(url: string): UrlType {
  if (!url.trim()) return 'unknown';
  if (url.includes('linkedin.com/in/') || url.includes('linkedin.com/pub/')) return 'linkedin';
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('www.')) return 'website';
  return 'unknown';
}

function normalizeUrl(url: string): string {
  const trimmed = url.trim();
  if (!trimmed) return '';
  if (trimmed.startsWith('www.')) return `https://${trimmed}`;
  return trimmed;
}

export function UnifiedInputStep({ onSubmit }: UnifiedInputStepProps) {
  const [fullName, setFullName] = useState('');
  const [profileUrl, setProfileUrl] = useState('');
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [linkedInIdentity, setLinkedInIdentity] = useState<LinkedInIdentity | null>(null);
  const [linkedInConnected, setLinkedInConnected] = useState(false);

  const urlType = detectUrlType(profileUrl);

  useEffect(() => {
    getConnectedAccounts().then(({ accounts }) => {
      const linkedIn = accounts.find(a => a.provider === 'linkedin');
      if (linkedIn?.profile_snapshot?.display_name) {
        const identity: LinkedInIdentity = {
          displayName: linkedIn.profile_snapshot.display_name,
          headline: linkedIn.profile_snapshot.headline ?? undefined,
          profileUrl: linkedIn.profile_snapshot.profile_url ?? undefined,
          imageUrl: linkedIn.profile_snapshot.image_url ?? undefined,
        };
        setLinkedInConnected(true);
        setLinkedInIdentity(identity);
        setFullName(prev => prev.trim() ? prev : identity.displayName);
        if (identity.headline) {
          // headline carried through linkedInIdentity, not a separate field
        }
        if (identity.profileUrl && !profileUrl.trim()) {
          setProfileUrl(identity.profileUrl);
        }
      }
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleConnectLinkedIn = async () => {
    const supabase = getSupabaseClient();
    await supabase.auth.signInWithOAuth({
      provider: 'linkedin_oidc',
      options: {
        redirectTo: typeof window !== 'undefined'
          ? `${window.location.origin}/onboarding`
          : '/onboarding',
      },
    });
  };

  const handleFileChange = (file: File | null) => {
    if (!file) return;
    if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) {
      setResumeFile(file);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileChange(file);
  };

  const handleSubmit = async () => {
    if (!fullName.trim() || !consent) return;
    setIsSubmitting(true);

    await onSubmit({
      fullName: fullName.trim(),
      profileUrl: normalizeUrl(profileUrl) || undefined,
      resumeFile: resumeFile ?? undefined,
      consent,
      linkedInIdentity: linkedInIdentity ?? undefined,
      headline: linkedInIdentity?.headline,
    });

    setIsSubmitting(false);
  };

  const isValid = fullName.trim().length >= 2 && consent;

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-3xl font-bold text-white mb-3">Create Your Persona</h2>
        <p className="text-slate-400 max-w-md mx-auto text-sm leading-6">
          Enter your name — we&apos;ll search the web and build your profile automatically.
          A URL or resume makes it much richer.
        </p>
      </div>

      <Card className="p-8 bg-slate-900 border-slate-700">
        <div className="space-y-6">

          {/* Full Name */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Your name <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={fullName}
              onChange={e => setFullName(e.target.value)}
              placeholder="e.g. Sarah Chen"
              autoFocus
              className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>

          {/* Profile URL — LinkedIn or website, one field */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              LinkedIn or website URL{' '}
              <span className="text-slate-500">(optional — greatly improves quality)</span>
            </label>
            <div className="relative">
              <input
                type="url"
                value={profileUrl}
                onChange={e => setProfileUrl(e.target.value)}
                placeholder="linkedin.com/in/yourname  or  yourwebsite.com"
                className={`w-full px-4 py-3 bg-slate-800 border rounded-lg text-white placeholder-slate-500 focus:outline-none transition-colors pr-36 ${
                  urlType !== 'unknown'
                    ? 'border-green-600 focus:border-green-500'
                    : 'border-slate-700 focus:border-blue-500'
                }`}
              />
              {urlType !== 'unknown' && (
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-green-400 font-medium">
                  {urlType === 'linkedin' ? 'LinkedIn ✓' : 'Website ✓'}
                </span>
              )}
            </div>
            {/* LinkedIn OAuth as secondary option */}
            {!linkedInConnected && (
              <button
                type="button"
                onClick={handleConnectLinkedIn}
                className="mt-2 text-xs text-blue-400 hover:text-blue-300 transition-colors"
              >
                Or connect LinkedIn via OAuth to import your photo →
              </button>
            )}
            {linkedInConnected && linkedInIdentity && (
              <p className="mt-2 text-xs text-green-400">
                LinkedIn connected as {linkedInIdentity.displayName} — photo will be imported
              </p>
            )}
          </div>

          {/* Resume drop zone */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Resume <span className="text-slate-500">(optional — PDF)</span>
            </label>
            {resumeFile ? (
              <div className="flex items-center gap-3 px-4 py-3 bg-slate-800 border border-green-600 rounded-lg">
                <svg className="w-5 h-5 text-green-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <span className="text-sm text-slate-300 truncate">{resumeFile.name}</span>
                <button
                  type="button"
                  onClick={() => setResumeFile(null)}
                  className="ml-auto text-slate-500 hover:text-red-400 transition-colors shrink-0"
                >
                  ×
                </button>
              </div>
            ) : (
              <label
                onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                className={`flex flex-col items-center justify-center gap-2 px-4 py-6 border-2 border-dashed rounded-lg cursor-pointer transition-colors ${
                  isDragging
                    ? 'border-blue-500 bg-blue-500/5'
                    : 'border-slate-700 hover:border-slate-600 bg-slate-800/50'
                }`}
              >
                <svg className="w-6 h-6 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
                <span className="text-sm text-slate-500">Drop PDF here or click to browse</span>
                <input
                  type="file"
                  accept=".pdf"
                  className="sr-only"
                  onChange={e => handleFileChange(e.target.files?.[0] ?? null)}
                />
              </label>
            )}
          </div>

          {/* Consent */}
          <div className="pt-2 border-t border-slate-800">
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={consent}
                onChange={e => setConsent(e.target.checked)}
                className="mt-1 w-5 h-5 rounded border-slate-600 bg-slate-800 text-blue-500 focus:ring-blue-500/20"
              />
              <span className="text-sm text-slate-300 leading-6">
                Search the public web for content about me. I control what gets added and can change it anytime.
              </span>
            </label>
          </div>
        </div>
      </Card>

      <button
        onClick={handleSubmit}
        disabled={!isValid || isSubmitting}
        className="w-full py-4 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-semibold text-lg transition-colors flex items-center justify-center gap-2"
      >
        {isSubmitting ? (
          <>
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Creating…
          </>
        ) : (
          'Build My Persona →'
        )}
      </button>
    </div>
  );
}
