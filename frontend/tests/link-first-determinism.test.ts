/**
 * Determinism Harness for Link-First Persona
 * 
 * Runs extraction→inference→bio generation 5x with fixed seed/mock.
 * Verifies:
 * 1. Identical claim_id set across runs
 * 2. Bio sentence→claim mapping is stable
 * 3. No claim drift between runs
 */

import { test, expect } from '@playwright/test';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// Fixed test content for reproducibility
const TEST_CONTENT = {
  linkedin_export: `
    Sainath Setti
    Investor & Founder at Acme Ventures
    
    My investment thesis focuses on B2B enterprise software because 
    the sales cycles are predictable and customers stick around. 
    I prefer B2B over B2C for early-stage ventures.
    
    When evaluating teams, I look for resilience more than credentials. 
    I back exceptional founders, then figure out the market.
    
    Transparency matters more than polish. Tell me the real numbers, 
    not the deck version.
  `,
  
  github_readme: `
    # My Projects
    
    I'm a full-stack developer passionate about developer tools.
    I believe in open source and community-driven development.
  `
};

test.describe('Link-First Determinism Harness (5 runs)', () => {
  const RUN_COUNT = 5;
  const results: Array<{
    run: number;
    claimIds: string[];
    bioShort: string;
    bioLinkedIn: string;
  }> = [];

  for (let run = 1; run <= RUN_COUNT; run++) {
    test(`Run ${run}: Extract claims and generate bios`, async ({ request }) => {
      // Create fresh twin for this run
      const twinRes = await request.post(`${API_BASE_URL}/twins`, {
        headers: { 'Content-Type': 'application/json' },
        data: {
          name: `Determinism Test ${run}`,
          mode: 'link_first',
          specialization: 'investor'
        }
      });

      expect(twinRes.status()).toBe(200);
      const { id: twinId } = await twinRes.json();

      // Submit paste content (mode-b) with deterministic content
      const pasteRes = await request.post(`${API_BASE_URL}/persona/link-compile/jobs/mode-b`, {
        headers: { 'Content-Type': 'application/json' },
        data: {
          twin_id: twinId,
          content: TEST_CONTENT.linkedin_export,
          title: 'LinkedIn Export (Deterministic Test)'
        }
      });

      expect(pasteRes.status()).toBe(200);

      // Poll for completion
      let attempts = 0;
      let claims: Array<{id: string; claim_text: string}> = [];
      
      while (attempts < 20) {
        await new Promise(r => setTimeout(r, 1000));
        
        const jobRes = await request.get(`${API_BASE_URL}/persona/link-compile/twins/${twinId}/job`);
        if (jobRes.ok) {
          const job = await jobRes.json();
          
          if (job.status === 'completed' || job.status === 'claims_ready') {
            // Fetch claims
            const claimsRes = await request.get(`${API_BASE_URL}/persona/link-compile/twins/${twinId}/claims`);
            if (claimsRes.ok) {
              const data = await claimsRes.json();
              claims = data.claims || [];
            }
            break;
          }
        }
        attempts++;
      }

      expect(claims.length).toBeGreaterThan(0);

      // Fetch bios
      const biosRes = await request.get(`${API_BASE_URL}/persona/link-compile/twins/${twinId}/bios`);
      let bios: Array<{bio_type: string; bio_text: string}> = [];
      
      if (biosRes.ok) {
        const data = await biosRes.json();
        bios = data.variants || [];
      }

      // Store results
      results.push({
        run,
        claimIds: claims.map(c => c.id).sort(),
        bioShort: bios.find(b => b.bio_type === 'short')?.bio_text || '',
        bioLinkedIn: bios.find(b => b.bio_type === 'linkedin_about')?.bio_text || ''
      });

      console.log(`[Determinism] Run ${run}: ${claims.length} claims extracted`);
    });
  }

  test('Verify claim_id set identical across all runs', () => {
    expect(results.length).toBe(RUN_COUNT);
    
    // Use Run 1 as baseline
    const baseline = results[0];
    
    for (let i = 1; i < results.length; i++) {
      const current = results[i];
      
      // Check claim count
      expect(current.claimIds.length).toBe(baseline.claimIds.length);
      
      // Check claim IDs match (order-independent)
      const baselineSet = new Set(baseline.claimIds);
      const currentSet = new Set(current.claimIds);
      
      expect(currentSet).toEqual(baselineSet);
      
      console.log(`[Determinism] Run ${i + 1} claim set matches baseline`);
    }
  });

  test('Verify bio sentence→claim mapping is stable', () => {
    const baseline = results[0];
    
    for (let i = 1; i < results.length; i++) {
      const current = results[i];
      
      // Extract claim citations from bios
      const baselineShortCitations = extractCitations(baseline.bioShort);
      const currentShortCitations = extractCitations(current.bioShort);
      
      expect(currentShortCitations.sort()).toEqual(baselineShortCitations.sort());
      
      console.log(`[Determinism] Run ${i + 1} bio citations match baseline`);
    }
  });

  test('Verify no claim drift between runs', () => {
    // Claim drift = claims that appear in some runs but not others
    const allClaimIds = new Set<string>();
    const claimFrequency = new Map<string, number>();
    
    for (const result of results) {
      for (const claimId of result.claimIds) {
        allClaimIds.add(claimId);
        claimFrequency.set(claimId, (claimFrequency.get(claimId) || 0) + 1);
      }
    }
    
    // All claims should appear in all runs (frequency = RUN_COUNT)
    const driftedClaims: string[] = [];
    
    for (const [claimId, frequency] of claimFrequency) {
      if (frequency !== RUN_COUNT) {
        driftedClaims.push(`${claimId} (appeared ${frequency}/${RUN_COUNT} runs)`);
      }
    }
    
    expect(driftedClaims).toEqual([]);
    
    console.log(`[Determinism] No claim drift detected across ${RUN_COUNT} runs`);
  });

  test('Report determinism metrics', () => {
    const baseline = results[0];
    
    console.log('\n=== DETERMINISM HARNESS REPORT ===');
    console.log(`Runs: ${RUN_COUNT}`);
    console.log(`Claims per run: ${baseline.claimIds.length}`);
    console.log(`Claim ID format: ${baseline.claimIds[0]?.substring(0, 20)}...`);
    console.log(`Bio variants: ${results[0].bioShort ? 'short, ' : ''}${results[0].bioLinkedIn ? 'linkedin' : ''}`);
    console.log('=== END REPORT ===\n');
    
    expect(baseline.claimIds.length).toBeGreaterThan(0);
  });
});

// Helper function to extract [claim_xxx] citations from bio text
function extractCitations(bioText: string): string[] {
  const matches = bioText.match(/\[claim_\w+\]/g) || [];
  return matches.map(m => m.slice(1, -1)); // Remove brackets
}

/**
 * Manual Determinism Test Instructions:
 * 
 * To run this harness locally:
 * 
 * 1. Start backend with deterministic LLM mode:
 *    DETERMINISTIC_LLM=true python -m uvicorn main:app
 * 
 * 2. Run tests:
 *    npx playwright test link-first-determinism.test.ts
 * 
 * 3. Check report output for:
 *    - Claim count consistency
 *    - Claim ID stability
 *    - Citation mapping consistency
 */
