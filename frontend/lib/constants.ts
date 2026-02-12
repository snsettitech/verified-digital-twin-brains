/**
 * Centralized API Configuration
 * 
 * This is the SINGLE SOURCE OF TRUTH for API configuration.
 * Do NOT define API_BASE_URL in individual files.
 */

// Default values for Vercel deployments (when env vars not set in dashboard)
const DEFAULT_SUPABASE_URL = 'https://jvtffdbuwyhmcynauety.supabase.co';
const DEFAULT_SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp2dGZmZGJ1d3lobWN5bmF1ZXR5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjYwMTY1MzksImV4cCI6MjA4MTU5MjUzOX0.tRpBHBhL2GM9s6sSncrVrNnmtwxrzED01SzwjKRb37E';
const DEFAULT_BACKEND_URL = 'https://verified-digital-twin-brains.onrender.com';

function getEnvVar(name: string, defaultValue?: string): string {
  const value = process.env[name] || defaultValue;
  if (!value) {
    console.warn(`[WARN] Missing environment variable: ${name}, using fallback`);
    return '';
  }
  return value.replace(/\/$/, ''); // Remove trailing slash
}

/**
 * The base URL for all API requests.
 * Uses default backend URL if environment variable not set.
 */
export const API_BASE_URL = getEnvVar('NEXT_PUBLIC_BACKEND_URL', DEFAULT_BACKEND_URL) || DEFAULT_BACKEND_URL;

/**
 * Supabase configuration
 * Uses defaults for Vercel deployments when env vars not set in dashboard
 */
export const SUPABASE_URL = getEnvVar('NEXT_PUBLIC_SUPABASE_URL', DEFAULT_SUPABASE_URL) || DEFAULT_SUPABASE_URL;
export const SUPABASE_ANON_KEY = getEnvVar('NEXT_PUBLIC_SUPABASE_ANON_KEY', DEFAULT_SUPABASE_ANON_KEY) || DEFAULT_SUPABASE_ANON_KEY;

/**
 * Frontend URL (for redirects, sharing, etc.)
 */
export const FRONTEND_URL = process.env.NEXT_PUBLIC_FRONTEND_URL || 
  (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000');

/**
 * API endpoint paths (centralized to prevent typos)
 */
export const API_ENDPOINTS = {
  // Health/Version
  HEALTH: '/health',
  VERSION: '/version',
  
  // Twins
  TWINS: '/twins',
  TWIN_DETAIL: (twinId: string) => `/twins/${twinId}`,
  TWIN_SOURCES: (twinId: string) => `/sources/${twinId}`,
  TWIN_SOURCE_DETAIL: (twinId: string, sourceId: string) => `/sources/${twinId}/${sourceId}`,
  TWIN_KNOWLEDGE_PROFILE: (twinId: string) => `/twins/${twinId}/knowledge-profile`,
  TWIN_GRAPH: (twinId: string) => `/twins/${twinId}/graph`,
  TWIN_GRAPH_STATS: (twinId: string) => `/twins/${twinId}/graph-stats`,
  
  // Chat
  CHAT: (twinId: string) => `/chat/${twinId}`,
  CONVERSATIONS: (twinId: string) => `/conversations/${twinId}`,
  MESSAGES: (conversationId: string) => `/conversations/${conversationId}/messages`,
  
  // Interview
  INTERVIEW_SESSIONS: '/api/interview/sessions',
  INTERVIEW_REALTIME: '/api/interview/realtime/sessions',
  INTERVIEW_FINALIZE: (sessionId: string) => `/api/interview/sessions/${sessionId}/finalize`,
  
  // Ingestion
  INGEST_FILE: (twinId: string) => `/ingest/file/${twinId}`,
  INGEST_URL: (twinId: string) => `/ingest/url/${twinId}`,
  INGEST_YOUTUBE: (twinId: string) => `/ingest/youtube/${twinId}`,
  INGEST_PODCAST: (twinId: string) => `/ingest/podcast/${twinId}`,
  INGEST_X: (twinId: string) => `/ingest/x/${twinId}`,
  INGEST_EXTRACT_NODES: (sourceId: string) => `/ingest/extract-nodes/${sourceId}`,
  INGEST_REALTIME_START: (twinId: string) => `/ingest/realtime/sessions/${twinId}/start`,
  INGEST_REALTIME_APPEND: (sessionId: string) => `/ingest/realtime/sessions/${sessionId}/append`,
  INGEST_REALTIME_COMMIT: (sessionId: string) => `/ingest/realtime/sessions/${sessionId}/commit`,
  INGEST_REALTIME_SESSION: (sessionId: string) => `/ingest/realtime/sessions/${sessionId}`,
  INGEST_REALTIME_HEALTH: '/ingest/realtime/health',
  
  // Jobs
  JOBS: '/jobs',
  JOB_DETAIL: (jobId: string) => `/jobs/${jobId}`,
  JOB_LOGS: (jobId: string) => `/jobs/${jobId}/logs`,
  JOB_RETRY: (jobId: string) => `/jobs/${jobId}/retry`,
  
  // Memory/Training
  OWNER_MEMORY: (twinId: string) => `/twins/${twinId}/owner-memory`,
  OWNER_MEMORY_DETAIL: (twinId: string, memoryId: string) => `/twins/${twinId}/owner-memory/${memoryId}`,
  CLARIFICATIONS: (twinId: string) => `/twins/${twinId}/clarifications`,
  CLARIFICATION_RESOLVE: (twinId: string, clarificationId: string) => 
    `/twins/${twinId}/clarifications/${clarificationId}/resolve`,
  TRAINING_SESSIONS: (twinId: string) => `/twins/${twinId}/training-sessions`,
  TRAINING_SESSION_START: (twinId: string) => `/twins/${twinId}/training-sessions/start`,
  TRAINING_SESSION_STOP: (twinId: string, sessionId: string) => 
    `/twins/${twinId}/training-sessions/${sessionId}/stop`,
  TRAINING_SESSION_ACTIVE: (twinId: string) => `/twins/${twinId}/training-sessions/active`,
  
  // Metrics
  METRICS_DASHBOARD: (twinId: string) => `/metrics/dashboard/${twinId}`,
  METRICS_ACTIVITY: (twinId: string) => `/metrics/activity/${twinId}`,
  METRICS_CONVERSATIONS: (twinId: string) => `/metrics/conversations/${twinId}`,
  METRICS_TOP_QUESTIONS: (twinId: string) => `/metrics/top-questions/${twinId}`,
  
  // Audio/Voice
  AUDIO_VOICES: '/audio/voices',
  AUDIO_SETTINGS: (twinId: string) => `/audio/settings/${twinId}`,
  AUDIO_TTS: (twinId: string) => `/audio/tts/${twinId}`,
  
  // Auth
  AUTH_INVITATION: (token: string) => `/auth/invitation/${token}`,
  AUTH_ACCEPT_INVITATION: '/auth/accept-invitation',
  
  // Specializations
  SPECIALIZATIONS: '/specializations',
  
  // Cognitive
  COGNITIVE_PROFILES: (twinId: string) => `/cognitive/profiles/${twinId}`,
  COGNITIVE_PROFILE_VERSIONS: (twinId: string) => `/cognitive/profiles/${twinId}/versions`,
  COGNITIVE_INTERVIEW: (twinId: string) => `/cognitive/interview/${twinId}`,
  
  // Feedback
  FEEDBACK: '/feedback',
  FEEDBACK_PUBLIC: '/feedback/public',
} as const;
