'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { createProfile, startDeepResearch, getDeepResearchStatus, DeepResearchRun } from '@/lib/context/ProfileContext';
import { getSupabaseClient } from '@/lib/supabase/client';
import { resolveApiBaseUrl } from '@/lib/api';

// ============================================================================
// Types
// ============================================================================

type OnboardingStep = 'identity' | 'hints' | 'content' | 'building' | 'complete';
type BuildMode = 'with_links' | 'name_only';

interface IdentityData {
  fullName: string;
  headline: string;
  buildMode: BuildMode;
}

interface HintsData {
  role: string;
  location: string;
  expertiseTags: string[];
}

interface ContentData {
  urls: string[];
  files: File[];
}

// ============================================================================
// Main Component
// ============================================================================

export default function OnboardingV2Page() {
  const router = useRouter();
  const API_URL = resolveApiBaseUrl();
  const [currentStep, setCurrentStep] = useState<OnboardingStep>('identity');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Data state
  const [identity, setIdentity] = useState<IdentityData>({
    fullName: '',
    headline: '',
    buildMode: 'with_links'
  });
  const [hints, setHints] = useState<HintsData>({
    role: '',
    location: '',
    expertiseTags: []
  });
  const [content, setContent] = useState<ContentData>({
    urls: [],
    files: []
  });
  
  // Build tracking
  const [researchRun, setResearchRun] = useState<DeepResearchRun | null>(null);
  const [profileId, setProfileId] = useState<string | null>(null);
  const [buildProgress, setBuildProgress] = useState({
    stage: '',
    percent: 0,
    stats: {} as Record<string, any>
  });
  const [nameResearchCompleted, setNameResearchCompleted] = useState(false);
  const [personCompletenessTriggered, setPersonCompletenessTriggered] = useState(false);

  const refreshProfileSnapshot = useCallback(async () => {
    try {
      const supabase = getSupabaseClient();
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData?.session?.access_token;
      if (!token) return;
      await fetch(`${API_URL}/profile`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
    } catch {
      // Best-effort refresh for onboarding flow.
    }
  }, [API_URL]);

  // ============================================================================
  // Step 1: Identity
  // ============================================================================

  const handleIdentitySubmit = async () => {
    if (!identity.fullName.trim()) {
      setError('Full name is required');
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      if (identity.buildMode === 'name_only') {
        // Name-only flow: Start deep research FIRST (creates twin internally)
        const run = await startDeepResearch({
          name: identity.fullName,
          hints: {}
        });
        setResearchRun(run);
        setProfileId(run.twin_id); // Use the twin_id as profileId
        setCurrentStep('building');
      } else {
        // With-links flow: Create profile first
        const profile = await createProfile({
          full_name: identity.fullName,
          headline: identity.headline,
          build_mode: 'with_links'
        });
        setProfileId(profile.id);
        setCurrentStep('hints');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to create profile');
    } finally {
      setIsLoading(false);
    }
  };

  // ============================================================================
  // Step 2: Hints (with-links only)
  // ============================================================================

  const handleHintsSubmit = async (skip: boolean = false) => {
    if (!skip && profileId) {
      setIsLoading(true);
      try {
        const supabase = getSupabaseClient();
        const { data: sessionData } = await supabase.auth.getSession();
        const token = sessionData?.session?.access_token;
        
        if (token) {
          await fetch(`${API_URL}/profile`, {
            method: 'PATCH',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              role: hints.role,
              location: hints.location,
              expertise_tags: hints.expertiseTags
            })
          });
        }
      } catch (err) {
        console.error('Failed to update hints:', err);
      } finally {
        setIsLoading(false);
      }
    }
    setCurrentStep('content');
  };

  // ============================================================================
  // Step 3: Content (with-links only)
  // ============================================================================

  const handleContentSubmit = async () => {
    const hasContent = content.urls.length > 0 || content.files.length > 0;
    if (!hasContent) {
      setError('Please add at least one URL or file');
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      // Upload files and URLs
      await uploadContent();
      
      // Start person completeness pipeline
      const supabase = getSupabaseClient();
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData?.session?.access_token;
      
      if (token && profileId) {
        await fetch(`${API_URL}/profile/person-completeness/run`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });
      }
      
      setCurrentStep('building');
    } catch (err: any) {
      setError(err.message || 'Failed to upload content');
    } finally {
      setIsLoading(false);
    }
  };

  const uploadContent = async () => {
    const supabase = getSupabaseClient();
    const { data: sessionData } = await supabase.auth.getSession();
    const token = sessionData?.session?.access_token;
    
    if (!token || !profileId) return;
    
    const sourceLabel = 'identity';
    const identityConfirmed = true;

    // Upload URLs
    for (const url of content.urls) {
      await fetch(`${API_URL}/ingest/url`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          url,
          twin_id: profileId,
          source_label: sourceLabel,
          identity_confirmed: identityConfirmed
        })
      });
    }

    // Upload files
    for (const file of content.files) {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('twin_id', profileId);
      formData.append('source_label', sourceLabel);
      formData.append('identity_confirmed', String(identityConfirmed));
      
      await fetch(`${API_URL}/ingest/document`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });
    }

    // Best-effort drain so person-completeness sees indexed data.
    for (let i = 0; i < 8; i += 1) {
      const queueRes = await fetch(`${API_URL}/training-jobs/process-queue?twin_id=${profileId}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!queueRes.ok) {
        break;
      }
      const queueData = await queueRes.json().catch(() => ({} as Record<string, any>));
      const remaining = typeof queueData?.remaining === 'number' ? queueData.remaining : 0;
      if (remaining <= 0) {
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 1200));
    }
  };

  // ============================================================================
  // Building Step: Poll for completion
  // ============================================================================

  useEffect(() => {
    if (currentStep !== 'building') return;
    
    const pollInterval = setInterval(async () => {
      try {
        if (identity.buildMode === 'name_only' && researchRun) {
          // Poll deep research status
          const status = await getDeepResearchStatus(researchRun.run_id);
          if (!nameResearchCompleted) {
            setBuildProgress({
              stage: status.status,
              percent: calculateResearchProgress(status),
              stats: status.crawl_stats
            });
          }

          if (status.status === 'completed') {
            setNameResearchCompleted(true);

            if (!personCompletenessTriggered) {
              const supabase = getSupabaseClient();
              const { data: sessionData } = await supabase.auth.getSession();
              const token = sessionData?.session?.access_token;
              if (token) {
                await fetch(`${API_URL}/profile/person-completeness/run`, {
                  method: 'POST',
                  headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                  }
                });
              }
              setPersonCompletenessTriggered(true);
            }

            const supabase = getSupabaseClient();
            const { data: sessionData } = await supabase.auth.getSession();
            const token = sessionData?.session?.access_token;

            if (token) {
              const buildResponse = await fetch(`${API_URL}/profile/build-status`, {
                headers: { 'Authorization': `Bearer ${token}` }
              });
              if (buildResponse.ok) {
                const buildStatus = await buildResponse.json();
                setBuildProgress({
                  stage: buildStatus.stage || 'building',
                  percent: typeof buildStatus.progress_percent === 'number' ? buildStatus.progress_percent : 85,
                  stats: buildStatus.stats || {}
                });

                if (buildStatus.status === 'ready' || buildStatus.status === 'needs_attention') {
                  await refreshProfileSnapshot();
                  clearInterval(pollInterval);
                  setCurrentStep('complete');
                }
              }
            }
          }
        } else {
          // Poll profile build status for with-links mode
          const supabase = getSupabaseClient();
          const { data: sessionData } = await supabase.auth.getSession();
          const token = sessionData?.session?.access_token;
          
          if (token) {
            const response = await fetch(`${API_URL}/profile/build-status`, {
              headers: { 'Authorization': `Bearer ${token}` }
            });
            
            if (response.ok) {
              const status = await response.json();
              setBuildProgress({
                stage: status.stage,
                percent: status.progress_percent,
                stats: status.stats
              });
              
              if (status.status === 'ready' || status.status === 'needs_attention') {
                await refreshProfileSnapshot();
                clearInterval(pollInterval);
                setCurrentStep('complete');
              }
            }
          }
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    }, 3000);
    
    return () => clearInterval(pollInterval);
  }, [
    currentStep,
    identity.buildMode,
    researchRun,
    profileId,
    API_URL,
    refreshProfileSnapshot,
    nameResearchCompleted,
    personCompletenessTriggered
  ]);

  const calculateResearchProgress = (status: any): number => {
    const stageMap: Record<string, number> = {
      'created': 5,
      'searching': 15,
      'crawling': 35,
      'extracting': 55,
      'synthesizing': 75,
      'completed': 100
    };
    return stageMap[status.status] || 0;
  };

  // ============================================================================
  // Complete Step
  // ============================================================================

  const handleComplete = () => {
    router.push('/dashboard/profile');
  };

  // ============================================================================
  // Render Helpers
  // ============================================================================

  const renderProgressBar = () => (
    <div className="w-full bg-slate-800 rounded-full h-2 mb-4">
      <div 
        className="bg-gradient-to-r from-indigo-500 to-purple-500 h-2 rounded-full transition-all duration-500"
        style={{ width: `${buildProgress.percent}%` }}
      />
    </div>
  );

  // ============================================================================
  // Render Steps
  // ============================================================================

  if (currentStep === 'identity') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-slate-800/50 backdrop-blur-xl rounded-2xl p-8 border border-slate-700/50">
          <div className="mb-8">
            <h1 className="text-3xl font-black text-white mb-2">Create Your Profile</h1>
            <p className="text-slate-400">Let&apos;s build your verified digital presence</p>
          </div>
          
          {error && (
            <div className="mb-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}
          
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Full Name <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={identity.fullName}
                onChange={(e) => setIdentity({ ...identity, fullName: e.target.value })}
                placeholder="e.g., Jane Doe"
                className="w-full px-4 py-3 bg-slate-900/50 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Headline <span className="text-slate-500">(optional)</span>
              </label>
              <input
                type="text"
                value={identity.headline}
                onChange={(e) => setIdentity({ ...identity, headline: e.target.value })}
                placeholder="e.g., Founder & Builder"
                className="w-full px-4 py-3 bg-slate-900/50 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-3">
                Build Mode
              </label>
              <div className="space-y-3">
                <button
                  onClick={() => setIdentity({ ...identity, buildMode: 'with_links' })}
                  className={`w-full p-4 rounded-xl border text-left transition-all ${
                    identity.buildMode === 'with_links'
                      ? 'border-indigo-500 bg-indigo-500/20'
                      : 'border-slate-700 hover:border-slate-600'
                  }`}
                >
                  <div className="font-medium text-white">With Links</div>
                  <div className="text-sm text-slate-400">
                    Upload documents, URLs, and files for a comprehensive profile
                  </div>
                </button>
                
                <button
                  onClick={() => setIdentity({ ...identity, buildMode: 'name_only' })}
                  className={`w-full p-4 rounded-xl border text-left transition-all ${
                    identity.buildMode === 'name_only'
                      ? 'border-indigo-500 bg-indigo-500/20'
                      : 'border-slate-700 hover:border-slate-600'
                  }`}
                >
                  <div className="font-medium text-white">Name Only</div>
                  <div className="text-sm text-slate-400">
                    We&apos;ll research and build your profile automatically from public sources
                  </div>
                </button>
              </div>
            </div>
            
            <button
              onClick={handleIdentitySubmit}
              disabled={isLoading || !identity.fullName.trim()}
              className="w-full py-4 bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-semibold rounded-xl hover:from-indigo-500 hover:to-purple-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {isLoading ? 'Creating...' : 'Continue →'}
            </button>
          </div>
          
          <div className="mt-6 text-center text-xs text-slate-500">
            Step 1 of {identity.buildMode === 'name_only' ? '2' : '3'}
          </div>
        </div>
      </div>
    );
  }

  if (currentStep === 'hints') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-slate-800/50 backdrop-blur-xl rounded-2xl p-8 border border-slate-700/50">
          <div className="mb-8">
            <h1 className="text-3xl font-black text-white mb-2">Optional Details</h1>
            <p className="text-slate-400">Add more context to improve your profile</p>
          </div>
          
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Role</label>
              <input
                type="text"
                value={hints.role}
                onChange={(e) => setHints({ ...hints, role: e.target.value })}
                placeholder="e.g., Software Engineer"
                className="w-full px-4 py-3 bg-slate-900/50 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Location</label>
              <input
                type="text"
                value={hints.location}
                onChange={(e) => setHints({ ...hints, location: e.target.value })}
                placeholder="e.g., San Francisco, CA"
                className="w-full px-4 py-3 bg-slate-900/50 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Expertise Tags</label>
              <input
                type="text"
                placeholder="Add tags separated by commas"
                onChange={(e) => setHints({ 
                  ...hints, 
                  expertiseTags: e.target.value.split(',').map(t => t.trim()).filter(Boolean)
                })}
                className="w-full px-4 py-3 bg-slate-900/50 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            
            <div className="flex gap-3">
              <button
                onClick={() => handleHintsSubmit(true)}
                className="flex-1 py-3 border border-slate-600 text-slate-400 font-medium rounded-xl hover:border-slate-500 transition-all"
              >
                Skip
              </button>
              <button
                onClick={() => handleHintsSubmit(false)}
                disabled={isLoading}
                className="flex-1 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-semibold rounded-xl hover:from-indigo-500 hover:to-purple-500 transition-all"
              >
                Continue →
              </button>
            </div>
          </div>
          
          <div className="mt-6 text-center text-xs text-slate-500">
            Step 2 of 3
          </div>
        </div>
      </div>
    );
  }

  if (currentStep === 'content') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-slate-800/50 backdrop-blur-xl rounded-2xl p-8 border border-slate-700/50">
          <div className="mb-8">
            <h1 className="text-3xl font-black text-white mb-2">Add Content</h1>
            <p className="text-slate-400">Upload documents or add URLs to build your knowledge base</p>
          </div>
          
          {error && (
            <div className="mb-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}
          
          <div className="space-y-6">
            {/* URL Input */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">URLs</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="https://example.com/article"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      const value = (e.target as HTMLInputElement).value;
                      if (value) {
                        setContent({ ...content, urls: [...content.urls, value] });
                        (e.target as HTMLInputElement).value = '';
                      }
                    }
                  }}
                  className="flex-1 px-4 py-3 bg-slate-900/50 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              {content.urls.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {content.urls.map((url, idx) => (
                    <span key={idx} className="inline-flex items-center gap-1 px-2 py-1 bg-slate-700 rounded text-xs text-slate-300">
                      {url.slice(0, 30)}...
                      <button 
                        onClick={() => setContent({ 
                          ...content, 
                          urls: content.urls.filter((_, i) => i !== idx) 
                        })}
                        className="text-slate-400 hover:text-red-400"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
            
            {/* File Upload */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Files</label>
              <div className="border-2 border-dashed border-slate-700 rounded-xl p-6 text-center hover:border-indigo-500 transition-colors">
                <input
                  type="file"
                  multiple
                  onChange={(e) => {
                    const files = Array.from(e.target.files || []);
                    setContent({ ...content, files: [...content.files, ...files] });
                  }}
                  className="hidden"
                  id="file-upload"
                />
                <label htmlFor="file-upload" className="cursor-pointer">
                  <div className="text-slate-400 text-sm">
                    Drop files here or click to upload
                  </div>
                </label>
              </div>
              {content.files.length > 0 && (
                <div className="mt-2 space-y-1">
                  {content.files.map((file, idx) => (
                    <div key={idx} className="flex items-center justify-between px-3 py-2 bg-slate-700/50 rounded text-sm text-slate-300">
                      <span>{file.name}</span>
                      <button 
                        onClick={() => setContent({ 
                          ...content, 
                          files: content.files.filter((_, i) => i !== idx) 
                        })}
                        className="text-slate-400 hover:text-red-400"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            <button
              onClick={handleContentSubmit}
              disabled={isLoading || (content.urls.length === 0 && content.files.length === 0)}
              className="w-full py-4 bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-semibold rounded-xl hover:from-indigo-500 hover:to-purple-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {isLoading ? 'Uploading...' : 'Build My Profile →'}
            </button>
          </div>
          
          <div className="mt-6 text-center text-xs text-slate-500">
            Step 3 of 3
          </div>
        </div>
      </div>
    );
  }

  if (currentStep === 'building') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-slate-800/50 backdrop-blur-xl rounded-2xl p-8 border border-slate-700/50">
          <div className="text-center mb-8">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-r from-indigo-500 to-purple-500 flex items-center justify-center">
              <svg className="w-8 h-8 text-white animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            </div>
            <h1 className="text-2xl font-black text-white mb-2">
              {identity.buildMode === 'name_only' ? 'Researching...' : 'Building Your Profile...'}
            </h1>
            <p className="text-slate-400">
              {identity.buildMode === 'name_only' 
                ? 'Discovering public information about you'
                : 'Processing your content and building knowledge'
              }
            </p>
          </div>
          
          {renderProgressBar()}
          
          <div className="text-center">
            <div className="text-sm font-medium text-indigo-400 mb-2">
              {buildProgress.stage}
            </div>
            <div className="text-xs text-slate-500">
              {buildProgress.percent}% complete
            </div>
          </div>
          
          {Object.keys(buildProgress.stats).length > 0 && (
            <div className="mt-6 p-4 bg-slate-900/50 rounded-xl">
              <div className="grid grid-cols-2 gap-4 text-center">
                {buildProgress.stats.urls_crawled !== undefined && (
                  <div>
                    <div className="text-lg font-bold text-white">{buildProgress.stats.urls_crawled}</div>
                    <div className="text-xs text-slate-500">Sources Found</div>
                  </div>
                )}
                {buildProgress.stats.words_extracted !== undefined && (
                  <div>
                    <div className="text-lg font-bold text-white">
                      {Math.round(buildProgress.stats.words_extracted / 1000)}K
                    </div>
                    <div className="text-xs text-slate-500">Words Processed</div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (currentStep === 'complete') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-slate-800/50 backdrop-blur-xl rounded-2xl p-8 border border-slate-700/50 text-center">
          <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 flex items-center justify-center">
            <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
            </svg>
          </div>
          
          <h1 className="text-3xl font-black text-white mb-2">Profile Ready!</h1>
          <p className="text-slate-400 mb-8">
            Your verified profile is now live and ready to engage
          </p>
          
          <div className="space-y-3">
            <button
              onClick={handleComplete}
              className="w-full py-4 bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-semibold rounded-xl hover:from-indigo-500 hover:to-purple-500 transition-all"
            >
              Go to Profile →
            </button>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
