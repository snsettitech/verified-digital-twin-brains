/* eslint-disable @typescript-eslint/no-require-imports */
// Phase 5 E2E canary run (local frontend -> canary backend) using real UI flow.
// - Starts Next dev server pointed at the Render canary backend
// - Drives login + realtime ingestion UI + simulator roleplay via Playwright
// - Prints a JSON summary with exact assistant outputs
//
// Notes:
// - Reads TEST_ACCOUNT_EMAIL/TEST_ACCOUNT_PASSWORD from repo root .env
// - Does NOT print credentials
// - Designed for ad-hoc verification (not a committed CI step yet)

const fs = require('fs');
const path = require('path');
const { spawn, spawnSync } = require('child_process');
const { chromium } = require('@playwright/test');

function parseDotenv(text) {
  const out = {};
  const lines = text.split(/\r?\n/);
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const idx = line.indexOf('=');
    if (idx <= 0) continue;
    const key = line.slice(0, idx).trim();
    let val = line.slice(idx + 1).trim();
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    out[key] = val;
  }
  return out;
}

function nowIsoCompact() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

function killTree(pid) {
  if (!pid) return;
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'], { stdio: 'ignore' });
    return;
  }
  try {
    process.kill(-pid, 'SIGTERM');
  } catch {
    try {
      process.kill(pid, 'SIGTERM');
    } catch {
      // ignore
    }
  }
}

async function waitForServerReady(child, timeoutMs) {
  const start = Date.now();
  let buffer = '';
  return await new Promise((resolve, reject) => {
    const onData = (chunk) => {
      buffer += chunk.toString('utf8');
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() || '';
      for (const line of lines) {
        const l = line.toLowerCase();
        if (l.includes('ready') || (l.includes('local:') && l.includes('http'))) {
          cleanup();
          resolve(true);
          return;
        }
      }
      if (Date.now() - start > timeoutMs) {
        cleanup();
        reject(new Error('Timed out waiting for Next dev server to become ready'));
      }
    };

    const onExit = (code) => {
      cleanup();
      reject(new Error(`Next dev server exited early (code=${code})`));
    };

    const timer = setInterval(() => {
      if (Date.now() - start > timeoutMs) {
        cleanup();
        reject(new Error('Timed out waiting for Next dev server to become ready'));
      }
    }, 1000);

    function cleanup() {
      clearInterval(timer);
      child.stdout?.off('data', onData);
      child.stderr?.off('data', onData);
      child.off('exit', onExit);
    }

    child.stdout?.on('data', onData);
    child.stderr?.on('data', onData);
    child.on('exit', onExit);
  });
}

