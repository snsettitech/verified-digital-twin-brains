/**
 * Chat Gating Hook
 * 
 * Ensures chat access is blocked for non-active twins.
 * Redirects to onboarding resume if needed.
 */

import { useCallback } from 'react';
import { useRouter } from 'next/navigation';

export type TwinStatus = 'draft' | 'ingesting' | 'claims_ready' | 'clarification_pending' | 'persona_built' | 'active';

export interface Twin {
  id: string;
  name: string;
  status: TwinStatus;
}

export interface ChatGateResult {
  canChat: boolean;
  isLoading: boolean;
  checkAndRedirect: (twin?: Twin | null) => boolean;
  getResumeUrl: (twinId: string) => string;
  handle403Error: (response: Response) => boolean;
}

/**
 * Hook to gate chat access based on twin status
 */
export function useChatGating(): ChatGateResult {
  const router = useRouter();

  const getResumeUrl = useCallback((twinId: string): string => {
    return `/onboarding?twinId=${encodeURIComponent(twinId)}`;
  }, []);

  const checkAndRedirect = useCallback((twin?: Twin | null): boolean => {
    if (!twin) {
      return false;
    }

    const canChat = twin.status === 'active';
    
    if (!canChat) {
      router.push(getResumeUrl(twin.id));
      return false;
    }

    return true;
  }, [getResumeUrl, router]);

  const handle403Error = useCallback((response: Response): boolean => {
    if (response.status === 403) {
      // Extract twin ID from URL if present
      const url = response.url;
      const match = url.match(/\/chat\/(\w+)/);
      const twinId = match?.[1];
      
      if (twinId) {
        router.push(getResumeUrl(twinId));
        return true;
      }
    }
    return false;
  }, [getResumeUrl, router]);

  return {
    canChat: false, // Will be set by caller based on twin status
    isLoading: false,
    checkAndRedirect,
    getResumeUrl,
    handle403Error,
  };
}

/**
 * Standalone function to handle chat API errors
 */
export async function handleChatError(
  response: Response,
  router: ReturnType<typeof useRouter>
): Promise<{ handled: boolean; shouldRedirect: string | null }> {
  if (response.status === 403) {
    const data = await response.json().catch(() => ({}));
    
    // Check if it's a twin not active error
    if (data.detail?.includes('not active') || data.status) {
      const url = response.url;
      const match = url.match(/\/chat\/(\w+)/);
      const twinId = match?.[1] || data.twin_id;
      
      if (twinId) {
        const resumeUrl = `/onboarding?twinId=${encodeURIComponent(twinId)}`;
        return { handled: true, shouldRedirect: resumeUrl };
      }
    }
  }
  
  return { handled: false, shouldRedirect: null };
}
