'use client';

import Link from "next/link";
import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { getSupabaseClient } from '@/lib/supabase/client';
import type { User, Session } from '@supabase/supabase-js';

export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeFaq, setActiveFaq] = useState<number | null>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    const supabase = getSupabaseClient();

    supabase.auth.getSession()
      .then(({ data: { session } }: { data: { session: Session | null } }) => {
        setUser(session?.user ?? null);
      })
      .catch(() => { /* treat network failure as logged-out */ })
      .finally(() => { setLoading(false); });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event: string, session: Session | null) => {
      setUser(session?.user || null);
    });

    observerRef.current = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) entry.target.classList.add('animate-in');
      });
    }, { threshold: 0.1 });

    document.querySelectorAll('.animate-on-scroll').forEach(el => {
      observerRef.current?.observe(el);
    });

    return () => {
      subscription.unsubscribe();
      observerRef.current?.disconnect();
    };
  }, []);

  const handleLogout = async () => {
    const supabase = getSupabaseClient();
    await supabase.auth.signOut();
    setUser(null);
    router.refresh();
  };

  const scrollToSection = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
    setMobileMenuOpen(false);
  };

  return (
    <div className="min-h-screen bg-[#080E1A] text-white overflow-x-hidden" style={{ fontFamily: "var(--font-sans, 'Plus Jakarta Sans', sans-serif)" }}>

      {/* Warm ambient radial — amber top-right, teal bottom-left */}
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute -top-32 right-0 w-[520px] h-[520px] rounded-full bg-amber-500/[0.06] blur-[130px]" />
        <div className="absolute bottom-0 -left-24 w-[380px] h-[380px] rounded-full bg-teal-600/[0.05] blur-[100px]" />
      </div>

      {/* ─── Navigation ─── */}
      <nav className="fixed top-4 left-4 right-4 z-50 rounded-2xl bg-[#0a1120]/85 backdrop-blur-xl border border-white/8 shadow-xl">
        <div className="mx-auto max-w-7xl px-5 lg:px-8">
          <div className="flex items-center justify-between h-14">

            {/* Logo */}
            <Link href="/" className="flex items-center gap-2.5 group" aria-label="PersonaOn AI home">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 shadow-sm">
                <svg viewBox="0 0 24 24" fill="none" className="w-[18px] h-[18px]" aria-hidden="true">
                  <circle cx="12" cy="8" r="3" fill="white" fillOpacity="0.95" />
                  <circle cx="7" cy="16" r="2" fill="white" fillOpacity="0.7" />
                  <circle cx="17" cy="16" r="2" fill="white" fillOpacity="0.7" />
                  <path d="M12 11L7 13.5M12 11L17 13.5" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeOpacity="0.5" />
                </svg>
              </div>
              <span className="text-base font-bold tracking-tight">PersonaOn AI</span>
            </Link>

            {/* Desktop Nav */}
            <div className="hidden md:flex items-center gap-7">
              {[
                { label: 'Features', id: 'features' },
                { label: 'How It Works', id: 'how-it-works' },
                { label: 'FAQ', id: 'faq' },
              ].map(({ label, id }) => (
                <button key={id} onClick={() => scrollToSection(id)} className="cursor-pointer text-sm text-slate-400 hover:text-white transition-colors duration-150">
                  {label}
                </button>
              ))}
              <Link href="/marketplace" className="text-sm text-slate-400 hover:text-white transition-colors duration-150">
                Marketplace
              </Link>

              {loading ? (
                <div className="h-8 w-24 rounded-lg bg-white/5 animate-pulse" />
              ) : user ? (
                <div className="flex items-center gap-4">
                  <Link href="/dashboard" className="text-sm text-slate-400 hover:text-white transition-colors">Dashboard</Link>
                  <button onClick={handleLogout} className="cursor-pointer rounded-full border border-white/10 px-4 py-1.5 text-sm font-medium text-white hover:bg-white/5 transition-colors">
                    Sign Out
                  </button>
                </div>
              ) : (
                <>
                  <Link href="/auth/login" className="text-sm text-slate-400 hover:text-white transition-colors">Sign In</Link>
                  <Link
                    href="/auth/login?redirect=/onboarding"
                    className="rounded-full bg-[#F97316] px-5 py-2 text-sm font-semibold text-white shadow-[0_0_14px_rgba(249,115,22,0.35)] transition-shadow duration-200 hover:shadow-[0_0_22px_rgba(249,115,22,0.55)]"
                  >
                    Build yours free →
                  </Link>
                </>
              )}
            </div>

            {/* Mobile menu button */}
            <button
              className="md:hidden cursor-pointer p-2 text-slate-400 hover:text-white"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Toggle menu"
              aria-expanded={mobileMenuOpen}
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                {mobileMenuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>

        {/* Mobile dropdown */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-white/8 px-5 py-4 space-y-3">
            {[
              { label: 'Features', id: 'features' },
              { label: 'How It Works', id: 'how-it-works' },
              { label: 'FAQ', id: 'faq' },
            ].map(({ label, id }) => (
              <button key={id} onClick={() => scrollToSection(id)} className="cursor-pointer block w-full text-left text-sm text-slate-400 hover:text-white transition-colors">
                {label}
              </button>
            ))}
            <Link href="/marketplace" className="block text-sm text-slate-400 hover:text-white transition-colors">Marketplace</Link>
            {user ? (
              <>
                <Link href="/dashboard" className="block text-sm text-slate-400 hover:text-white transition-colors">Dashboard</Link>
                <button onClick={handleLogout} className="cursor-pointer block w-full text-left text-sm text-slate-400 hover:text-white transition-colors">Sign Out</button>
              </>
            ) : (
              <>
                <Link href="/auth/login" className="block text-sm text-slate-400 hover:text-white transition-colors">Sign In</Link>
                <Link href="/auth/login?redirect=/onboarding" className="mt-2 block w-full rounded-full bg-[#F97316] py-2.5 text-center text-sm font-semibold text-white shadow-[0_0_14px_rgba(249,115,22,0.35)]">
                  Build yours free →
                </Link>
              </>
            )}
          </div>
        )}
      </nav>

      {/* ─── Hero ─── */}
      <section className="relative pt-36 pb-24 lg:pt-48 lg:pb-36">
        <div className="mx-auto max-w-7xl px-6 lg:px-12">
          <div className="grid gap-16 lg:grid-cols-2 lg:gap-20 items-center">

            {/* Left: copy */}
            <div className="animate-on-scroll opacity-0 translate-y-8 transition-all duration-700">
              {/* Badge */}
              <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-amber-500/25 bg-amber-500/10 px-4 py-1.5">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-60" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-500" />
                </span>
                <span className="text-sm font-medium text-amber-300">Your digital persona · always on</span>
              </div>

              {/* Headline — DM Serif Display */}
              <h1 style={{ fontFamily: "'DM Serif Display', Georgia, serif" }} className="text-5xl leading-[1.08] text-white lg:text-6xl xl:text-7xl mb-6">
                Be present,<br />
                <span className="text-amber-100/90">even when<br />you can't be.</span>
              </h1>

              <p className="text-lg leading-8 text-slate-400 max-w-md mb-9">
                Turn your knowledge into an AI that answers exactly like you — with verified sources, your voice, and zero hallucinations.
              </p>

              <div className="flex flex-col sm:flex-row gap-3">
                <Link
                  href={user ? "/dashboard" : "/auth/login?redirect=/onboarding"}
                  className="rounded-full bg-[#F97316] px-7 py-3.5 text-base font-semibold text-white shadow-[0_0_20px_rgba(249,115,22,0.40)] transition-shadow duration-200 hover:shadow-[0_0_32px_rgba(249,115,22,0.60)] text-center"
                >
                  {user ? "Go to Dashboard →" : "Build yours free →"}
                </Link>
                <Link
                  href="/marketplace"
                  className="rounded-full border border-white/10 bg-white/5 px-7 py-3.5 text-base font-semibold text-white hover:bg-white/10 transition-colors text-center"
                >
                  Browse Personas
                </Link>
              </div>

              <p className="mt-4 text-xs text-slate-500">Free forever · No credit card · 2-minute setup</p>
            </div>

            {/* Right: demo card */}
            <div className="animate-on-scroll opacity-0 translate-y-8 transition-all duration-700 delay-200">
              <div className="relative rounded-[28px] border border-white/10 bg-[#0F1C2E] p-6 shadow-2xl">
                {/* Card header */}
                <div className="flex items-center gap-3 border-b border-white/8 pb-5 mb-5">
                  <div className="flex h-10 w-10 items-center justify-center rounded-[10px] bg-[linear-gradient(135deg,#f59e0b,#f97316)] text-sm font-bold text-white">
                    AR
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-white">Alex Rivera</p>
                    <p className="text-xs text-slate-500">Product Strategy · Always On</p>
                  </div>
                  <div className="flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" aria-hidden="true" />
                    Live
                  </div>
                </div>

                {/* Stats */}
                <div className="mb-5 grid grid-cols-3 gap-3">
                  {[
                    { label: 'Conversations', value: '1.4k' },
                    { label: 'Verified Sources', value: '218' },
                    { label: 'Live Advice', value: 'Always on' },
                  ].map(({ label, value }) => (
                    <div key={label} className="rounded-[14px] bg-[#162236] p-3 text-center">
                      <p className="text-lg font-semibold text-white">{value}</p>
                      <p className="mt-0.5 text-[10px] uppercase tracking-[0.12em] text-slate-400">{label}</p>
                    </div>
                  ))}
                </div>

                {/* Chat preview */}
                <div className="space-y-3 rounded-[18px] bg-[#060C18] p-4">
                  <div className="flex gap-2.5">
                    <div className="shrink-0 h-7 w-7 rounded-full bg-[linear-gradient(135deg,#f59e0b,#f97316)] flex items-center justify-center text-[10px] font-bold text-white">AR</div>
                    <div className="max-w-[82%] rounded-[16px] rounded-tl-sm bg-[#0F1C2E] px-3 py-2.5 text-sm leading-6 text-slate-200">
                      Hi! Ask me anything about product strategy or growth — I'll answer from my actual work.
                    </div>
                  </div>
                  <div className="flex justify-end gap-2.5">
                    <div className="max-w-[82%] rounded-[16px] rounded-tr-sm bg-blue-600/20 border border-blue-500/20 px-3 py-2.5 text-sm leading-6 text-blue-100">
                      How do you prioritize features with limited eng bandwidth?
                    </div>
                  </div>
                  <div className="flex gap-2.5">
                    <div className="shrink-0 h-7 w-7 rounded-full bg-[linear-gradient(135deg,#f59e0b,#f97316)] flex items-center justify-center text-[10px] font-bold text-white">AR</div>
                    <div className="max-w-[82%] rounded-[16px] rounded-tl-sm bg-[#0F1C2E] px-3 py-2.5 text-sm leading-6 text-slate-200">
                      I start with impact-to-effort ratio, then layer in strategic bets…
                      <span className="ml-1.5 inline-flex h-4 w-4 items-center justify-center rounded bg-blue-600/30 text-[10px] font-semibold text-blue-300">1</span>
                    </div>
                  </div>
                </div>

                {/* Input */}
                <div className="mt-4 flex gap-2.5 rounded-[14px] border border-white/8 bg-[#060C18] px-4 py-3">
                  <span className="flex-1 text-sm text-slate-400">Ask Alex anything…</span>
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600">
                    <svg className="h-3.5 w-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 12h14M12 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── How It Works ─── */}
      <section id="how-it-works" className="py-28">
        <div className="mx-auto max-w-6xl px-6 lg:px-12">
          <div className="animate-on-scroll opacity-0 translate-y-8 transition-all duration-700 mb-16 text-center">
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">How It Works</p>
            <h2 style={{ fontFamily: "'DM Serif Display', Georgia, serif" }} className="text-4xl text-white lg:text-5xl">
              From knowledge to persona in minutes
            </h2>
          </div>

          <div className="grid gap-5 md:grid-cols-3">
            {[
              {
                num: '01',
                title: 'Connect your content',
                desc: 'Upload PDFs, paste URLs, connect Notion or YouTube. Your knowledge becomes the source of truth.',
                icon: (
                  <svg className="h-6 w-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                ),
              },
              {
                num: '02',
                title: 'Capture your voice',
                desc: 'Answer a few questions about your style, values, and expertise boundaries. Takes 5 minutes.',
                icon: (
                  <svg className="h-6 w-6 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                  </svg>
                ),
              },
              {
                num: '03',
                title: 'Share everywhere',
                desc: 'Get a shareable link, embed on your site, or list in the public marketplace.',
                icon: (
                  <svg className="h-6 w-6 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                  </svg>
                ),
              },
            ].map((step, i) => (
              <div
                key={step.num}
                className="animate-on-scroll opacity-0 translate-y-8 transition-all duration-700 relative rounded-[22px] border border-white/8 bg-[#0F1C2E] p-8"
                style={{ transitionDelay: `${i * 80}ms` }}
              >
                <p className="absolute top-6 right-7 text-5xl font-black text-white/[0.04] select-none">{step.num}</p>
                <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-[14px] bg-white/5 border border-white/8">
                  {step.icon}
                </div>
                <h3 className="mb-2 text-lg font-semibold text-white">{step.title}</h3>
                <p className="text-sm leading-7 text-slate-400">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Features ─── */}
      <section id="features" className="py-28">
        <div className="mx-auto max-w-6xl px-6 lg:px-12">
          <div className="animate-on-scroll opacity-0 translate-y-8 transition-all duration-700 mb-16 text-center">
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Features</p>
            <h2 style={{ fontFamily: "'DM Serif Display', Georgia, serif" }} className="text-4xl text-white lg:text-5xl">
              Built for trust
            </h2>
          </div>

          {/* 4-col feature grid — Delphi style */}
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                title: 'Source Citations',
                desc: 'Every answer links to the source document. No hallucinations, fully traceable.',
                icon: (
                  <svg className="h-5 w-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                ),
              },
              {
                title: 'Voice Consistent',
                desc: 'Trained on your writing style, tone, and decision patterns — sounds like you.',
                icon: (
                  <svg className="h-5 w-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75" d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                  </svg>
                ),
              },
              {
                title: 'Confidence Scoring',
                desc: 'Each response shows how confident your persona is. Low scores trigger escalation.',
                icon: (
                  <svg className="h-5 w-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                ),
              },
              {
                title: 'Access Control',
                desc: 'Public link, password-protected, or private. You choose who can talk to your persona.',
                icon: (
                  <svg className="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                ),
              },
              {
                title: 'Human Escalation',
                desc: 'Questions outside your expertise are flagged and queued for your review.',
                icon: (
                  <svg className="h-5 w-5 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                  </svg>
                ),
              },
              {
                title: 'Knowledge Graph',
                desc: 'Structured memory of your beliefs, stances, and expertise — updated as you learn.',
                badge: 'Beta',
                icon: (
                  <svg className="h-5 w-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                  </svg>
                ),
              },
              {
                title: 'Marketplace',
                desc: 'List your persona publicly so anyone can discover and chat with your AI.',
                icon: (
                  <svg className="h-5 w-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                ),
              },
              {
                title: 'Always Free',
                desc: 'No paywalls, no credits. Build and share your persona at no cost.',
                icon: (
                  <svg className="h-5 w-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                ),
              },
            ].map((feature, i) => (
              <div
                key={feature.title}
                className="animate-on-scroll opacity-0 translate-y-8 transition-all duration-700 rounded-[20px] border border-white/8 bg-[#0F1C2E] p-6 hover:border-white/12 transition-colors"
                style={{ transitionDelay: `${i * 50}ms` }}
              >
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-[12px] bg-white/5 border border-white/8">
                  {feature.icon}
                </div>
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="text-sm font-semibold text-white">{feature.title}</h3>
                  {feature.badge && (
                    <span className="rounded-full bg-amber-500/15 border border-amber-500/30 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-amber-400">
                      {feature.badge}
                    </span>
                  )}
                </div>
                <p className="text-sm leading-6 text-slate-500">{feature.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── FAQ ─── */}
      <section id="faq" className="py-28">
        <div className="mx-auto max-w-3xl px-6 lg:px-12">
          <div className="animate-on-scroll opacity-0 translate-y-8 transition-all duration-700 mb-16 text-center">
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">FAQ</p>
            <h2 style={{ fontFamily: "'DM Serif Display', Georgia, serif" }} className="text-4xl text-white lg:text-5xl">
              Common questions
            </h2>
          </div>

          <div className="space-y-2">
            {[
              { q: 'How is this different from ChatGPT?', a: 'Your persona only answers from your verified knowledge sources — no hallucinations, no generic answers. It learns your specific voice, decision style, and expertise boundaries through structured training, not just prompt engineering.' },
              { q: 'Can I update my persona\'s knowledge?', a: 'Yes. Add new documents, URLs, or text anytime. Your persona automatically incorporates new knowledge while maintaining the same consistent voice.' },
              { q: 'Is my data private?', a: 'Your training data and knowledge sources are isolated per user with Row Level Security. We never use your data to train models for other users. Full export and deletion supported.' },
              { q: 'Is it really free?', a: 'Yes — build your persona and share it at no cost. We believe everyone should have access to this technology.' },
              { q: 'What happens if someone asks something I haven\'t covered?', a: 'Unsupported or review-worthy questions are queued in your dashboard so you can answer them directly or add the topic to your knowledge base.' },
            ].map((faq, i) => (
              <div
                key={i}
                className="animate-on-scroll opacity-0 translate-y-8 transition-all duration-700 rounded-[18px] border border-white/8 overflow-hidden"
                style={{ transitionDelay: `${i * 60}ms` }}
              >
                <button
                  id={`faq-btn-${i}`}
                  className="cursor-pointer flex w-full items-center justify-between gap-4 px-6 py-5 text-left hover:bg-white/[0.02] transition-colors"
                  onClick={() => setActiveFaq(activeFaq === i ? null : i)}
                  aria-expanded={activeFaq === i}
                  aria-controls={`faq-panel-${i}`}
                >
                  <span className="text-sm font-semibold text-white">{faq.q}</span>
                  <svg
                    className={`h-4 w-4 shrink-0 text-slate-400 transition-transform duration-200 ${activeFaq === i ? 'rotate-180' : ''}`}
                    fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                <div
                  id={`faq-panel-${i}`}
                  role="region"
                  aria-labelledby={`faq-btn-${i}`}
                  className={`overflow-hidden transition-[max-height] duration-300 ease-in-out ${activeFaq === i ? 'max-h-40' : 'max-h-0'}`}
                >
                  <p className="px-6 pb-5 text-sm leading-7 text-slate-400">{faq.a}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Final CTA ─── */}
      <section className="relative py-28 overflow-hidden">
        <div className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full bg-amber-500/[0.07] blur-[100px]" />
        <div className="relative mx-auto max-w-3xl px-6 lg:px-12 text-center">
          <div className="animate-on-scroll opacity-0 translate-y-8 transition-all duration-700 rounded-[32px] border border-white/8 bg-[#0F1C2E] px-8 py-16 sm:px-16">
            <h2 style={{ fontFamily: "'DM Serif Display', Georgia, serif" }} className="text-4xl text-white mb-4 lg:text-5xl">
              Your persona, always on.
            </h2>
            <p className="mb-8 text-lg leading-8 text-slate-400 max-w-sm mx-auto">
              Build once. Answer every question — even while you sleep.
            </p>
            <Link
              href={user ? "/dashboard" : "/auth/login?redirect=/onboarding"}
              className="inline-block rounded-full bg-[#F97316] px-8 py-4 text-base font-semibold text-white shadow-[0_0_24px_rgba(249,115,22,0.45)] transition-shadow duration-200 hover:shadow-[0_0_40px_rgba(249,115,22,0.65)]"
            >
              {user ? "Go to Dashboard →" : "Build yours free →"}
            </Link>
            <p className="mt-4 text-xs text-slate-500">Free forever · No credit card</p>
          </div>
        </div>
      </section>

      {/* ─── Footer ─── */}
      <footer className="border-t border-white/[0.05] py-14">
        <div className="mx-auto max-w-6xl px-6 lg:px-12">
          <div className="grid gap-10 md:grid-cols-4 mb-12">
            {/* Brand */}
            <div className="md:col-span-1">
              <div className="mb-3 flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600">
                  <svg viewBox="0 0 24 24" fill="none" className="h-3.5 w-3.5" aria-hidden="true">
                    <circle cx="12" cy="8" r="3" fill="white" fillOpacity="0.95" />
                    <circle cx="7" cy="16" r="2" fill="white" fillOpacity="0.7" />
                    <circle cx="17" cy="16" r="2" fill="white" fillOpacity="0.7" />
                  </svg>
                </div>
                <span className="text-sm font-bold">PersonaOn AI</span>
              </div>
              <p className="text-sm leading-6 text-slate-500">Your digital persona, always on.</p>
            </div>

            {/* Product */}
            <div>
              <h4 className="mb-4 text-xs font-semibold uppercase tracking-[0.15em] text-slate-400">Product</h4>
              <ul className="space-y-2.5">
                <li><Link href="#features" className="text-sm text-slate-500 hover:text-white transition-colors">Features</Link></li>
                <li><Link href="/marketplace" className="text-sm text-slate-500 hover:text-white transition-colors">Marketplace</Link></li>
                <li><span className="text-sm text-slate-600 cursor-default" aria-disabled="true">API</span></li>
              </ul>
            </div>

            {/* Resources */}
            <div>
              <h4 className="mb-4 text-xs font-semibold uppercase tracking-[0.15em] text-slate-400">Resources</h4>
              <ul className="space-y-2.5">
                {['Documentation', 'Blog', 'Help Center'].map((item) => (
                  <li key={item}><span className="text-sm text-slate-600 cursor-default" aria-disabled="true">{item}</span></li>
                ))}
              </ul>
            </div>

            {/* Company */}
            <div>
              <h4 className="mb-4 text-xs font-semibold uppercase tracking-[0.15em] text-slate-400">Company</h4>
              <ul className="space-y-2.5">
                {['About', 'Privacy', 'Contact'].map((item) => (
                  <li key={item}><span className="text-sm text-slate-600 cursor-default" aria-disabled="true">{item}</span></li>
                ))}
              </ul>
            </div>
          </div>

          <div className="flex flex-col gap-4 border-t border-white/[0.05] pt-8 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-500">© 2026 PersonaOn AI. All rights reserved.</p>
            <div className="flex gap-2">
              {[
                { label: 'X', ariaLabel: 'X (Twitter)', href: '#' },
                { label: 'GH', ariaLabel: 'GitHub', href: '#' },
              ].map(({ label, ariaLabel, href }) => (
                <a key={label} href={href} className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/5 text-[11px] font-bold text-slate-500 hover:bg-white/8 hover:text-white transition-colors" aria-label={ariaLabel}>
                  {label}
                </a>
              ))}
            </div>
          </div>
        </div>
      </footer>

      {/* Scroll-in animation */}
      <style jsx>{`
        .animate-in {
          opacity: 1 !important;
          transform: translateY(0) !important;
        }
      `}</style>
    </div>
  );
}
