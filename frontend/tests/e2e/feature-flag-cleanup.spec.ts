import { test, expect } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

const frontendRoot = path.resolve(__dirname, '../..');

function readFrontendFile(relativePath: string): string {
  return readFileSync(path.join(frontendRoot, relativePath), 'utf8');
}

test.describe('frontend stale feature-flag cleanup guard', () => {
  test('removes obsolete frontend runtime flag plumbing from active code paths', () => {
    expect(existsSync(path.join(frontendRoot, 'lib/features/runtimeFlags.ts'))).toBe(false);
    expect(existsSync(path.join(frontendRoot, 'lib/features/FeatureFlags.tsx'))).toBe(false);
    expect(existsSync(path.join(frontendRoot, 'components/ui/FeatureGate.tsx'))).toBe(false);

    const envExample = readFrontendFile('.env.example');
    expect(envExample).not.toContain('NEXT_PUBLIC_FF_DASHBOARD_CHAT');
    expect(envExample).not.toContain('NEXT_PUBLIC_FF_MEMORY_CENTER');
    expect(envExample).not.toContain('NEXT_PUBLIC_FF_PRIVACY_CONTROLS');
    expect(envExample).not.toContain('NEXT_PUBLIC_FF_PUBLISH_CONTROLS');
    expect(envExample).not.toContain('NEXT_PUBLIC_FF_CONTEXT_PANEL');
    expect(envExample).not.toContain('NEXT_PUBLIC_FF_SOURCE_LABELING');
    expect(envExample).not.toContain('NEXT_PUBLIC_FF_OFFICE_HOURS_MODE');

    const layout = readFrontendFile('app/layout.tsx');
    expect(layout).not.toContain('FeatureFlagProvider');

    const sidebar = readFrontendFile('components/Sidebar.tsx');
    expect(sidebar).not.toContain('isRuntimeFeatureEnabled');

    const navigationConfig = readFrontendFile('lib/navigation/config.ts');
    expect(navigationConfig).not.toContain('featureFlag:');

    const navigationTypes = readFrontendFile('lib/navigation/types.ts');
    expect(navigationTypes).not.toContain('featureFlag?:');

    const chatPage = readFrontendFile('app/dashboard/chat/page.tsx');
    expect(chatPage).not.toContain('FeatureGate');
    expect(chatPage).not.toContain('isRuntimeFeatureEnabled');

    const memoryPage = readFrontendFile('app/dashboard/memory/page.tsx');
    expect(memoryPage).not.toContain('FeatureGate');
    expect(memoryPage).not.toContain('isRuntimeFeatureEnabled');

    const privacyPage = readFrontendFile('app/dashboard/privacy/page.tsx');
    expect(privacyPage).not.toContain('FeatureGate');
    expect(privacyPage).not.toContain('isRuntimeFeatureEnabled');

    const publishControlsPage = readFrontendFile('app/dashboard/publish-controls/page.tsx');
    expect(publishControlsPage).not.toContain('FeatureGate');
    expect(publishControlsPage).not.toContain('isRuntimeFeatureEnabled');
  });
});
