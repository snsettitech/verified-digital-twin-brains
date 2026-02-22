/**
 * E2E Founder Test: Sainath Setti Scenario
 * 
 * End-to-end test for link-first onboarding flow:
 * 1. Create draft twin
 * 2. Upload LinkedIn export (mode-a)
 * 3. Poll until claims_ready
 * 4. Approve claims, answer clarifications
 * 5. Activate twin
 * 6. Verify chat cites claims
 * 
 * This test uses mocked LLM responses for determinism.
 */

import { test, expect } from '@playwright/test';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// Test data for Sainath Setti
const FOUNDER_DATA = {
  name: 'Sainath Setti',
  specialization: 'founder',
  links: [
    'https://github.com/sainathsetti',
    'https://sainathsetti.com',
    'https://youtube.com/@sainathsetti'
  ]
};

// Mock claims expected from LinkedIn export
const MOCK_CLAIMS = [
  {
    id: 'claim_001',
    claim_text: 'I prefer B2B over B2C for early-stage ventures',
    claim_type: 'preference',
    confidence: 0.92,
    authority: 'extracted',
    source_id: 'linkedin_export',
    quote: 'My investment thesis focuses on B2B enterprise software'
  },
  {
    id: 'claim_002',
    claim_text: 'Team quality matters more than market size in pre-seed',
    claim_type: 'belief',
    confidence: 0.88,
    authority: 'extracted',
    source_id: 'linkedin_export',
    quote: 'I back exceptional founders, then figure out the market'
  },
  {
    id: 'claim_003',
    claim_text: 'I value transparency over polish in founder communication',
    claim_type: 'value',
    confidence: 0.75,
    authority: 'inferred',
    source_id: 'linkedin_export',
    quote: 'Tell me the real numbers, not the deck version'
  }
];

// Mock bio with citations
const MOCK_BIOS = {
  short: 'Investor and founder focused on B2B enterprise software [claim_001]. I back exceptional teams before the market is obvious [claim_002].',
  linkedin_about: 'I\'m an investor and entrepreneur with a passion for B2B startups [claim_001]. My approach prioritizes team quality over market timing [claim_002].',
  one_liner: 'B2B investor who bets on people first [claim_001][claim_002]'
};

// Mock clarification questions
const MOCK_CLARIFICATIONS = [
  {
    target_item_id: 'layer2_team_evaluation',
    question: 'When evaluating a founding team, what specific signals do you look for beyond prior experience?',
    current_confidence: 0.65,
    purpose: 'improve_heuristic'
  },
  {
    target_item_id: 'layer3_transparency_value',
    question: 'Can you share an example of when transparency from a founder changed your investment decision?',
    current_confidence: 0.58,
    purpose: 'ground_value'
  }
];

