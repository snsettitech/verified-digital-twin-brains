/**
 * Navigation Configuration
 *
 * SINGLE SOURCE OF TRUTH for sidebar structure.
 *
 * Subscription tiers (future Stripe gate):
 *   free    — Home, Profile, Knowledge, Studio, Share
 *   pro     — + Chat, Interview, Preview, Escalations, Verified Q&A,
 *               Widget, API Keys, Memory, Analytics, Ingestion Jobs
 *   team    — + Privacy & Data, Publish Controls (future)
 *
 * Pages accessible by URL but intentionally not in the nav:
 *   /dashboard/deep-research   — "Rebuild Persona" tool; surface via Profile > Settings
 *   /dashboard/products        — Product catalog; backend ready, UI not complete yet
 *   /dashboard/actions         — Automation connectors; not yet built
 *
 * To add a new sidebar item:
 * 1. Add the route in app/dashboard/[route]/page.tsx
 * 2. Add the item here in the appropriate section
 * 3. Add the icon to Sidebar.tsx getIcon() if needed
 */

import type { SidebarConfig } from './types';

export const SIDEBAR_CONFIG: SidebarConfig = [
    {
        title: '',
        items: [
            { name: 'Home',      href: '/dashboard',           icon: 'home'    },
            { name: 'Profile',   href: '/dashboard/profile',   icon: 'profile' },
            { name: 'Knowledge', href: '/dashboard/knowledge', icon: 'book'    },
            { name: 'Chat',      href: '/dashboard/chat',      icon: 'chat'    },
        ]
    },
    {
        title: 'Persona',
        items: [
            { name: 'Studio',          href: '/dashboard/studio',          icon: 'studio'      },
            { name: 'Interview',       href: '/dashboard/simulator/training', icon: 'training'  },
            { name: 'Memory',          href: '/dashboard/memory',          icon: 'memory'      },
            { name: 'Escalations',     href: '/dashboard/escalations',     icon: 'escalations' },
            { name: 'Verified Q&A',    href: '/dashboard/verified-qna',    icon: 'check'       },
            { name: 'Ingestion Jobs',  href: '/dashboard/training-jobs',   icon: 'history'     },
        ]
    },
    {
        title: 'Publish',
        items: [
            { name: 'Marketplace', href: '/marketplace',                   icon: 'group' },
            { name: 'Share',    href: '/dashboard/share',               icon: 'share' },
            { name: 'Preview',  href: '/dashboard/simulator/public',    icon: 'profile' },
            { name: 'Widget',   href: '/dashboard/widget',              icon: 'code'  },
            { name: 'API Keys', href: '/dashboard/api-keys',            icon: 'key'   },
        ]
    },
    {
        title: 'Account',
        items: [
            { name: 'Analytics',        href: '/dashboard/insights',         icon: 'chart'    },
            { name: 'Settings',         href: '/dashboard/settings',         icon: 'settings' },
            { name: 'Privacy & Data',   href: '/dashboard/privacy',          icon: 'privacy'  },
            { name: 'Publish Controls', href: '/dashboard/publish-controls', icon: 'publish'  },
        ]
    },
];

export const APP_NAME = 'PersonaOn';
export const APP_TAGLINE = 'Your AI Persona';
