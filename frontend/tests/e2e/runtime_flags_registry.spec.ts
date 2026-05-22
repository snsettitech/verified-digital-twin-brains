import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import path from "node:path";

import { SIDEBAR_CONFIG } from "../../lib/navigation/config";
import { RUNTIME_FLAGS } from "../../lib/features/runtimeFlags";

test("runtime flag registry stays aligned with live dashboard gates", async () => {
  const runtimeFlags = Object.keys(RUNTIME_FLAGS).sort();
  const navFlags = SIDEBAR_CONFIG.flatMap((section) =>
    section.items.flatMap((item) => (item.featureFlag ? [item.featureFlag] : [])),
  ).sort();

  expect(runtimeFlags).toEqual([
    "contextPanel",
    "dashboardChat",
    "memoryCenter",
    "privacyControls",
    "publishControls",
  ]);
  expect(navFlags).toEqual([
    "dashboardChat",
    "memoryCenter",
    "privacyControls",
    "publishControls",
  ]);
});

test("live dashboard pages keep their runtime gate wiring", async () => {
  const cases = [
    {
      file: "app/dashboard/chat/page.tsx",
      patterns: [
        /const chatEnabled = isRuntimeFeatureEnabled\('dashboardChat'\);/,
        /const contextPanelEnabled = isRuntimeFeatureEnabled\('contextPanel'\);/,
        /\{contextPanelEnabled \? <ContextPanel snapshot=\{snapshot\} \/>\s*: null\}/,
      ],
    },
    {
      file: "app/dashboard/memory/page.tsx",
      patterns: [
        /const enabled = isRuntimeFeatureEnabled\('memoryCenter'\);/,
        /<FeatureGate\s+enabled=\{enabled\}/,
      ],
    },
    {
      file: "app/dashboard/privacy/page.tsx",
      patterns: [
        /const enabled = isRuntimeFeatureEnabled\('privacyControls'\);/,
        /<FeatureGate\s+enabled=\{enabled\}/,
      ],
    },
    {
      file: "app/dashboard/publish-controls/page.tsx",
      patterns: [
        /const enabled = isRuntimeFeatureEnabled\('publishControls'\);/,
        /<FeatureGate\s+enabled=\{enabled\}/,
      ],
    },
  ];

  for (const { file, patterns } of cases) {
    const contents = await readFile(path.join(process.cwd(), file), "utf8");

    for (const pattern of patterns) {
      expect(contents).toMatch(pattern);
    }
  }
});
