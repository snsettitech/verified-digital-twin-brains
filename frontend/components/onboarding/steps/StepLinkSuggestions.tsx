'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';

interface LinkCandidate {
  id: string;
  url: string;
  title: string;
  snippet: string;
  favicon?: string;
  confidence: 'high' | 'medium' | 'low';
  matchSignals: string[];
  isSelected: boolean | null; // null = undecided, true = selected, false = rejected
}

interface StepLinkSuggestionsProps {
  twinId: string | null;
  fullName: string;
  location?: string;
  role?: string;
  onComplete: (selectedUrls: string[]) => void;
  onSkip: () => void;
}

export function StepLinkSuggestions({ 
  twinId, 
  fullName, 
  location, 
  role, 
  onComplete, 
  onSkip 
}: StepLinkSuggestionsProps) {
  const [candidates, setCandidates] = useState<LinkCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all');

  // Fetch suggestions on mount
  useEffect(() => {
    const fetchSuggestions = async () => {
      if (!twinId) return;
      
      try {
        const params = new URLSearchParams({ 
          name: fullName,
          ...(location && { location }),
          ...(role && { role })
        });
        
        const response = await fetch(`/api/persona/link-compile/suggest?${params}`);
        if (!response.ok) throw new Error('Failed to fetch suggestions');
        
        const data = await response.json();
        // Mark high confidence as pre-selected
        const processed = (data.candidates || []).map((c: LinkCandidate) => ({
          ...c,
          isSelected: c.confidence === 'high' ? true : null
        }));
        setCandidates(processed);
      } catch (e) {
        console.error('Failed to load suggestions:', e);
      } finally {
        setLoading(false);
      }
    };

    fetchSuggestions();
  }, [twinId, fullName, location, role]);

  const toggleCandidate = (id: string) => {
    setCandidates(prev => prev.map(c => 
      c.id === id ? { ...c, isSelected: c.isSelected === true ? false : true } : c
    ));
  };

  const markAsNotMe = (id: string) => {
    setCandidates(prev => prev.map(c => 
      c.id === id ? { ...c, isSelected: false } : c
    ));
  };

  const selectAllHighConfidence = () => {
    setCandidates(prev => prev.map(c => 
      c.confidence === 'high' ? { ...c, isSelected: true } : c
    ));
  };

  const deselectAll = () => {
    setCandidates(prev => prev.map(c => ({ ...c, isSelected: null })));
  };

  const handleContinue = () => {
    const selectedUrls = candidates
      .filter(c => c.isSelected === true)
      .map(c => c.url);
    onComplete(selectedUrls);
  };

  const filteredCandidates = candidates.filter(c => {
    if (filter === 'all') return c.isSelected !== false; // Hide rejected
    return c.confidence === filter && c.isSelected !== false;
  });

  const selectedCount = candidates.filter(c => c.isSelected === true).length;
  const highConfidenceCount = candidates.filter(c => c.confidence === 'high').length;

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-slate-400">Searching for public links...</p>
        <p className="text-sm text-slate-500 mt-2">{fullName}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-white mb-2">
          We Found Possible Matches
        </h2>
        <p className="text-slate-400">
          Select links that are actually you. This prevents mixing your persona with someone else's.
        </p>
      </div>

      {/* Stats & Quick Actions */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-900 p-4 rounded-xl border border-slate-700">
        <div className="flex items-center gap-4 text-sm">
          <span className="text-slate-400">
            Found: <span className="text-white font-medium">{candidates.length}</span>
          </span>
          <span className="text-green-400">
            Selected: <span className="font-medium">{selectedCount}</span>
          </span>
          <span className="text-slate-400">
            Rejected: <span className="font-medium">{candidates.filter(c => c.isSelected === false).length}</span>
          </span>
        </div>
        
        <div className="flex gap-2">
          <button
            onClick={selectAllHighConfidence}
            className="px-3 py-1.5 bg-green-500/20 text-green-400 rounded-lg text-sm font-medium hover:bg-green-500/30 transition-colors"
          >
            Select All High Confidence
          </button>
          <button
            onClick={deselectAll}
            className="px-3 py-1.5 bg-slate-800 text-slate-400 rounded-lg text-sm hover:bg-slate-700 transition-colors"
          >
            Clear All
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2">
        {(['all', 'high', 'medium', 'low'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              filter === f 
                ? 'bg-indigo-600 text-white' 
                : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
            {f === 'high' && highConfidenceCount > 0 && (
              <span className="ml-2 px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded text-xs">
                {highConfidenceCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Candidates List */}
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {filteredCandidates.length === 0 ? (
          <Card className="p-8 text-center bg-slate-900 border-slate-700">
            <p className="text-slate-400">No {filter !== 'all' ? filter + ' confidence ' : ''}links found.</p>
            <p className="text-sm text-slate-500 mt-2">
              Try adjusting filters or add links manually in the next step.
            </p>
          </Card>
        ) : (
          filteredCandidates.map((candidate) => (
            <Card 
              key={candidate.id}
              className={`p-4 border-2 transition-all ${
                candidate.isSelected === true 
                  ? 'border-green-500 bg-green-500/5' 
                  : candidate.isSelected === false
                    ? 'border-red-500/30 bg-red-500/5 opacity-50'
                    : 'border-slate-700 hover:border-slate-600'
              }`}
            >
              <div className="flex items-start gap-4">
                {/* Selection Checkbox */}
                <button
                  onClick={() => toggleCandidate(candidate.id)}
                  className={`mt-1 w-6 h-6 rounded border-2 flex items-center justify-center transition-colors ${
                    candidate.isSelected === true
                      ? 'bg-green-500 border-green-500 text-white'
                      : candidate.isSelected === false
                        ? 'bg-red-500/20 border-red-500/50'
                        : 'border-slate-600 hover:border-slate-500'
                  }`}
                >
                  {candidate.isSelected === true && '✓'}
                  {candidate.isSelected === false && '✕'}
                </button>

                {/* Favicon/Icon */}
                <div className="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center flex-shrink-0">
                  {candidate.favicon ? (
                    <img src={candidate.favicon} alt="" className="w-6 h-6" />
                  ) : (
                    <span className="text-lg">🌐</span>
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-medium text-white truncate">{candidate.title}</h3>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      candidate.confidence === 'high' ? 'bg-green-500/20 text-green-400' :
                      candidate.confidence === 'medium' ? 'bg-amber-500/20 text-amber-400' :
                      'bg-red-500/20 text-red-400'
                    }`}>
                      {candidate.confidence} confidence
                    </span>
                  </div>
                  
                  <p className="text-sm text-slate-400 line-clamp-2 mb-2">
                    {candidate.snippet}
                  </p>
                  
                  <p className="text-xs text-slate-500 truncate">
                    {candidate.url}
                  </p>

                  {/* Match Signals */}
                  <div className="flex flex-wrap gap-1 mt-2">
                    {candidate.matchSignals.map((signal, idx) => (
                      <span 
                        key={idx}
                        className="px-2 py-0.5 bg-slate-800 text-slate-400 rounded text-xs"
                      >
                        {signal}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Not Me Button */}
                {candidate.isSelected !== false && (
                  <button
                    onClick={() => markAsNotMe(candidate.id)}
                    className="text-xs text-slate-500 hover:text-red-400 transition-colors px-2 py-1"
                  >
                    Not me
                  </button>
                )}
              </div>
            </Card>
          ))
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-col sm:flex-row gap-3 pt-4">
        <button
          onClick={handleContinue}
          disabled={selectedCount === 0}
          className="flex-1 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-semibold transition-colors"
        >
          Continue with {selectedCount} Selected
        </button>
        
        <button
          onClick={onSkip}
          className="px-6 py-3 border border-slate-700 hover:bg-slate-800 text-slate-300 rounded-xl font-medium transition-colors"
        >
          Skip & Add Manually →
        </button>
      </div>

      <p className="text-center text-sm text-slate-500">
        Don't worry—you can add more sources later.
      </p>
    </div>
  );
}
