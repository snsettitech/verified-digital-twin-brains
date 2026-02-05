/**
 * Navigation Types
 * 
 * Single source of truth for sidebar structure types.
 */

export interface NavItem {
    name: string;
    href: string;
    icon: string;
    badge?: string;
    /** Optional: require a capability to show this item */
    requiresCapability?: string;
}

export interface NavSection {
    title: string;
    items: NavItem[];
}

export type SidebarConfig = NavSection[];
