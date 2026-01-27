/**
 * Navigation Configuration
 * 
 * SINGLE SOURCE OF TRUTH for sidebar structure.
 * 
 * This is static configuration - it does NOT depend on:
 * - Twin selection
 * - API calls
 * - User authentication state
 * 
 * To add a new sidebar item:
 * 1. Add the route in app/dashboard/[route]/page.tsx
 * 2. Add the item here in the appropriate section
 * 3. Add the icon to Sidebar.tsx getIcon() if needed
 */

import type { SidebarConfig } from './types';

export const SIDEBAR_CONFIG: SidebarConfig = [
    {
        title: 'Build',
        items: [
            { name: 'Dashboard', href: '/dashboard', icon: 'home' },
            { name: 'Interview Mode', href: '/dashboard/interview', icon: 'activity' },
            { name: 'Knowledge', href: '/dashboard/knowledge', icon: 'book' },
            { name: 'Right Brain', href: '/dashboard/right-brain', icon: 'chart' },
        ]
    },
    {
        title: 'Train',
        items: [
            { name: 'Simulator', href: '/dashboard/simulator', icon: 'chat' },
            { name: 'Verified Q&A', href: '/dashboard/verified-qna', icon: 'check' },
            { name: 'Escalations', href: '/dashboard/escalations', icon: 'alert' },
            { name: 'Actions Hub', href: '/dashboard/actions', icon: 'bolt' },
        ]
    },
    {
        title: 'Share',
        items: [
            { name: 'Access Groups', href: '/dashboard/access-groups', icon: 'users' },
            { name: 'Widget', href: '/dashboard/widget', icon: 'code' },
            { name: 'API Keys', href: '/dashboard/api-keys', icon: 'key' },
        ]
    },
    {
        title: 'Settings',
        items: [
            { name: 'Governance', href: '/dashboard/governance', icon: 'shield' },
            { name: 'Settings', href: '/dashboard/settings', icon: 'settings' },
        ]
    }
];

/**
 * Get the display name for the app.
 * This can be customized per deployment if needed.
 */
export const APP_NAME = 'VT-BRAIN';
export const APP_TAGLINE = 'Digital Twin';
