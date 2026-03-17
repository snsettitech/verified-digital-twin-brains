import { redirect } from 'next/navigation';

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Block admin access in production until role-based auth is implemented
  if (process.env.NODE_ENV === 'production') {
    redirect('/dashboard');
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-slate-900 text-white px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <h1 className="text-xl font-bold">Admin Dashboard</h1>
          <a href="/dashboard" className="text-sm text-slate-400 hover:text-white">
            Back to App →
          </a>
        </div>
      </header>
      <main className="max-w-7xl mx-auto p-6">
        {children}
      </main>
    </div>
  );
}
