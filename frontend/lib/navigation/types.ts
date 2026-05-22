/**
 * Navigation Types
 * 
 * Single source of truth for sidebar structure types.
 */

import type { RuntimeFeatureFlag } from "@/lib/features/runtimeFlags";

export interface NavItem {
    name: string;
    href: string;
    icon: string;
    badge?: string;
    /** Optional: require a capability to show this item */
    requiresCapability?: string;
    /** Optional runtime feature flag gate */
    featureFlag?: RuntimeFeatureFlag;
}

export interface NavSection {
    title: string;
    items: NavItem[];
}

export type SidebarConfig = NavSection[];
