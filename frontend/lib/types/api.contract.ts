/**
 * API Contract Types with Zod Validation
 * 
 * These types ensure frontend-backend contract alignment.
 * Used for runtime validation at API boundaries.
 */

import { z } from 'zod';

// =============================================================================
// Twin Status
// =============================================================================

export const TwinStatusSchema = z.enum([
  'draft',
  'ingesting', 
  'claims_ready',
  'clarification_pending',
  'persona_built',
  'active'
]);

export type TwinStatus = z.infer<typeof TwinStatusSchema>;

// =============================================================================
// Twin Create Request/Response
// =============================================================================

export const TwinCreateRequestSchema = z.object({
  name: z.string().min(2).max(100),
  description: z.string().max(500).optional(),
  specialization: z.string().default('vanilla'),
  mode: z.enum(['manual', 'link_first']).optional(),
  links: z.array(z.string().url()).max(10).optional(),
  settings: z.record(z.unknown()).optional(),
  persona_v2_data: z.record(z.unknown()).optional(),
});

export type TwinCreateRequest = z.infer<typeof TwinCreateRequestSchema>;

export const TwinCreateResponseSchema = z.object({
  id: z.string(),
  name: z.string(),
  status: TwinStatusSchema,
  specialization: z.string(),
  settings: z.record(z.unknown()).optional(),
  persona_v2: z.object({
    id: z.string(),
    version: z.string(),
    status: z.string(),
  }).optional(),
  link_first: z.object({
    status: z.string(),
    links: z.array(z.string()),
    next_step: z.string(),
  }).optional(),
});

export type TwinCreateResponse = z.infer<typeof TwinCreateResponseSchema>;

// =============================================================================
// Link-Compile Job Types
// =============================================================================

export const LinkCompileJobModeSchema = z.enum(['A', 'B', 'C']);
export const LinkCompileJobStatusSchema = z.enum([
  'pending',
  'processing',
  'extracting_claims',
  'compiling_persona',
  'completed',
  'failed'
]);

export const LinkCompileJobSchema = z.object({
  job_id: z.string(),
  status: LinkCompileJobStatusSchema,
  mode: LinkCompileJobModeSchema,
  total_sources: z.number().default(0),
  processed_sources: z.number().default(0),
  extracted_claims: z.number().default(0),
  error_message: z.string().optional(),
  created_at: z.string(),
  updated_at: z.string().optional(),
});

export type LinkCompileJob = z.infer<typeof LinkCompileJobSchema>;

// Mode A: Export Upload
export const ModeARequestSchema = z.object({
  twin_id: z.string(),
  files: z.instanceof(File).array().min(1).max(10),
});

export type ModeARequest = z.infer<typeof ModeARequestSchema>;

// Mode B: Paste/Import
export const ModeBRequestSchema = z.object({
  twin_id: z.string(),
  content: z.string().min(10).max(100000),
  title: z.string().max(200).optional(),
  source_context: z.string().optional(),
});

export type ModeBRequest = z.infer<typeof ModeBRequestSchema>;

// Mode C: Web Fetch
export const ModeCRequestSchema = z.object({
  twin_id: z.string(),
  urls: z.array(z.string().url()).min(1).max(10),
});

export type ModeCRequest = z.infer<typeof ModeCRequestSchema>;

// =============================================================================
// Claim Types
// =============================================================================

export const ClaimTypeSchema = z.enum([
  'preference',
  'belief',
  'heuristic',
  'value',
  'experience',
  'boundary',
  'uncertain'
]);

export const ClaimSchema = z.object({
  id: z.string(),
  claim_text: z.string(),
  claim_type: ClaimTypeSchema,
  confidence: z.number().min(0).max(1),
  authority: z.enum(['extracted', 'owner_direct', 'inferred', 'uncertain']),
  verification_status: z.enum(['pending', 'approved', 'rejected']),
  source_id: z.string(),
  quote: z.string().optional(),
});

export type Claim = z.infer<typeof ClaimSchema>;

