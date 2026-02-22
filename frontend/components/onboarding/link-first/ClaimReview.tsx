'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { validateClaimsResponse, type Claim } from '@/lib/types/api.contract';

interface ClaimReviewProps {
  twinId: string | null;
  onApprove: () => void;
}

export function ClaimReview({ twinId, onApprove }: ClaimReviewProps) {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [loading, setLoading] = useState(true);
  const [approvedClaims, setApprovedClaims] = useState<Set<string>>(new Set());
  const [rejectedClaims, setRejectedClaims] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!twinId) return;

    const fetchClaims = async () => {
      try {
        const response = await fetch(`/api/persona/link-compile/twins/${twinId}/claims?min_confidence=0.3`);
        if (!response.ok) throw new Error('Failed to fetch claims');
        
        const data = await response.json();
        const validated = validateClaimsResponse(data);
        
        if (validated) {
          setClaims(validated.claims);
          // Auto-approve high confidence claims
          const autoApproved = new Set(
            validated.claims
              .filter(c => c.confidence >= 0.7)
              .map(c => c.id)
          );
          setApprovedClaims(autoApproved);
        }
      } catch (e) {
        console.error('Failed to load claims:', e);
      } finally {
        setLoading(false);
      }
    };

    fetchClaims();
  }, [twinId]);

  const toggleApproval = (claimId: string) => {
    const newApproved = new Set(approvedClaims);
    const newRejected = new Set(rejectedClaims);
    
    if (approvedClaims.has(claimId)) {
      newApproved.delete(claimId);
      newRejected.add(claimId);
    } else if (rejectedClaims.has(claimId)) {
      newRejected.delete(claimId);
    } else {
      newApproved.add(claimId);
    }
    
    setApprovedClaims(newApproved);
    setRejectedClaims(newRejected);
  };

  const handleContinue = async () => {
    if (!twinId) return;
    
    // Update claim statuses in backend
    try {
      await fetch(`/api/twins/${twinId}/transition/clarification-pending`, {
        method: 'POST',
      });
    } catch (e) {
      console.error('Transition failed:', e);
    }
    
    onApprove();
  };

  const getClaimTypeIcon = (type: string) => {
    const icons: Record<string, string> = {
      preference: '⚖️',
      belief: '🧠',
      heuristic: '🔍',
      value: '💎',
      experience: '📚',
      boundary: '🚫',
    };
    return icons[type] || '📝';
  };

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-slate-400">Loading extracted claims...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2 text-white">Review Extracted Claims</h2>
        <p className="text-slate-400">
          We've extracted claims from your content. Review and approve them for your persona.
        </p>
      </div>

      <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 mb-4">
        <div className="flex justify-between text-sm text-slate-400">
          <span>Total: {claims.length}</span>
          <span>Approved: {approvedClaims.size}</span>
          <span>Rejected: {rejectedClaims.size}</span>
        </div>
      </div>

      <div className="space-y-3 max-h-96 overflow-y-auto">
        {claims.map((claim) => {
          const isApproved = approvedClaims.has(claim.id);
          const isRejected = rejectedClaims.has(claim.id);
          
          return (
            <Card 
              key={claim.id}
              className={`p-4 border-2 transition-colors cursor-pointer ${
                isApproved ? 'border-green-500 bg-green-500/10' :
                isRejected ? 'border-red-500 bg-red-500/10' :
                'border-slate-700 hover:border-slate-600 bg-slate-900'
              }`}
              onClick={() => toggleApproval(claim.id)}
            >
              <div className="flex items-start gap-3">
                <span className="text-2xl">{getClaimTypeIcon(claim.claim_type)}</span>
                <div className="flex-1">
                  <p className="text-white font-medium">{claim.claim_text}</p>
                  <div className="flex items-center gap-3 mt-2 text-sm">
                    <span className="text-slate-400 capitalize">{claim.claim_type}</span>
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      claim.confidence >= 0.7 ? 'bg-green-500/20 text-green-400' :
                      claim.confidence >= 0.4 ? 'bg-amber-500/20 text-amber-400' :
                      'bg-red-500/20 text-red-400'
                    }`}>
                      {Math.round(claim.confidence * 100)}% confidence
                    </span>
                  </div>
                </div>
                <div className="text-2xl">
                  {isApproved ? '✅' : isRejected ? '❌' : '⭕'}
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {claims.length === 0 && (
        <div className="text-center py-8 text-slate-400">
          <p>No claims were extracted from your content.</p>
          <p className="text-sm mt-2">You may need to submit more content.</p>
        </div>
      )}

      <button
        onClick={handleContinue}
        disabled={approvedClaims.size === 0}
        className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-semibold transition-colors"
      >
        Continue with {approvedClaims.size} Approved Claims
      </button>
    </div>
  );
}
