'use client';

import { useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useTwin, Twin, getOnboardingResumeUrl } from '@/lib/context/TwinContext';

export interface ChatGateResult {
  canChat: boolean;
  isLoading: boolean;
  checkAndRedirect: (twinId?: string) => boolean;
  getBlockReason: (twin?: Twin | null) => string | null;
}

/**
 * Hook to gate chat access based on twin status.
 * Redirects to onboarding if twin is not active.
 */
export function useChatGating(): ChatGateResult {
  const router = useRouter();
  const { activeTwin, twins, isLoading } = useTwin();

  const getBlockReason = useCallback((twin?: Twin | null): string | null => {
    const targetTwin = twin || activeTwin;
    
    if (!targetTwin) {
      return 'No twin selected';
    }

    if (targetTwin.status === 'active' || targetTwin.is_active) {
      return null;
    }

    // Map status to user-friendly message
    switch (targetTwin.status) {
      case 'draft':
        return 'Your Digital Twin is in draft mode. Continue setup to activate it.';
      case 'ingesting':
        return 'Your content is being processed. Please wait for processing to complete.';
      case 'claims_ready':
        return 'Please review the extracted claims from your content.';
      case 'clarification_pending':
        return 'Please answer a few clarification questions to improve your persona.';
      case 'persona_built':
        return 'Your persona is ready. Activate it to start chatting.';
      default:
        return 'Your Digital Twin is not yet active. Continue setup to activate it.';
    }
  }, [activeTwin]);

  const checkAndRedirect = useCallback((twinId?: string): boolean => {
    const targetTwinId = twinId || activeTwin?.id;
    
    if (!targetTwinId) {
      return false;
    }

    // Find the twin
    const twin = twins.find(t => t.id === targetTwinId) || activeTwin;
    
    if (!twin) {
      return false;
    }

    // Check if can chat
    const canChat = twin.status === 'active' || twin.is_active;
    
    if (!canChat) {
      // Redirect to onboarding resume
      router.push(getOnboardingResumeUrl(targetTwinId));
      return false;
    }

    return true;
  }, [activeTwin, twins, router]);

  return {
    canChat: !!activeTwin && (activeTwin.status === 'active' || activeTwin.is_active),
    isLoading,
    checkAndRedirect,
    getBlockReason,
  };
}

/**
 * Handle 403 errors from chat API (twin not active)
 */
export function handleChat403(error: Response, router: ReturnType<typeof useRouter>): boolean {
  if (error.status === 403) {
    // Extract twin ID from URL if present
    const url = error.url;
    const match = url.match(/\/chat\/(\w+)/);
    const twinId = match?.[1];
    
    if (twinId) {
      router.push(getOnboardingResumeUrl(twinId));
      return true;
    }
  }
  return false;
}
