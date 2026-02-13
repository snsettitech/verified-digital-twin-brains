import { redirect } from 'next/navigation';

/**
 * Legacy route preserved for backward-compatible links.
 * Canonical destination for interview/training flows is /dashboard/simulator.
 */
export default function InterviewPage() {
    redirect('/dashboard/simulator');
}