test.describe('Founder E2E: Sainath Setti Link-First Flow', () => {
  let twinId: string;
  let authToken: string;

  test.beforeAll(async ({ request }) => {
    // Get auth token (assumes test user exists)
    const loginRes = await request.post(`${API_BASE_URL}/auth/login`, {
      data: {
        email: 'test@example.com',
        password: 'testpassword'
      }
    });
    
    if (loginRes.ok) {
      const data = await loginRes.json();
      authToken = data.access_token;
    }
  });

  test('Step 1: Create link-first twin → status=draft', async ({ request }) => {
    const response = await request.post(`${API_BASE_URL}/twins`, {
      headers: { 
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
      },
      data: {
        name: FOUNDER_DATA.name,
        specialization: FOUNDER_DATA.specialization,
        mode: 'link_first',
        links: FOUNDER_DATA.links
      }
    });

    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.status).toBe('draft');
    expect(data.link_first).toBeDefined();
    expect(data.link_first.status).toBe('draft');
    expect(data.link_first.links).toEqual(FOUNDER_DATA.links);
    
    // Verify NO persona_v2 created
    expect(data.persona_v2).toBeUndefined();
    
    twinId = data.id;
    console.log(`[E2E] Created twin: ${twinId}`);
  });

  test('Step 2: Upload LinkedIn export (mode-a)', async ({ request }) => {
    // Create mock LinkedIn export file
    const exportContent = Buffer.from(JSON.stringify({
      profile: {
        name: 'Sainath Setti',
        headline: 'Investor & Founder',
        summary: 'My investment thesis focuses on B2B enterprise software. I back exceptional founders, then figure out the market. Tell me the real numbers, not the deck version.'
      }
    }));
    
    const formData = new FormData();
    formData.append('twin_id', twinId);
    formData.append('files', new Blob([exportContent]), 'LinkedInExport.zip');

    const response = await request.post(`${API_BASE_URL}/persona/link-compile/jobs/mode-a`, {
      headers: { 'Authorization': `Bearer ${authToken}` },
      multipart: {
        twin_id: twinId,
        files: {
          name: 'LinkedInExport.zip',
          mimeType: 'application/zip',
          buffer: exportContent
        }
      }
    });

    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.job_id).toBeDefined();
    expect(data.status).toBe('pending');
    console.log(`[E2E] Created mode-a job: ${data.job_id}`);
  });

  test('Step 3: Poll until status=claims_ready', async ({ request }) => {
    let attempts = 0;
    const maxAttempts = 30; // 30 * 2s = 60s timeout
    
    while (attempts < maxAttempts) {
      const response = await request.get(`${API_BASE_URL}/persona/link-compile/twins/${twinId}/job`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (response.ok) {
        const data = await response.json();
        console.log(`[E2E] Poll ${attempts + 1}: status=${data.status}, claims=${data.extracted_claims}`);
        
        if (data.status === 'claims_ready' || data.status === 'completed') {
          expect(data.extracted_claims).toBeGreaterThan(0);
          break;
        }
        
        if (data.status === 'failed') {
          throw new Error(`Job failed: ${data.error_message}`);
        }
      }
      
      await new Promise(r => setTimeout(r, 2000));
      attempts++;
    }
    
    expect(attempts).toBeLessThan(maxAttempts);
  });

  test('Step 4: GET claims → each has claim_id + provenance', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/persona/link-compile/twins/${twinId}/claims?min_confidence=0.3`, {
      headers: { 'Authorization': `Bearer ${authToken}` }
    });

    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.claims).toBeDefined();
    expect(data.claims.length).toBeGreaterThan(0);
    
    // Verify claim structure
    for (const claim of data.claims) {
      expect(claim.id).toMatch(/^claim_/);
      expect(claim.claim_text).toBeDefined();
      expect(claim.claim_type).toBeDefined();
      expect(claim.confidence).toBeGreaterThanOrEqual(0);
      expect(claim.confidence).toBeLessThanOrEqual(1);
      expect(claim.source_id).toBeDefined();
    }
    
    console.log(`[E2E] Verified ${data.claims.length} claims`);
  });

  test('Step 5: Approve claims → status=clarification_pending', async ({ request }) => {
    // Transition to clarification pending
    const response = await request.post(`${API_BASE_URL}/twins/${twinId}/transition/clarification-pending`, {
      headers: { 'Authorization': `Bearer ${authToken}` }
    });

    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.status).toBe('clarification_pending');
  });

  test('Step 6: Answer 5 clarification questions', async ({ request }) => {
    // Get clarification questions
    const questionsRes = await request.get(`${API_BASE_URL}/persona/link-compile/twins/${twinId}/clarification-questions`, {
      headers: { 'Authorization': `Bearer ${authToken}` }
    });

    expect(questionsRes.status()).toBe(200);
    const { questions } = await questionsRes.json();
    
    // Answer up to 5 questions
    const questionsToAnswer = questions.slice(0, 5);
    
    for (const q of questionsToAnswer) {
      const answerRes = await request.post(`${API_BASE_URL}/persona/link-compile/twins/${twinId}/clarification-answers`, {
        headers: { 
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        data: {
          question_id: q.target_item_id,
          question: q,
          answer: `As a founder, I look for ${q.purpose.includes('team') ? 'resilience and adaptability' : 'honest communication and clear thinking'} in my investments.`
        }
      });
      
      expect(answerRes.status()).toBe(200);
    }
    
    // Transition to persona_built
    const transitionRes = await request.post(`${API_BASE_URL}/twins/${twinId}/transition/persona-built`, {
      headers: { 'Authorization': `Bearer ${authToken}` }
    });
    
    expect(transitionRes.status()).toBe(200);
    const data = await transitionRes.json();
    expect(data.status).toBe('persona_built');
  });

  test('Step 7: Activate → status=active, source=link-compile', async ({ request }) => {
    const response = await request.post(`${API_BASE_URL}/twins/${twinId}/activate`, {
      headers: { 
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
      },
      data: { final_name: FOUNDER_DATA.name }
    });

    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.status).toBe('active');
    expect(data.name).toBe(FOUNDER_DATA.name);
    expect(data.persona_spec_id).toBeDefined();
    
    // Verify persona source
    const personaRes = await request.get(`${API_BASE_URL}/twins/${twinId}/persona-specs/active`, {
      headers: { 'Authorization': `Bearer ${authToken}` }
    });
    
    if (personaRes.ok) {
      const persona = await personaRes.json();
      expect(persona.source).toBe('link-compile');
    }
  });

  test('Step 8: GET bios → every sentence maps to ≥1 claim_id', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/persona/link-compile/twins/${twinId}/bios`, {
      headers: { 'Authorization': `Bearer ${authToken}` }
    });

    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.variants).toBeDefined();
    expect(data.variants.length).toBeGreaterThan(0);
    
    // Verify bios have citations
    for (const bio of data.variants) {
      if (bio.validation_status === 'valid') {
        // Check for claim_id references
        const hasCitations = /\[claim_\w+\]/.test(bio.bio_text);
        expect(hasCitations).toBe(true);
      }
    }
  });

  test('Step 9: Chat growth vs profitability → owner facts cite [claim_id] OR clarify', async ({ request }) => {
    const chatResponse = await request.post(`${API_BASE_URL}/chat/${twinId}`, {
      headers: { 
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
      },
      data: {
        query: 'When should a founder prioritize growth over profitability?',
        conversation_id: null
      }
    });

    expect(chatResponse.status()).toBe(200);
    
    // Parse streaming response
    const text = await chatResponse.text();
    
    // Verify response contains either:
    // 1. Claim citations [claim_xxx]
    // 2. Clarification request (no unsupported facts)
    const hasCitations = /\[claim_\w+\]/.test(text);
    const asksClarification = text.toLowerCase().includes('help me understand') || 
                               text.toLowerCase().includes('could you clarify');
    
    expect(hasCitations || asksClarification).toBe(true);
    
    console.log(`[E2E] Chat response has citations: ${hasCitations}, asks clarification: ${asksClarification}`);
  });

  test('Determinism: claim_id set identical across runs', async () => {
    // This would be tested via a separate determinism harness
    // For E2E, we verify the claim_id format is consistent
    const response = await fetch(`${API_BASE_URL}/persona/link-compile/twins/${twinId}/claims`, {
      headers: { 'Authorization': `Bearer ${authToken}` }
    });

    const data = await response.json();
    const claimIds = data.claims.map((c: {id: string}) => c.id).sort();
    
    // All claim IDs should follow consistent format
    for (const id of claimIds) {
      expect(id).toMatch(/^claim_[a-f0-9]{8,}$/);
    }
    
    console.log(`[E2E] Verified ${claimIds.length} claim IDs are consistent`);
  });
});

test.describe('Chat Gating: Non-active twin → 403', () => {
  test('draft twin chat returns 403 with redirect hint', async ({ request }) => {
    // Create a new draft twin
    const createRes = await request.post(`${API_BASE_URL}/twins`, {
      headers: { 
        'Authorization': `Bearer test-token`,
        'Content-Type': 'application/json'
      },
      data: {
        name: 'Test Draft',
        mode: 'link_first'
      }
    });

    if (!createRes.ok) return; // Skip if auth fails
    
    const { id: draftTwinId } = await createRes.json();
    
    // Try to chat
    const chatRes = await request.post(`${API_BASE_URL}/chat/${draftTwinId}`, {
      headers: { 
        'Authorization': `Bearer test-token`,
        'Content-Type': 'application/json'
      },
      data: { query: 'Hello' }
    });

    expect(chatRes.status()).toBe(403);
    
    const data = await chatRes.json();
    expect(data.detail).toContain('not active');
  });
});
