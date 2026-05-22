import { expect, test } from "@playwright/test";

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
