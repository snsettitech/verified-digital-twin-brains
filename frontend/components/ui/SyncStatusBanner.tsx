'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useTwin } from '@/lib/context/TwinContext';

export default function SyncStatusBanner() {
    const { syncStatus, syncMessage, syncRetryAt, syncUser } = useTwin();
    const [showDetails, setShowDetails] = useState(false);
    const [showSuccess, setShowSuccess] = useState(false);
    const [countdown, setCountdown] = useState<number | null>(null);
    const prevStatusRef = useRef(syncStatus);
    const successTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Track recovery from error to ok for success acknowledgment
    useEffect(() => {
        const wasError = prevStatusRef.current === 'error' || prevStatusRef.current === 'retrying';
        const isNowOk = syncStatus === 'ok';

        if (wasError && isNowOk) {
            // Show success briefly
            setShowSuccess(true);
            if (successTimeoutRef.current) {
                clearTimeout(successTimeoutRef.current);
            }
            successTimeoutRef.current = setTimeout(() => {
                setShowSuccess(false);
            }, 3000);
        }

        prevStatusRef.current = syncStatus;

        return () => {
            if (successTimeoutRef.current) {
                clearTimeout(successTimeoutRef.current);
            }
        };
    }, [syncStatus]);

    // Countdown timer for retry
    useEffect(() => {
        if (!syncRetryAt) {
            setCountdown(null);
            return;
        }

        const updateCountdown = () => {
            const remaining = Math.max(0, Math.ceil((syncRetryAt - Date.now()) / 1000));
            setCountdown(remaining);
        };

        updateCountdown();
        const interval = setInterval(updateCountdown, 1000);

        return () => clearInterval(interval);
    }, [syncRetryAt]);

    const handleRetry = () => {
        syncUser();
    };

    // Success acknowledgment banner (brief, after recovery)
    if (showSuccess && syncStatus === 'ok') {
        return (
            <div className="mb-4 flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 shadow-sm animate-in fade-in slide-in-from-top-2 duration-300">
                <svg className="h-4 w-4 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
                <span className="font-medium">Sync restored</span>
            </div>
        );
    }

    // Don't show for normal states
    if (syncStatus === 'idle' || syncStatus === 'ok' || syncStatus === 'syncing') {
        return null;
    }

    const isRetrying = syncStatus === 'retrying';
    const isError = syncStatus === 'error';

    return (
        <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 shadow-sm overflow-hidden">
            {/* Main banner */}
            <div className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="flex items-center gap-3 text-sm text-amber-800">
                    {isRetrying ? (
                        <div className="h-4 w-4 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
                    ) : (
                        <svg className="h-4 w-4 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M5.07 19h13.86c1.54 0 2.5-1.67 1.73-3L13.73 4c-.77-1.33-2.69-1.33-3.46 0L3.34 16c-.77 1.33.19 3 1.73 3z" />
                        </svg>
                    )}
                    <span className="font-medium">
                        {syncMessage || 'Sync temporarily unavailable.'}
                        {isRetrying && countdown !== null && countdown > 0 && (
                            <span className="text-amber-600 ml-1">({countdown}s)</span>
                        )}
                    </span>
                </div>

                <div className="flex items-center gap-2">
                    {/* Retry button */}
                    {(isError || isRetrying) && (
                        <button
                            onClick={handleRetry}
                            className="px-3 py-1.5 text-xs font-semibold text-amber-800 bg-amber-100 hover:bg-amber-200 border border-amber-300 rounded-lg transition-colors"
                        >
                            Retry now
                        </button>
                    )}

                    {/* Details toggle */}
                    <button
                        onClick={() => setShowDetails(!showDetails)}
                        className="p-1.5 text-amber-600 hover:bg-amber-100 rounded-lg transition-colors"
                        aria-label={showDetails ? 'Hide details' : 'Show details'}
                    >
                        <svg
                            className={`w-4 h-4 transition-transform ${showDetails ? 'rotate-180' : ''}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                        </svg>
                    </button>
                </div>
            </div>

            {/* Expandable details */}
            {showDetails && (
                <div className="px-4 py-3 bg-amber-100/50 border-t border-amber-200 text-xs text-amber-700 space-y-1">
                    <div className="flex justify-between">
                        <span className="font-medium">Status:</span>
                        <span className="font-mono">{syncStatus}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="font-medium">Endpoint:</span>
                        <span className="font-mono">/auth/sync-user</span>
                    </div>
                    {syncRetryAt && (
                        <div className="flex justify-between">
                            <span className="font-medium">Next retry:</span>
                            <span className="font-mono">{new Date(syncRetryAt).toLocaleTimeString()}</span>
                        </div>
                    )}
                    <div className="flex justify-between">
                        <span className="font-medium">Current time:</span>
                        <span className="font-mono">{new Date().toLocaleTimeString()}</span>
                    </div>
                    <p className="mt-2 text-amber-600">
                        If this persists, try refreshing the page or signing out and back in.
                    </p>
                </div>
            )}
        </div>
    );
}
