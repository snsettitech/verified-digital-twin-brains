'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { useTwin } from '@/lib/context/TwinContext';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';

interface SidebarItem {
    name: string;
    href: string;
    icon: string;
}

interface SidebarSection {
    title: string;
    items: SidebarItem[];
}

interface SpecializationConfig {
    name: string;
    display_name: string;
    description: string;
    sidebar: {
        sections: SidebarSection[];
    };
    features: Record<string, boolean>;
    default_settings: Record<string, any>;
}

interface SpecializationContextType {
    config: SpecializationConfig | null;
    loading: boolean;
    isFeatureEnabled: (featureName: string) => boolean;
    isVC: boolean;
}

const defaultContext: SpecializationContextType = {
    config: null,
    loading: true,
    isFeatureEnabled: () => false,
    isVC: false
};

const SpecializationContext = createContext<SpecializationContextType>(defaultContext);

export function SpecializationProvider({ children }: { children: React.ReactNode }) {
    const { activeTwin, isLoading: twinLoading } = useTwin();
    const { get } = useAuthFetch();

    const [config, setConfig] = useState<SpecializationConfig | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchConfig = async () => {
            if (twinLoading) return;

            if (!activeTwin?.id) {
                setLoading(false);
                return;
            }

            try {
                const res = await get(`/twins/${activeTwin.id}/specialization`);
                if (res.ok) {
                    const data = await res.json();
                    setConfig(data);
                }
            } catch (err) {
                console.error('Failed to fetch specialization config:', err);
            } finally {
                setLoading(false);
            }
        };

        fetchConfig();
    }, [activeTwin?.id, twinLoading, get]);

    const isFeatureEnabled = (featureName: string): boolean => {
        return config?.features?.[featureName] ?? false;
    };

    const isVC = config?.name === 'vc';

    return (
        <SpecializationContext.Provider value={{ config, loading, isFeatureEnabled, isVC }}>
            {children}
        </SpecializationContext.Provider>
    );
}

export function useSpecialization() {
    const context = useContext(SpecializationContext);
    if (!context) {
        throw new Error('useSpecialization must be used within SpecializationProvider');
    }
    return context;
}

// Hook for feature flag gating
export function useFeatureFlag(featureName: string): boolean {
    const { isFeatureEnabled } = useSpecialization();
    return isFeatureEnabled(featureName);
}
