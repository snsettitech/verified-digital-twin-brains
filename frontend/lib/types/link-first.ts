/**
 * Link-First Persona Types
 * 
 * These types define the contract between frontend and backend
 * for the Link-First Persona onboarding flow.
 */

// =============================================================================
// Twin Status (matches backend state machine)
// =============================================================================

export type TwinStatus = 
  | 'draft'           // Initial state, awaiting content
  | 'ingesting'       // Content being processed
  | 'claims_ready'    // Claims extracted, awaiting review
  | 'clarification_pending'  // Clarification questions pending
  | 'persona_built'   // Persona compiled, awaiting activation
  | 'active';         // Ready for chat

// =============================================================================
// API Request/Response Types
// =============================================================================

export interface TwinCreateRequest {
  name: string;
  description?: string;
  specialization?: string;
  mode?: 'manual' | 'link_first';
  links?: string[];
  settings?: Record<string, unknown>;
  persona_v2_data?: Record<string, unknown>;
}

export interface TwinCreateResponse {
  id: string;
  name: string;
  status: TwinStatus;
  specialization: string;
  persona_v2?: {
    id: string;
    version: string;
    status: string;
  };
  link_first?: {
    status: string;
    links: string[];
    next_step: string;
  };
}

// =============================================================================
// Link-Compile Job Types
// =============================================================================

export type LinkCompileJobMode = 'A' | 'B' | 'C';
export type LinkCompileJobStatus = 
  | 'pending'
  | 'processing'
  | 'extracting_claims'
  | 'compiling_persona'
  | 'completed'
  | 'failed';

export interface LinkCompileJob {
  job_id: string;
  status: LinkCompileJobStatus;
  mode: LinkCompileJobMode;
  total_sources: number;
  processed_sources: number;
  extracted_claims: number;
  error_message?: string;
  created_at: string;
  updated_at?: string;
}

// =============================================================================
// Claim Types
// =============================================================================

export type ClaimType = 'preference' | 'belief' | 'heuristic' | 'value' | 'experience' | 'boundary';

export interface Claim {
  id: string;
  claim_text: string;
  claim_type: ClaimType;
  confidence: number;
  authority: string;
  verification_status: 'pending' | 'approved' | 'rejected';
  source_id: string;
  quote?: string;
}

export interface ClaimsResponse {
  twin_id: string;
  claims: Claim[];
  total_count: number;
}

// =============================================================================
// Clarification Types
// =============================================================================

export interface ClarificationQuestion {
  target_item_id: string;
  question: string;
  current_confidence: number;
  purpose: string;
}

export interface ClarificationQuestionsResponse {
  twin_id: string;
  questions: ClarificationQuestion[];
  low_confidence_count: number;
}

export interface ClarificationAnswerRequest {
  question_id: string;
  question: ClarificationQuestion;
  answer: string;
}

// =============================================================================
// Bio Types
// =============================================================================

export type BioType = 'one_liner' | 'short' | 'linkedin_about' | 'speaker_intro' | 'full';

export interface BioVariant {
  bio_type: BioType;
  bio_text: string;
  validation_status: 'valid' | 'invalid' | 'needs_claims';
}

export interface BiosResponse {
  twin_id: string;
  variants: BioVariant[];
}

// =============================================================================
// URL Validation
// =============================================================================

export interface UrlValidationResult {
  url: string;
  allowed: boolean;
  reason?: string;
  error_code?: string;
  crawl_delay?: number;
}

// =============================================================================
// State Transitions
// =============================================================================

export interface StateTransitionResponse {
  twin_id: string;
  status: TwinStatus;
}

export interface ActivateTwinRequest {
  final_name?: string;
}

export interface ActivateTwinResponse {
  twin_id: string;
  status: 'active';
  name: string;
  persona_spec_id?: string;
}

// =============================================================================
// Telemetry Events
// =============================================================================

export type LinkFirstTelemetryEvent =
  | 'link_first_onboarding_started'
  | 'link_first_twin_created'
  | 'ingestion_started'
  | 'claims_ready'
  | 'clarification_completed'
  | 'persona_activated';

export interface TelemetryProperties {
  twin_id?: string;
  mode?: string;
  url_count?: number;
  file_count?: number;
  [key: string]: unknown;
}
