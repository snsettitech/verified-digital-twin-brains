import { redirect } from 'next/navigation';

/**
 * Legacy route preserved for backward-compatible links.
 * Canonical destination for persona editing is /dashboard/studio.
 */
export default function RightBrainPage() {
    redirect('/dashboard/studio');
}
