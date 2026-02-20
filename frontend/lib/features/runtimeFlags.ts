export type RuntimeFeatureFlag =
  | "dashboardChat"
  | "memoryCenter"
  | "privacyControls"
  | "publishControls"
  | "contextPanel"
  | "sourceLabeling"
  | "officeHoursMode";

const toBool = (value: string | undefined, fallback: boolean): boolean => {
  if (value === undefined) return fallback;
  const normalized = value.trim().toLowerCase();
  if (["1", "true", "yes", "on"].includes(normalized)) return true;
  if (["0", "false", "no", "off"].includes(normalized)) return false;
  return fallback;
};

export const RUNTIME_FLAGS: Record<RuntimeFeatureFlag, boolean> = {
  dashboardChat: toBool(process.env.NEXT_PUBLIC_FF_DASHBOARD_CHAT, true),
  memoryCenter: toBool(process.env.NEXT_PUBLIC_FF_MEMORY_CENTER, true),
  privacyControls: toBool(process.env.NEXT_PUBLIC_FF_PRIVACY_CONTROLS, true),
  publishControls: toBool(process.env.NEXT_PUBLIC_FF_PUBLISH_CONTROLS, true),
  contextPanel: toBool(process.env.NEXT_PUBLIC_FF_CONTEXT_PANEL, true),
  sourceLabeling: toBool(process.env.NEXT_PUBLIC_FF_SOURCE_LABELING, true),
  officeHoursMode: toBool(process.env.NEXT_PUBLIC_FF_OFFICE_HOURS_MODE, true),
};

export const isRuntimeFeatureEnabled = (flag: RuntimeFeatureFlag): boolean =>
  Boolean(RUNTIME_FLAGS[flag]);

