'use client';

import React, { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import ChatInterface, { type ChatStreamEvent } from '@/components/Chat/ChatInterface';
import ContextPanel from '@/components/Chat/ContextPanel';
import FeatureGate from '@/components/ui/FeatureGate';
import { useTwin } from '@/lib/context/TwinContext';
import { isRuntimeFeatureEnabled } from '@/lib/features/runtimeFlags';
import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';
import { API_ENDPOINTS } from '@/lib/constants';

type ContextSnapshot = {
  queryClass?: string;
  answerabilityState?: string;
  plannerAction?: string;
  confidenceScore?: number;
  citations?: string[];
  citationDetails?: Array<{
    id: string;
    filename?: string | null;
    citation_url?: string | null;
  }>;
  usedOwnerMemory?: boolean;
  ownerMemoryTopics?: string[];
  retrievalStats?: Record<string, any>;
  selectedEvidenceBlockTypes?: string[];
};

const CONTEXT_FLUSH_MS = 120;

function DashboardChatPageContent() {
  const { activeTwin, isLoading, twins, setActiveTwin } = useTwin();
  const searchParams = useSearchParams();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [canonicalProfileId, setCanonicalProfileId] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<ContextSnapshot | null>(null);
  const [profileQuestions, setProfileQuestions] = useState<string[]>([]);
  const [profileQuestionCapacity, setProfileQuestionCapacity] = useState<number | null>(null);
  const pendingSnapshotRef = useRef<ContextSnapshot | null>(null);
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const chatEnabled = isRuntimeFeatureEnabled('dashboardChat');
  const contextPanelEnabled = isRuntimeFeatureEnabled('contextPanel');
  const requestedTwinId = searchParams.get('twinId');
  const twinId = activeTwin?.id;
  const effectiveTwinId = canonicalProfileId || twinId;
  const effectiveTwin = useMemo(() => {
    if (!effectiveTwinId) return null;
    return twins.find((t) => t.id === effectiveTwinId) || (activeTwin?.id === effectiveTwinId ? activeTwin : null);
  }, [effectiveTwinId, twins, activeTwin]);
  const chatSource = searchParams.get('source');
  const seededQuestion = searchParams.get('q');
  const canChat = useMemo(() => {
    const status = String(effectiveTwin?.status || '').toLowerCase();
    const byStatus = status === 'active' || status === 'persona_built' || status === 'live';
    const byLegacyFlag = !status && Boolean(effectiveTwin?.is_active);
    return byStatus || byLegacyFlag;
  }, [effectiveTwin]);

  useEffect(() => {
    let cancelled = false;

    async function resolveCanonicalProfile() {
      try {
        const response = await authFetchStandalone('/profile');
        if (!response.ok) return;
        const payload = await response.json();
        if (!cancelled) {
          setCanonicalProfileId(typeof payload?.id === 'string' ? payload.id : null);
        }
      } catch (error) {
        console.error('[DashboardChat] Failed to resolve canonical profile:', error);
      }
    }

    void resolveCanonicalProfile();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!requestedTwinId) return;
    if (canonicalProfileId && requestedTwinId !== canonicalProfileId) return;
    if (activeTwin?.id === requestedTwinId) return;
    const exists = twins.some((t) => t.id === requestedTwinId);
    if (!exists) return;
    setActiveTwin(requestedTwinId);
  }, [requestedTwinId, canonicalProfileId, activeTwin?.id, twins, setActiveTwin]);

  useEffect(() => {
    if (!canonicalProfileId) return;
    if (activeTwin?.id === canonicalProfileId) return;
    const exists = twins.some((t) => t.id === canonicalProfileId);
    if (!exists) return;
    setActiveTwin(canonicalProfileId);
  }, [canonicalProfileId, activeTwin?.id, twins, setActiveTwin]);

  useEffect(() => {
    let cancelled = false;

    async function loadProfileQuestions() {
      if (!effectiveTwinId || chatSource !== 'profile') {
        setProfileQuestions([]);
        setProfileQuestionCapacity(null);
        return;
      }

      try {
        const response = await authFetchStandalone(API_ENDPOINTS.TWIN_PROFILE_INSIGHTS(effectiveTwinId));
        if (!response.ok) {
          throw new Error(`Failed to load profile insights: ${response.status}`);
        }
        const payload = await response.json();
        const suggested = Array.isArray(payload?.question_suggestions)
          ? payload.question_suggestions
              .map((q: unknown) => (typeof q === 'string' ? q.trim() : ''))
              .filter((q: string) => q.length > 0)
          : [];
        const withSeed: string[] = seededQuestion && seededQuestion.trim()
          ? [seededQuestion.trim(), ...suggested]
          : suggested;
        const deduped: string[] = Array.from(new Set(withSeed)).slice(0, 12);

        if (!cancelled) {
          setProfileQuestions(deduped);
          const capacity = Number(payload?.question_capacity_estimate);
          setProfileQuestionCapacity(Number.isFinite(capacity) ? Math.max(0, Math.floor(capacity)) : null);
        }
      } catch (error) {
        console.error('[DashboardChat] Failed to load profile questions:', error);
        if (!cancelled) {
          const fallback = seededQuestion && seededQuestion.trim() ? [seededQuestion.trim()] : [];
          setProfileQuestions(fallback);
          setProfileQuestionCapacity(null);
        }
      }
    }

    void loadProfileQuestions();
    return () => {
      cancelled = true;
    };
  }, [effectiveTwinId, chatSource, seededQuestion]);

  const flushSnapshot = useCallback(() => {
    if (!pendingSnapshotRef.current) return;
    setSnapshot((prev) => ({ ...(prev || {}), ...(pendingSnapshotRef.current as ContextSnapshot) }));
    pendingSnapshotRef.current = null;
    flushTimerRef.current = null;
  }, []);

  const scheduleSnapshotFlush = useCallback(() => {
    if (flushTimerRef.current) return;
    flushTimerRef.current = setTimeout(flushSnapshot, CONTEXT_FLUSH_MS);
  }, [flushSnapshot]);

  const handleStreamEvent = useCallback((event: ChatStreamEvent) => {
    if (event.type !== 'metadata') return;
    const payload = event.payload || {};
    const next: ContextSnapshot = {
      queryClass: payload.query_class,
      answerabilityState: payload.answerability_state,
      plannerAction: payload.planner_action,
      confidenceScore: payload.confidence_score,
      citations: Array.isArray(payload.citations) ? payload.citations : [],
      citationDetails: Array.isArray(payload.citation_details) ? payload.citation_details : [],
      usedOwnerMemory: Boolean(payload.owner_memory_refs?.length || payload.used_owner_memory),
      ownerMemoryTopics: Array.isArray(payload.owner_memory_topics) ? payload.owner_memory_topics : [],
      retrievalStats: payload.retrieval_stats || payload.debug_snapshot?.retrieval_stats || {},
      selectedEvidenceBlockTypes:
        payload.selected_evidence_block_types || payload.debug_snapshot?.selected_evidence_block_types || [],
    };
    pendingSnapshotRef.current = next;
    scheduleSnapshotFlush();
  }, [scheduleSnapshotFlush]);

  useEffect(() => {
    return () => {
      if (flushTimerRef.current) {
        clearTimeout(flushTimerRef.current);
        flushTimerRef.current = null;
      }
    };
  }, []);

  const content = useMemo(() => {
    if (isLoading) {
      return (
        <div className="flex min-h-[420px] items-center justify-center rounded-2xl border border-slate-200 bg-white">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
        </div>
      );
    }

    if (!effectiveTwinId) {
      return (
        <div className="rounded-2xl border border-slate-200 bg-white p-8">
          <h2 className="text-xl font-bold text-slate-900">No Twin Selected</h2>
          <p className="mt-2 text-sm text-slate-600">Select a twin from the sidebar to start chatting.</p>
        </div>
      );
    }

    if (!canChat) {
      return (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-8">
          <h2 className="text-xl font-bold text-amber-900">Profile Still Building</h2>
          <p className="mt-2 text-sm text-amber-800">
            Chat unlocks after research and ingestion complete for this profile.
          </p>
        </div>
      );
    }

    return (
      <div className="flex flex-col gap-4 xl:flex-row">
        <div className="min-h-[620px] flex-1 overflow-hidden rounded-2xl border border-slate-200 bg-white">
          {chatSource === 'profile' && profileQuestionCapacity !== null ? (
            <div className="border-b border-slate-200 bg-amber-50 px-4 py-3 text-xs text-slate-700">
              Profile research suggests about <strong>{profileQuestionCapacity.toLocaleString()}</strong> answerable
              questions. Start with a follow-up prompt below or ask your own question.
            </div>
          ) : null}
          <ChatInterface
            twinId={effectiveTwinId}
            tenantId={activeTwin?.tenant_id}
            conversationId={conversationId}
            onConversationStarted={setConversationId}
            onStreamEvent={handleStreamEvent}
            presetQuestions={profileQuestions}
            initialInput={seededQuestion}
          />
        </div>
        {contextPanelEnabled ? <ContextPanel snapshot={snapshot} /> : null}
      </div>
    );
  }, [
    isLoading,
    effectiveTwinId,
    canChat,
    activeTwin?.tenant_id,
    conversationId,
    handleStreamEvent,
    contextPanelEnabled,
    snapshot,
    chatSource,
    profileQuestionCapacity,
    profileQuestions,
    seededQuestion,
  ]);

  return (
    <FeatureGate
      enabled={chatEnabled}
      title="Chat Workspace"
      description="Enable NEXT_PUBLIC_FF_DASHBOARD_CHAT to turn on the dashboard chat workspace."
    >
      <div className="space-y-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-slate-900">Chat</h1>
          <p className="mt-1 text-sm text-slate-600">
            Document-grounded chat with streaming responses and structured context visibility.
          </p>
        </div>
        {content}
      </div>
    </FeatureGate>
  );
}

function DashboardChatFallback() {
  return (
    <div className="flex min-h-[420px] items-center justify-center rounded-2xl border border-slate-200 bg-white">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
    </div>
  );
}

export default function DashboardChatPage() {
  return (
    <Suspense fallback={<DashboardChatFallback />}>
      <DashboardChatPageContent />
    </Suspense>
  );
}
