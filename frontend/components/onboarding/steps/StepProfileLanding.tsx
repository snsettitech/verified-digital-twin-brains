'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';

interface BioVariant {
  bio_type: string;
  bio_text: string;
  validation_status: string;
}

interface ClaimSummary {
  total: number;
  verified: number;
  disputed: number;
  needsConfirmation: number;
}

interface StepProfileLandingProps {
  twinId: string | null;
  onActivate: () => void;
  onReviewClaims: () => void;
  onAddMoreSources: () => void;
}

export function StepProfileLanding({ 
  twinId, 
  onActivate, 
  onReviewClaims,
  onAddMoreSources 
}: StepProfileLandingProps) {
  const [bios, setBios] = useState<BioVariant[]>([]);
  const [selectedBioType, setSelectedBioType] = useState<string>('short');
  const [claimSummary, setClaimSummary] = useState<ClaimSummary>({
    total: 0,
    verified: 0,
    disputed: 0,
    needsConfirmation: 0,
  });
  const [twinName, setTwinName] = useState('');
  const [sources, setSources] = useState<{url: string; title: string}[]>([]);
  const [loading, setLoading] = useState(true);
  const [activating, setActivating] = useState(false);
  const [showEvidencePanel, setShowEvidencePanel] = useState(false);

  // Starter questions (static for MVP)
  const starterQuestions = [
    'What is your background and what do you specialize in?',
    'What topics can your digital brain answer well?',
    'What are your main projects or services?',
  ];

  useEffect(() => {
    if (!twinId) return;

    const fetchData = async () => {
      try {
        // Fetch bios
        const biosRes = await authFetchStandalone(`/persona/link-compile/twins/${twinId}/bios`);
        if (biosRes.ok) {
          const data = await biosRes.json();
          setBios(data.variants || []);
        }

        // Fetch claims summary
        const claimsRes = await authFetchStandalone(`/persona/link-compile/twins/${twinId}/claims?min_confidence=0.3`);
        if (claimsRes.ok) {
          const data = await claimsRes.json();
          const claims = data.claims || [];
          setClaimSummary({
            total: claims.length,
            verified: claims.filter((c: {verification_status: string}) => c.verification_status === 'approved').length,
            disputed: claims.filter((c: {verification_status: string}) => c.verification_status === 'rejected').length,
            needsConfirmation: claims.filter((c: {verification_status: string}) => c.verification_status === 'pending').length,
          });
        }

        // Fetch twin info
        const twinRes = await authFetchStandalone(`/twins/${twinId}`);
        if (twinRes.ok) {
          const twin = await twinRes.json();
          setTwinName(twin.name);
        }

        // Fetch sources (from settings or job)
        const jobRes = await authFetchStandalone(`/persona/link-compile/twins/${twinId}/job`);
        if (jobRes.ok) {
          const job = await jobRes.json();
          const sourceFiles = (job.source_files || []).map((s: { url?: string; title?: string; filename?: string }) => ({
            url: s.url || '',
            title: s.title || s.filename || 'Source',
          }));
          const sourceUrls = (job.source_urls || []).map((url: string) => ({
            url,
            title: url,
          }));
          setSources([...sourceFiles, ...sourceUrls]);
        }
      } catch (e) {
        console.error('Failed to load profile:', e);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [twinId]);

  const selectedBio = bios.find(b => b.bio_type === selectedBioType) || bios[0];
  const validBios = bios.filter(b => b.validation_status === 'valid');

  const handleActivate = async () => {
    setActivating(true);
    try {
      const response = await authFetchStandalone(`/twins/${twinId}/activate`, {
        method: 'POST',
        body: JSON.stringify({ final_name: twinName }),
      });
      
      if (response.ok) {
        onActivate();
      } else {
        throw new Error('Activation failed');
      }
    } catch (e) {
      console.error('Activation failed:', e);
      alert('Failed to activate. Please try again.');
    } finally {
      setActivating(false);
    }
  };

  function detectSourceType(url: string): string {
    const t = (url || '').toLowerCase();
    if (t.includes('linkedin.com')) return 'linkedin';
    if (t.includes('youtube.com') || t.includes('youtu.be')) return 'youtube';
    if (t.includes('instagram.com')) return 'instagram';
    if (t.includes('tiktok.com')) return 'tiktok';
    if (t.startsWith('http')) return 'website';
    return 'other';
  }

  const groupedSources = sources.reduce<Record<string, { url: string; title: string }[]>>((acc, s) => {
    const type = detectSourceType(s.url);
    if (!acc[type]) acc[type] = [];
    acc[type].push(s);
    return acc;
  }, {});

  const sourceTypeLabels: Record<string, string> = {
    linkedin: 'LinkedIn',
    youtube: 'YouTube',
    instagram: 'Instagram',
    tiktok: 'TikTok',
    website: 'Website',
    other: 'Other',
  };

  const bioTypeLabels: Record<string, string> = {
    one_liner: 'One-Liner',
    short: 'Short Bio',
    linkedin_about: 'LinkedIn Style',
    speaker_intro: 'Speaker Intro',
    full: 'Full Bio',
  };

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-slate-400">Loading your profile...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <h2 className="text-3xl font-bold text-white mb-2">Your Profile</h2>
        <p className="text-slate-400">
          Review your auto-generated bio and evidence before activating.
        </p>
        <div className="flex justify-center gap-2 mt-3">
          <span className="px-3 py-1 rounded-full text-xs font-medium bg-green-500/20 text-green-400">
            Digital Brain Ready
          </span>
        </div>
      </div>

      {/* Twin Name */}
      <Card className="p-6 bg-slate-900 border-slate-700">
        <label className="block text-sm font-medium text-slate-300 mb-2">
          Digital Twin Name
        </label>
        <input
          type="text"
          value={twinName}
          onChange={(e) => setTwinName(e.target.value)}
          placeholder="e.g., Investment Advisor Sarah"
          className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
        />
      </Card>

      {/* Bio Selector */}
      <div className="flex gap-2 flex-wrap">
        {validBios.map((bio) => (
          <button
            key={bio.bio_type}
            onClick={() => setSelectedBioType(bio.bio_type)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              selectedBioType === bio.bio_type
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
            }`}
          >
            {bioTypeLabels[bio.bio_type] || bio.bio_type}
          </button>
        ))}
      </div>

      {/* Bio Display */}
      {selectedBio ? (
        <Card className="p-6 bg-slate-900 border-slate-700">
          <h3 className="text-sm font-medium text-slate-400 mb-3">
            {bioTypeLabels[selectedBio.bio_type]}
          </h3>
          <p className="text-white whitespace-pre-wrap leading-relaxed">{selectedBio.bio_text}</p>
          <div className="mt-4 flex items-center gap-2">
            <span className="text-green-400 text-sm">✓ Auto-generated from your sources</span>
          </div>
        </Card>
      ) : (
        <Card className="p-6 bg-slate-900 border-slate-700 text-center">
          <p className="text-slate-400">No bio generated yet. Try adding more sources.</p>
        </Card>
      )}

      {/* Starter Questions */}
      <Card className="p-6 bg-slate-900 border-slate-700">
        <h3 className="text-sm font-medium text-slate-400 mb-3">Suggested questions to ask</h3>
        <div className="flex flex-wrap gap-2">
          {starterQuestions.map((q, idx) => (
            <button
              key={idx}
              onClick={() => navigator.clipboard?.writeText(q)}
              className="px-4 py-2 rounded-lg text-sm text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition-colors text-left"
            >
              {q}
            </button>
          ))}
        </div>
      </Card>

      {/* Social Links (grouped by type) */}
      <Card className="p-4 bg-slate-900 border-slate-700">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-medium text-slate-300">Your links ({sources.length})</h3>
          <button
            onClick={onAddMoreSources}
            className="text-sm text-indigo-400 hover:text-indigo-300"
          >
            + Add More
          </button>
        </div>
        <div className="space-y-4 max-h-48 overflow-y-auto">
          {sources.length === 0 ? (
            <p className="text-sm text-slate-500">No sources added yet.</p>
          ) : (
            Object.entries(groupedSources).map(([type, items]) => (
              <div key={type}>
                <div className="text-xs font-medium text-slate-500 mb-2">
                  {sourceTypeLabels[type] || type}
                </div>
                <div className="space-y-1">
                  {items.map((source, idx) => (
                    <a
                      key={idx}
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 text-sm text-slate-400 hover:text-indigo-400 truncate"
                    >
                      <span className="text-slate-500 shrink-0">🔗</span>
                      <span className="truncate">{source.title || source.url}</span>
                    </a>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      </Card>

      {/* Evidence Panel (Collapsible) */}
      <Card className="p-4 bg-slate-900 border-slate-700">
        <button
          onClick={() => setShowEvidencePanel(!showEvidencePanel)}
          className="w-full flex items-center justify-between"
        >
          <div className="flex items-center gap-2">
            <span className="text-lg">📊</span>
            <span className="font-medium text-slate-300">Confidence & Evidence</span>
          </div>
          <span className="text-slate-500">{showEvidencePanel ? '▼' : '▶'}</span>
        </button>

        {showEvidencePanel && (
          <div className="mt-4 pt-4 border-t border-slate-800 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-green-500/10 p-3 rounded-lg">
                <div className="text-2xl font-bold text-green-400">{claimSummary.verified}</div>
                <div className="text-sm text-slate-400">Verified Claims</div>
              </div>
              <div className="bg-amber-500/10 p-3 rounded-lg">
                <div className="text-2xl font-bold text-amber-400">{claimSummary.needsConfirmation}</div>
                <div className="text-sm text-slate-400">Need Confirmation</div>
              </div>
            </div>
            
            {claimSummary.disputed > 0 && (
              <div className="bg-red-500/10 p-3 rounded-lg">
                <div className="text-lg font-bold text-red-400">{claimSummary.disputed}</div>
                <div className="text-sm text-slate-400">Disputed Claims</div>
              </div>
            )}

            {claimSummary.needsConfirmation > 0 && (
              <button
                onClick={onReviewClaims}
                className="w-full py-2 bg-amber-500/20 hover:bg-amber-500/30 text-amber-400 rounded-lg text-sm font-medium transition-colors"
              >
                Review {claimSummary.needsConfirmation} Claims →
              </button>
            )}
          </div>
        )}
      </Card>

      {/* Primary CTA */}
      <button
        onClick={handleActivate}
        disabled={activating || !twinName.trim()}
        className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-semibold text-lg transition-colors flex items-center justify-center gap-2"
      >
        {activating ? (
          <>
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Activating...
          </>
        ) : (
          <>
            <span>💬</span>
            Chat with Your Twin
          </>
        )}
      </button>

      {/* Secondary Actions */}
      <div className="flex gap-3">
        <button
          onClick={onReviewClaims}
          className="flex-1 py-3 border border-slate-700 hover:bg-slate-800 text-slate-300 rounded-xl font-medium transition-colors"
        >
          Review Claims
        </button>
        <button
          onClick={onAddMoreSources}
          className="flex-1 py-3 border border-slate-700 hover:bg-slate-800 text-slate-300 rounded-xl font-medium transition-colors"
        >
          Add Sources
        </button>
      </div>

      <p className="text-center text-sm text-slate-500">
        You can always improve your twin later by adding sources or reviewing claims.
      </p>
    </div>
  );
}
