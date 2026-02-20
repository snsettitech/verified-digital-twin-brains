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
            { name: 'Profile', href: '/dashboard/profile', icon: 'profile' },
            { name: 'Knowledge', href: '/dashboard/knowledge', icon: 'book' },
            { name: 'Memory Center', href: '/dashboard/memory', icon: 'memory', featureFlag: 'memoryCenter' },
            { name: 'Studio', href: '/dashboard/studio', icon: 'studio' },
            { name: 'Ingestion Jobs', href: '/dashboard/training-jobs', icon: 'history' },
            { name: 'Brain Graph', href: '/dashboard/brain', icon: 'activity' },
        ]
    },
    {
        title: 'Interact',
        items: [
            { name: 'Chat', href: '/dashboard/chat', icon: 'chat', featureFlag: 'dashboardChat' },
            { name: 'Actions', href: '/dashboard/actions', icon: 'actions' },
            { name: 'Share', href: '/dashboard/share', icon: 'share' },
        ]
    },
    {
        title: 'Test & Review',
        items: [
            { name: 'Simulator Hub', href: '/dashboard/simulator', icon: 'chat' },
            { name: 'Simulator Owner', href: '/dashboard/simulator/owner', icon: 'chat' },
            { name: 'Simulator Training', href: '/dashboard/simulator/training', icon: 'training' },
            { name: 'Simulator Public', href: '/dashboard/simulator/public', icon: 'share' },
            { name: 'Simulator Workflow', href: '/dashboard/simulator/workflow', icon: 'history' },
            { name: 'Retrieval Debug', href: '/dashboard/simulator/retrieval-debug', icon: 'activity' },
            { name: 'Escalations', href: '/dashboard/escalations', icon: 'escalations' },
            { name: 'Verified QnA', href: '/dashboard/verified-qna', icon: 'check' },
        ]
    },
    {
        title: 'Insights',
        items: [
            { name: 'Metrics', href: '/dashboard/metrics', icon: 'chart' },
            { name: 'Insights', href: '/dashboard/insights', icon: 'activity' },
        ]
    },
    {
        title: 'Share & Access',
        items: [
            { name: 'Access Groups', href: '/dashboard/access-groups', icon: 'group' },
            { name: 'Widget', href: '/dashboard/widget', icon: 'code' },
            { name: 'API Keys', href: '/dashboard/api-keys', icon: 'key' },
        ]
    },
    {
        title: 'Automation',
        items: [
            { name: 'Actions', href: '/dashboard/actions', icon: 'actions' },
            { name: 'Jobs', href: '/dashboard/jobs', icon: 'history' },
        ]
    },
    {
        title: 'Settings',
        items: [
            { name: 'Settings', href: '/dashboard/settings', icon: 'settings' },
            { name: 'Privacy & Data', href: '/dashboard/privacy', icon: 'privacy', featureFlag: 'privacyControls' },
            { name: 'Publish Controls', href: '/dashboard/publish-controls', icon: 'publish', featureFlag: 'publishControls' },
            { name: 'Users', href: '/dashboard/users', icon: 'users' },
            { name: 'Governance', href: '/dashboard/governance', icon: 'governance' },
        ]
    },
    {
        title: 'System',
        items: [
            { name: 'Admin', href: '/admin', icon: 'shield' },
        ]
    }
];

/**
 * Get the display name for the app.
 * This can be customized per deployment if needed.
 */
export const APP_NAME = 'VT-BRAIN';
export const APP_TAGLINE = 'Digital Twin';
