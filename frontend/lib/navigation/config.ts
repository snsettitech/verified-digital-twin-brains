/**
 * Navigation Configuration
 *
 * SINGLE SOURCE OF TRUTH for sidebar structure.
 *
 * Subscription tiers (future gate):
 *   free    — Home, Profile, Knowledge, Studio, Share
 *   pro     — + Chat, Escalations, Verified Q&A, Widget, API Keys
 *   team    — + Access Groups, Privacy & Data, Publish Controls
 *   admin   — all pages accessible via /admin (not surfaced here)
 *
 * To add a new sidebar item:
 * 1. Add the route in app/dashboard/[route]/page.tsx
 * 2. Add the item here in the appropriate section
 * 3. Add the icon to Sidebar.tsx getIcon() if needed
 *
 * Pages that exist but are intentionally NOT in the nav:
 *   /dashboard/deep-research      — "Rebuild Persona" tool (access via Settings > Rebuild)
 *   /dashboard/brain              — Knowledge graph visualizer (dev/power user)
 *   /dashboard/memory             — Graph memory explorer (feature-gated)
 *   /dashboard/simulator/*        — QA testing tools (dev only)
 *   /dashboard/training-jobs      — Background job monitor (dev/ops)
 *   /dashboard/metrics            — System health (dev/ops)
 *   /dashboard/insights           — Analytics (future paid feature)
 *   /dashboard/access-groups      — Team access control (team tier)
 *   /dashboard/governance         — Compliance/policy (enterprise tier)
 *   /dashboard/users              — User management (admin)
 *   /dashboard/jobs               — Job queue (admin/ops)
 *   /dashboard/actions            — Automation connectors (not yet built)
 *   /dashboard/products           — Products catalog (not yet built)
 */

import type { SidebarConfig } from './types';

export const SIDEBAR_CONFIG: SidebarConfig = [
    {
        title: '',
        items: [
            { name: 'Home',      href: '/dashboard',           icon: 'home'    },
            { name: 'Profile',   href: '/dashboard/profile',   icon: 'profile' },
            { name: 'Knowledge', href: '/dashboard/knowledge', icon: 'book'    },
            { name: 'Chat',      href: '/dashboard/chat',      icon: 'chat', featureFlag: 'dashboardChat' },
        ]
    },
    {
        title: 'Persona',
        items: [
            { name: 'Studio',       href: '/dashboard/studio',       icon: 'studio'     },
            { name: 'Escalations',  href: '/dashboard/escalations',  icon: 'escalations' },
            { name: 'Verified Q&A', href: '/dashboard/verified-qna', icon: 'check'      },
        ]
    },
    {
        title: 'Publish',
        items: [
            { name: 'Share',    href: '/dashboard/share',    icon: 'share' },
            { name: 'Widget',   href: '/dashboard/widget',   icon: 'code'  },
            { name: 'API Keys', href: '/dashboard/api-keys', icon: 'key'   },
        ]
    },
    {
        title: 'Account',
        items: [
            { name: 'Settings',       href: '/dashboard/settings',         icon: 'settings' },
            { name: 'Privacy & Data', href: '/dashboard/privacy',          icon: 'privacy',  featureFlag: 'privacyControls'  },
            { name: 'Publish Controls', href: '/dashboard/publish-controls', icon: 'publish', featureFlag: 'publishControls' },
        ]
    },
];

export const APP_NAME = 'PersonaOn';
export const APP_TAGLINE = 'Your AI Persona';