export const ClaimsResponseSchema = z.object({
  twin_id: z.string(),
  claims: z.array(ClaimSchema),
  total_count: z.number(),
});

export type ClaimsResponse = z.infer<typeof ClaimsResponseSchema>;

// =============================================================================
// Clarification Types
// =============================================================================

export const ClarificationQuestionSchema = z.object({
  target_item_id: z.string(),
  question: z.string(),
  current_confidence: z.number().min(0).max(1),
  purpose: z.string(),
});

export type ClarificationQuestion = z.infer<typeof ClarificationQuestionSchema>;

export const ClarificationQuestionsResponseSchema = z.object({
  twin_id: z.string(),
  questions: z.array(ClarificationQuestionSchema),
  low_confidence_count: z.number(),
});

export type ClarificationQuestionsResponse = z.infer<typeof ClarificationQuestionsResponseSchema>;

export const ClarificationAnswerRequestSchema = z.object({
  question_id: z.string(),
  question: z.record(z.unknown()),
  answer: z.string().min(1).max(5000),
});

export type ClarificationAnswerRequest = z.infer<typeof ClarificationAnswerRequestSchema>;

// =============================================================================
// Bio Types
// =============================================================================

export const BioTypeSchema = z.enum([
  'one_liner',
  'short',
  'linkedin_about',
  'speaker_intro',
  'full'
]);

export const BioVariantSchema = z.object({
  bio_type: BioTypeSchema,
  bio_text: z.string(),
  validation_status: z.enum(['valid', 'invalid', 'needs_claims']),
});

export type BioVariant = z.infer<typeof BioVariantSchema>;

export const BiosResponseSchema = z.object({
  twin_id: z.string(),
  variants: z.array(BioVariantSchema),
});

export type BiosResponse = z.infer<typeof BiosResponseSchema>;

// =============================================================================
// State Transitions
// =============================================================================

export const StateTransitionResponseSchema = z.object({
  twin_id: z.string(),
  status: TwinStatusSchema,
});

export type StateTransitionResponse = z.infer<typeof StateTransitionResponseSchema>;

export const ActivateTwinRequestSchema = z.object({
  final_name: z.string().min(2).max(100).optional(),
});

export type ActivateTwinRequest = z.infer<typeof ActivateTwinRequestSchema>;

export const ActivateTwinResponseSchema = z.object({
  twin_id: z.string(),
  status: z.literal('active'),
  name: z.string(),
  persona_spec_id: z.string().optional(),
});

export type ActivateTwinResponse = z.infer<typeof ActivateTwinResponseSchema>;

// =============================================================================
// URL Validation
// =============================================================================

export const UrlValidationResultSchema = z.object({
  url: z.string(),
  allowed: z.boolean(),
  reason: z.string().optional(),
  error_code: z.string().optional(),
  crawl_delay: z.number().optional(),
});

export type UrlValidationResult = z.infer<typeof UrlValidationResultSchema>;

// =============================================================================
// Helper Functions for Runtime Validation
// =============================================================================

export function validateTwinCreateRequest(data: unknown): TwinCreateRequest {
  return TwinCreateRequestSchema.parse(data);
}

export function validateTwinCreateResponse(data: unknown): TwinCreateResponse {
  return TwinCreateResponseSchema.parse(data);
}

export function validateClaimsResponse(data: unknown): ClaimsResponse {
  return ClaimsResponseSchema.parse(data);
}

export function validateLinkCompileJob(data: unknown): LinkCompileJob {
  return LinkCompileJobSchema.parse(data);
}

// Safe validators (return null instead of throwing)
export function safeValidateTwinCreateRequest(data: unknown): TwinCreateRequest | null {
  const result = TwinCreateRequestSchema.safeParse(data);
  return result.success ? result.data : null;
}

export function safeValidateTwinStatus(data: unknown): TwinStatus | null {
  const result = TwinStatusSchema.safeParse(data);
  return result.success ? result.data : null;
}
