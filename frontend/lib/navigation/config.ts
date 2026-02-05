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
            { name: 'Knowledge', href: '/dashboard/knowledge', icon: 'book' },
        ]
    },
    {
        title: 'Train',
        items: [
            { name: 'Simulator', href: '/dashboard/simulator', icon: 'chat' },
        ]
    },
    {
        title: 'Share',
        items: [
            { name: 'Widget', href: '/dashboard/widget', icon: 'code' },
            { name: 'API Keys', href: '/dashboard/api-keys', icon: 'key' },
        ]
    },
    {
        title: 'Settings',
        items: [
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