async function main() {
  const repoRoot = path.resolve(__dirname, '..', '..');
  const frontendDir = path.resolve(repoRoot, 'frontend');
  const rootEnvPath = path.resolve(repoRoot, '.env');
  const envLocalPath = path.resolve(frontendDir, '.env.local');
  const canaryBackend = process.env.CANARY_BACKEND_URL || 'https://verified-digital-twin-backend-canary3.onrender.com';

  const envText = fs.readFileSync(rootEnvPath, 'utf8');
  const env = parseDotenv(envText);

  const email = env.TEST_ACCOUNT_EMAIL;
  const password = env.TEST_ACCOUNT_PASSWORD;
  if (!email || !password) {
    throw new Error('Missing TEST_ACCOUNT_EMAIL/TEST_ACCOUNT_PASSWORD in repo root .env');
  }

  const runId = `phase5-canary-e2e-${nowIsoCompact()}`;
  const marker = `PHASE5_MARKER_${Math.floor(Date.now() / 1000)}`;

  const personaText = [
    'Persona seed (Phase 5 realtime):',
    'Name: Sainath.',
    'Role: building VT-BRAIN, a Delphi-style creator digital twin platform.',
    'Style: concise, direct, pragmatic.',
    'Preference: likes black coffee.',
    'Hobby: Brazilian Jiu-Jitsu.',
    'If asked about current focus: shipping a fully functional platform with top notch performance.',
  ].join('\n');

  let devServer = null;
  let browser = null;
  let context = null;
  let page = null;
  let originalEnvLocal = null;

  const requestHosts = new Set();
  const requestFailures = [];
  const relevantResponses = [];

  const result = {
    run_id: runId,
    canary_backend: canaryBackend,
    marker,
    error: null,
    frontend_runtime_env: null,
    frontend_env_local: null,
    realtime: {
      health_badge: null,
      health_detail: null,
      session_id: null,
      source_id: null,
      commit_status_text: null,
    },
    response_quality: {
      owner_small_talk: null,
      owner_general_qa: null,
      owner_persona_coffee: null,
      owner_marker_echo: null,
      roleplay_identity: null,
    },
    observed_request_hosts: [],
    request_failures: [],
    relevant_responses: [],
  };

  try {
    // Next loads .env.local and may override inherited env vars.
    // For a reliable canary run, patch frontend/.env.local for the duration of this script.
    originalEnvLocal = fs.readFileSync(envLocalPath, 'utf8');
    const patchedEnvLocal = (() => {
      const lines = originalEnvLocal.split(/\r?\n/);
      const map = {};
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue;
        const idx = trimmed.indexOf('=');
        map[trimmed.slice(0, idx)] = trimmed.slice(idx + 1);
      }
      map.NEXT_PUBLIC_BACKEND_URL = canaryBackend;
      map.NEXT_PUBLIC_API_URL = canaryBackend;
      map.NEXT_PUBLIC_FRONTEND_URL = 'http://127.0.0.1:3000';

      // Preserve SUPABASE defaults if present; otherwise leave Next's built-in fallbacks to handle it.
      const stableKeys = [
        'NEXT_PUBLIC_SUPABASE_URL',
        'NEXT_PUBLIC_SUPABASE_ANON_KEY',
        'NEXT_PUBLIC_BACKEND_URL',
        'NEXT_PUBLIC_API_URL',
        'NEXT_PUBLIC_FRONTEND_URL',
      ];
      return stableKeys
        .filter((k) => typeof map[k] === 'string' && String(map[k]).length > 0)
        .map((k) => `${k}=${map[k]}`)
        .join('\n') + '\n';
    })();
    fs.writeFileSync(envLocalPath, patchedEnvLocal, 'utf8');
    try {
      const verifyEnvLocal = parseDotenv(fs.readFileSync(envLocalPath, 'utf8'));
      result.frontend_env_local = {
        NEXT_PUBLIC_BACKEND_URL: verifyEnvLocal.NEXT_PUBLIC_BACKEND_URL || null,
        NEXT_PUBLIC_API_URL: verifyEnvLocal.NEXT_PUBLIC_API_URL || null,
        NEXT_PUBLIC_FRONTEND_URL: verifyEnvLocal.NEXT_PUBLIC_FRONTEND_URL || null,
      };
    } catch {
      result.frontend_env_local = { error: 'failed_to_read_frontend_env_local' };
    }

    // Force Next to rebuild bundles with the patched env (avoids stale .next cache across runs).
    try {
      fs.rmSync(path.resolve(frontendDir, '.next'), { recursive: true, force: true });
    } catch {
      // ignore
    }

    // Start Next dev server (using npm.cmd to bypass PowerShell script restrictions).
    const devEnv = {
      ...process.env,
      NEXT_PUBLIC_BACKEND_URL: canaryBackend,
      NEXT_PUBLIC_API_URL: canaryBackend,
      NEXT_PUBLIC_FRONTEND_URL: 'http://127.0.0.1:3000',
    };

    // Use cmd.exe so we avoid PowerShell ExecutionPolicy issues (npm.ps1).
    devServer = spawn(
      'cmd.exe',
      ['/c', 'npm.cmd', 'run', 'dev', '--', '--port', '3000', '--hostname', '127.0.0.1'],
      {
        cwd: frontendDir,
        env: devEnv,
        stdio: ['ignore', 'pipe', 'pipe'],
        windowsHide: true,
      }
    );

    await waitForServerReady(devServer, 120_000);

    // Drive UI via Playwright
    browser = await chromium.launch({
      headless: true,
      args: ['--disable-dev-shm-usage'],
    });
    context = await browser.newContext();
    page = await context.newPage();

    page.on('request', (req) => {
      try {
        requestHosts.add(new URL(req.url()).host);
      } catch {
        // ignore
      }
    });
    page.on('requestfailed', (req) => {
      const url = req.url();
      if (!url.includes('/health') && !url.includes('/ingest/realtime')) return;
      requestFailures.push({
        url,
        error_text: req.failure()?.errorText || null,
      });
    });
    page.on('response', (res) => {
      const url = res.url();
      if (!url.includes('/health') && !url.includes('/ingest/realtime')) return;
      relevantResponses.push({
        url,
        status: res.status(),
      });
    });

    const baseUrl = 'http://127.0.0.1:3000';
    await page.goto(`${baseUrl}/auth/login?redirect=/dashboard/knowledge`, {
      waitUntil: 'domcontentloaded',
      timeout: 30_000,
    });

    await page.getByPlaceholder('you@example.com').fill(email);
    await page.locator('input[type=\"password\"]').fill(password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.waitForURL('**/dashboard/knowledge', { timeout: 30_000 });

    // Capture what the client thinks the backend URL is (helps debug env propagation).
    result.frontend_runtime_env = await page
      .evaluate(() => {
        try {
          // In Next.js, NEXT_PUBLIC_* variables are inlined at build time.
          const env = (typeof process !== 'undefined' && process.env) ? process.env : {};
          return {
            NEXT_PUBLIC_BACKEND_URL: env.NEXT_PUBLIC_BACKEND_URL || null,
            NEXT_PUBLIC_API_URL: env.NEXT_PUBLIC_API_URL || null,
            NEXT_PUBLIC_FRONTEND_URL: env.NEXT_PUBLIC_FRONTEND_URL || null,
            location_origin: window.location.origin,
          };
        } catch {
          return { error: 'failed_to_read_env' };
        }
      })
      .catch(() => null);

    // Realtime ingestion UI
    await page.getByRole('heading', { name: 'Realtime Stream (Phase 5)' }).waitFor({ timeout: 30_000 });

    // The "start session" controls only render once the realtime health probe reports schema_available=true.
    // On cold starts or auth races, this can take a bit. We retry health refresh until the title input appears.
    const titleInput = page.getByPlaceholder('Optional title (e.g., Live call transcript)');
    const refreshBtn = page.getByRole('button', { name: 'Refresh' }).first();

    for (let i = 0; i < 40; i++) {
      if (await titleInput.isVisible().catch(() => false)) break;
      await refreshBtn.click().catch(() => {});
      await page.waitForTimeout(1500);
    }

    if (!(await titleInput.isVisible().catch(() => false))) {
      const badge = await page
        .locator('span')
        .filter({ hasText: /^(CHECKING|READY|DEGRADED|DISABLED|ERROR)$/ })
        .first()
        .innerText()
        .catch(() => null);
      const detailText = await page
        .locator('div')
        .filter({ hasText: 'Realtime ingestion is not available on this backend.' })
        .first()
        .innerText()
        .catch(() => null);
      result.realtime.health_badge = badge || null;
      result.realtime.health_detail = detailText || null;
      throw new Error(`Realtime ingestion UI never became ready (health badge=${badge || 'unknown'})`);
    }

    await titleInput.fill(runId);
    await page.getByRole('button', { name: 'Start' }).click();
    await page.getByText('Append Chunk', { exact: true }).waitFor({ timeout: 120_000 });

    // Extract UUID candidates before commit
    const beforeUuids = await page.evaluate(() => {
      const uuidRe = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
      const found = new Set();
      for (const el of Array.from(document.querySelectorAll('*'))) {
        const t = (el.textContent || '').trim();
        const matches = t.match(uuidRe);
        if (!matches) continue;
        for (const m of matches) found.add(m.toLowerCase());
      }
      return Array.from(found);
    });

    const chunkArea = page.getByPlaceholder(
      'Paste a transcript chunk (append-only). For testing, you can paste PHASE5_MARKER_12345 etc.'
    );

    async function selectEventType(value) {
      const selectHandle = await page.evaluateHandle(() => {
        const selects = Array.from(document.querySelectorAll('select'));
        return selects.find((sel) => Array.from(sel.options || []).some((o) => o.value === 'marker')) || null;
      });
      const el = selectHandle.asElement();
      if (!el) throw new Error('Could not locate realtime event_type <select>');
      await el.selectOption(value);
    }

    await selectEventType('text');
    await chunkArea.fill(personaText);
    await page.getByRole('button', { name: 'Append' }).click();

    await selectEventType('marker');
    await chunkArea.fill(marker);
    await page.getByRole('button', { name: 'Append' }).click();

    const commitAsyncToggle = page.getByLabel('Commit async');
    if (await commitAsyncToggle.isChecked().catch(() => false)) {
      await commitAsyncToggle.uncheck();
    }
    await page.getByRole('button', { name: 'Commit' }).click();
    await page.getByText(/Committed/i).first().waitFor({ timeout: 90_000 });

    // Extract UUID candidates after commit
    const afterUuids = await page.evaluate(() => {
      const uuidRe = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
      const found = new Set();
      for (const el of Array.from(document.querySelectorAll('*'))) {
        const t = (el.textContent || '').trim();
        const matches = t.match(uuidRe);
        if (!matches) continue;
        for (const m of matches) found.add(m.toLowerCase());
      }
      return Array.from(found);
    });

    const newUuids = afterUuids.filter((u) => !beforeUuids.includes(u));
    result.realtime.session_id = afterUuids[0] || null;
    result.realtime.source_id = newUuids.find((u) => u !== result.realtime.session_id) || null;

    // Commit status text (best-effort)
    result.realtime.commit_status_text = await page
      .getByText(/Committed/i)
      .first()
      .innerText()
      .catch(() => null);

    // Simulator response quality
    await page.goto(`${baseUrl}/dashboard/simulator#training-simulator`, {
      waitUntil: 'domcontentloaded',
      timeout: 30_000,
    });

    const chatInput = page.getByPlaceholder(
      'Ask anything about your knowledge base... (Enter to send, Shift+Enter for new line)'
    );
    await chatInput.waitFor({ timeout: 30_000 });
    // Let initial simulator API calls settle (conversation fetch, twin metadata, etc).
    await page.waitForTimeout(2000);

    // Ensure owner mode first (stop training if already active)
    const stopBtn = page.getByRole('button', { name: 'Stop Training' });
    if (await stopBtn.isVisible().catch(() => false)) {
      await stopBtn.click();
      await page.getByRole('button', { name: 'Start Training' }).waitFor({ timeout: 30_000 });
    }

    function parseChatStreamBody(bodyText) {
      const lines = String(bodyText || '')
        .split(/\r?\n/)
        .map((l) => l.trim())
        .filter(Boolean)
        .map((l) => (l.startsWith('data:') ? l.slice('data:'.length).trim() : l));

      let content = '';
      let metadata = null;
      let clarify = null;

      for (const line of lines) {
        let obj = null;
        try {
          obj = JSON.parse(line);
        } catch {
          continue;
        }
        if (!obj || typeof obj !== 'object') continue;
        if (obj.type === 'metadata' && !obj.ping) {
          metadata = obj;
          continue;
        }
        if (obj.type === 'clarify') {
          clarify = obj;
          // In the UI, clarifications are rendered as the assistant message content.
          if (typeof obj.question === 'string' && obj.question.trim()) {
            content = obj.question.trim();
          }
          continue;
        }
        if (obj.type === 'content' || obj.type === 'answer_token') {
          const tok = typeof obj.content === 'string' ? obj.content : (typeof obj.token === 'string' ? obj.token : '');
          if (tok) content += tok;
          continue;
        }
      }

      return { content: String(content || '').trim(), metadata, clarify };
    }

    async function waitForChatResponseForQuery(question) {
      const chatResponse = await page.waitForResponse(
        (res) => {
          try {
            if (!res.url().includes('/chat/')) return false;
            const req = res.request();
            if (req.method() !== 'POST') return false;
            const postData = req.postData() || '';
            if (!postData) return false;
            const parsed = JSON.parse(postData);
            return parsed && parsed.query === question;
          } catch {
            return false;
          }
        },
        { timeout: 90_000 }
      );

      // Ensure the stream fully completes before reading the body.
      await chatResponse.finished().catch(() => {});
      const bodyText = await chatResponse.text().catch(() => '');
      return parseChatStreamBody(bodyText);
    }

    async function sendChat(question, key) {
      const respPromise = waitForChatResponseForQuery(question);

      await chatInput.click();
      await chatInput.fill(question);
      await chatInput.press('Enter');

      const parsed = await respPromise;
      if (key && parsed?.metadata) {
        result.response_quality_meta = result.response_quality_meta || {};
        result.response_quality_meta[key] = {
          dialogue_mode: parsed.metadata.dialogue_mode || null,
          intent_label: parsed.metadata.intent_label || null,
          citations_count: Array.isArray(parsed.metadata.citations) ? parsed.metadata.citations.length : null,
          citations: Array.isArray(parsed.metadata.citations) ? parsed.metadata.citations.slice(0, 5) : null,
          conversation_id: parsed.metadata.conversation_id || null,
          persona_spec_version: parsed.metadata.persona_spec_version || null,
          persona_prompt_variant: parsed.metadata.persona_prompt_variant || null,
          forced_new_conversation: parsed.metadata.forced_new_conversation ?? null,
        };
      }
      return parsed?.content || '';
    }

    result.response_quality.owner_small_talk = await sendChat('Hey! How are you today?', 'owner_small_talk');
    result.response_quality.owner_general_qa = await sendChat('What is the capital of France?', 'owner_general_qa');
    result.response_quality.owner_persona_coffee = await sendChat(
      'Based on the latest realtime ingestion, what is my coffee preference? Answer in one sentence.'
    , 'owner_persona_coffee');
    result.response_quality.owner_marker_echo = await sendChat(
      `Repeat this marker exactly (no extra words): ${marker}`
    , 'owner_marker_echo');

    // Switch to training (roleplay) mode
    const startTraining = page.getByRole('button', { name: 'Start Training' });
    const stopTraining = page.getByRole('button', { name: 'Stop Training' });
    if (await stopTraining.isVisible().catch(() => false)) {
      // Already in training mode.
    } else {
      await startTraining.click();
      await stopTraining.waitFor({ timeout: 30_000 });
    }

    result.response_quality.roleplay_identity = await sendChat(
      'Roleplay mode: In one sentence, who are you and what are you building right now?'
    , 'roleplay_identity');

    result.observed_request_hosts = Array.from(requestHosts).filter((h) => {
      return h.includes('onrender.com') || h.includes('supabase.co') || h.includes('vercel.app') || h.includes('localhost');
    });
    result.request_failures = requestFailures.slice(0, 20);
    result.relevant_responses = relevantResponses.slice(0, 50);
  } catch (e) {
    result.error = e?.stack || String(e);
    // Best-effort: include any hosts we observed before failing.
    result.observed_request_hosts = Array.from(requestHosts).filter((h) => {
      return h.includes('onrender.com') || h.includes('supabase.co') || h.includes('vercel.app') || h.includes('localhost');
    });
    result.request_failures = requestFailures.slice(0, 20);
    result.relevant_responses = relevantResponses.slice(0, 50);
  } finally {
    try {
      await page?.close().catch(() => {});
      await context?.close().catch(() => {});
      await browser?.close().catch(() => {});
    } catch {
      // ignore
    }
    try {
      if (devServer) killTree(devServer.pid);
    } catch {
      // ignore
    }
    try {
      if (originalEnvLocal !== null) fs.writeFileSync(envLocalPath, originalEnvLocal, 'utf8');
    } catch {
      // ignore
    }
  }

  console.log(JSON.stringify(result, null, 2));
  if (result.error) process.exit(1);
}

main().catch((err) => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
