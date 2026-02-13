'use client';

import Link from "next/link";
import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { getSupabaseClient } from '@/lib/supabase/client';
import type { User, Session } from '@supabase/supabase-js';

// Digital Brains Landing Page - New Design
export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeFaq, setActiveFaq] = useState<number | null>(null);

  // Scroll animation observer
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    const supabase = getSupabaseClient();
    
    // Check current session
    supabase.auth.getSession().then(({ data: { session } }: { data: { session: Session | null } }) => {
      setUser(session?.user || null);
      setLoading(false);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event: string, session: Session | null) => {
      setUser(session?.user || null);
    });

    // Scroll animations
    observerRef.current = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('animate-in');
        }
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

  const toggleFaq = (index: number) => {
    setActiveFaq(activeFaq === index ? null : index);
  };

  const scrollToSection = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
    setMobileMenuOpen(false);
  };

  return (
    <div className="min-h-screen bg-[#0F0F1A] text-white font-sans overflow-x-hidden">
      {/* Animated Grid Background */}
      <div 
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage: `
            linear-gradient(rgba(79, 70, 229, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(79, 70, 229, 0.03) 1px, transparent 1px)
          `,
          backgroundSize: '60px 60px',
        }}
      />

      {/* Floating Gradient Orbs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-[500px] h-[500px] bg-[#4F46E5]/20 rounded-full blur-[120px]" />
        <div className="absolute bottom-20 -left-40 w-[400px] h-[400px] bg-[#7C3AED]/15 rounded-full blur-[100px]" />
      </div>

      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-[#0F0F1A]/80 backdrop-blur-xl border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-3 group">
              <div className="w-10 h-10 relative">
                <svg viewBox="0 0 44 44" fill="none" className="w-full h-full">
                  <path d="M22 2L40 12V32L22 42L4 32V12L22 2Z" fill="url(#logoGradient)" stroke="rgba(255,255,255,0.2)" strokeWidth="1"/>
                  <circle cx="22" cy="16" r="4" fill="white" fillOpacity="0.9"/>
                  <circle cx="14" cy="26" r="3" fill="white" fillOpacity="0.7"/>
                  <circle cx="30" cy="26" r="3" fill="white" fillOpacity="0.7"/>
                  <circle cx="22" cy="32" r="2.5" fill="white" fillOpacity="0.8"/>
                  <path d="M22 20L14 23M22 20L30 23M14 29L22 30M30 29L22 30" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeOpacity="0.6"/>
                  <defs>
                    <linearGradient id="logoGradient" x1="4" y1="2" x2="40" y2="42">
                      <stop stopColor="#4F46E5"/>
                      <stop offset="0.5" stopColor="#7C3AED"/>
                      <stop offset="1" stopColor="#EC4899"/>
                    </linearGradient>
                  </defs>
                </svg>
              </div>
              <span className="text-lg font-bold">Digital Brains</span>
            </Link>

            {/* Desktop Nav */}
            <div className="hidden md:flex items-center gap-8">
              <button onClick={() => scrollToSection('features')} className="text-sm text-slate-400 hover:text-white transition-colors relative group">
                Features
                <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] group-hover:w-full transition-all duration-200" />
              </button>
              <button onClick={() => scrollToSection('how-it-works')} className="text-sm text-slate-400 hover:text-white transition-colors relative group">
                How It Works
                <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] group-hover:w-full transition-all duration-200" />
              </button>
              <button onClick={() => scrollToSection('pricing')} className="text-sm text-slate-400 hover:text-white transition-colors relative group">
                Pricing
                <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] group-hover:w-full transition-all duration-200" />
              </button>
              <button onClick={() => scrollToSection('faq')} className="text-sm text-slate-400 hover:text-white transition-colors relative group">
                FAQ
                <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] group-hover:w-full transition-all duration-200" />
              </button>
              
              {loading ? (
                <div className="w-8 h-8 rounded-full bg-slate-700 animate-pulse" />
              ) : user ? (
                <div className="flex items-center gap-4">
                  <Link href="/dashboard" className="text-sm text-slate-400 hover:text-white transition-colors">
                    Dashboard
                  </Link>
                  <button
                    onClick={handleLogout}
                    className="px-4 py-2 bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] text-white text-sm font-semibold rounded-lg hover:shadow-lg hover:shadow-indigo-500/30 transition-all"
                  >
                    Sign Out
                  </button>
                </div>
              ) : (
                <>
                  <Link href="/auth/login" className="text-sm text-slate-400 hover:text-white transition-colors">Sign In</Link>
                  <Link
                    href="/auth/login?redirect=/onboarding"
                    className="px-4 py-2 bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] text-white text-sm font-semibold rounded-lg hover:shadow-lg hover:shadow-indigo-500/30 transition-all hover:-translate-y-0.5"
                  >
                    Get Started
                  </Link>
                </>
              )}
            </div>

            {/* Mobile Menu Button */}
            <button 
              className="md:hidden p-2 text-slate-400"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {mobileMenuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden bg-[#0F0F1A]/95 backdrop-blur-xl border-t border-white/5">
            <div className="px-6 py-4 space-y-4">
              <button onClick={() => scrollToSection('features')} className="block w-full text-left text-sm text-slate-400 hover:text-white transition-colors">Features</button>
              <button onClick={() => scrollToSection('how-it-works')} className="block w-full text-left text-sm text-slate-400 hover:text-white transition-colors">How It Works</button>
              <button onClick={() => scrollToSection('pricing')} className="block w-full text-left text-sm text-slate-400 hover:text-white transition-colors">Pricing</button>
              <button onClick={() => scrollToSection('faq')} className="block w-full text-left text-sm text-slate-400 hover:text-white transition-colors">FAQ</button>
              {user ? (
                <>
                  <Link href="/dashboard" className="block text-sm text-slate-400 hover:text-white transition-colors">Dashboard</Link>
                  <button onClick={handleLogout} className="w-full px-4 py-2 bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] text-white text-sm font-semibold rounded-lg">Sign Out</button>
                </>
              ) : (
                <>
                  <Link href="/auth/login" className="block text-sm text-slate-400 hover:text-white transition-colors">Sign In</Link>
                  <Link href="/auth/login?redirect=/onboarding" className="block w-full px-4 py-2 bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] text-white text-sm font-semibold rounded-lg text-center">Get Started</Link>
                </>
              )}
            </div>
          </div>
        )}
      </nav>

      {/* Hero Section */}
      <section className="relative pt-32 pb-20 lg:pt-40 lg:pb-32">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-20 items-center">
            {/* Hero Text */}
            <div className="animate-on-scroll opacity-0 translate-y-10 transition-all duration-700">
              <div className="inline-flex items-center gap-2 px-4 py-2 bg-[#4F46E5]/10 border border-[#4F46E5]/30 rounded-full mb-6">
                <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
                <span className="text-sm text-[#A5B4FC]">Trusted by 1,000+ creators</span>
              </div>
              
              <h1 className="text-5xl lg:text-6xl font-extrabold leading-tight mb-6">
                Create Your{' '}
                <span className="bg-gradient-to-r from-white via-[#A5B4FC] to-[#C4B5FD] bg-clip-text text-transparent">
                  Digital Twin
                </span>
              </h1>
              
              <p className="text-lg lg:text-xl text-slate-400 mb-8 leading-relaxed">
                An AI that answers exactly like you—with verified sources and zero hallucinations. Train once, scale infinitely.
              </p>

              <div className="flex flex-col sm:flex-row gap-4 mb-10">
                {user ? (
                  <Link
                    href="/dashboard"
                    className="group px-8 py-4 bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] text-white font-semibold rounded-xl shadow-lg shadow-indigo-500/30 hover:shadow-indigo-500/50 transition-all hover:-translate-y-0.5 flex items-center justify-center gap-2"
                  >
                    Go to Dashboard
                    <svg className="w-5 h-5 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                    </svg>
                  </Link>
                ) : (
                  <Link
                    href="/auth/login?redirect=/onboarding"
                    className="group px-8 py-4 bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] text-white font-semibold rounded-xl shadow-lg shadow-indigo-500/30 hover:shadow-indigo-500/50 transition-all hover:-translate-y-0.5 flex items-center justify-center gap-2"
                  >
                    Build Your Twin Free
                    <svg className="w-5 h-5 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                    </svg>
                  </Link>
                )}
                <button className="px-8 py-4 bg-white/5 text-white font-semibold rounded-xl border border-white/10 hover:bg-white/10 transition-all">
                  View Demo
                </button>
              </div>

              <div>
                <p className="text-xs text-slate-500 uppercase tracking-widest mb-3">Backed by teams at</p>
                <div className="flex flex-wrap gap-6">
                  {['Stripe', 'Notion', 'Figma', 'Linear'].map((company) => (
                    <span key={company} className="text-lg font-bold text-slate-500 hover:text-slate-400 transition-colors cursor-default">
                      {company}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Hero Demo Card */}
            <div className="animate-on-scroll opacity-0 translate-y-10 transition-all duration-700 delay-200 lg:perspective-1000">
              <div className="relative bg-[#1A1A2E]/80 backdrop-blur-xl border border-white/10 rounded-3xl p-6 shadow-2xl hover:shadow-indigo-500/10 transition-all duration-300 lg:rotate-y-[-5deg] lg:hover:rotate-y-0">
                {/* Demo Header */}
                <div className="flex items-center gap-3 mb-5 pb-5 border-b border-white/5">
                  <div className="w-11 h-11 bg-gradient-to-br from-[#4F46E5] to-[#7C3AED] rounded-xl flex items-center justify-center font-bold">
                    LR
                  </div>
                  <div className="flex-1">
                    <h4 className="font-semibold text-sm">Lenny Rachitsky</h4>
                    <p className="text-xs text-slate-500">Product & Growth Advisor</p>
                  </div>
                  <div className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-500/10 text-emerald-400 rounded-full text-xs font-semibold">
                    <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
                    LIVE
                  </div>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-2 gap-3 mb-5">
                  <div className="bg-white/5 border border-white/5 rounded-xl p-4 text-center hover:bg-white/[0.07] hover:border-[#4F46E5]/30 transition-all">
                    <div className="text-2xl font-bold bg-gradient-to-r from-white to-[#A5B4FC] bg-clip-text text-transparent">2,847</div>
                    <div className="text-xs text-slate-500 uppercase tracking-wide mt-1">Conversations</div>
                  </div>
                  <div className="bg-white/5 border border-white/5 rounded-xl p-4 text-center hover:bg-white/[0.07] hover:border-[#4F46E5]/30 transition-all">
                    <div className="text-2xl font-bold bg-gradient-to-r from-white to-[#A5B4FC] bg-clip-text text-transparent">98.5%</div>
                    <div className="text-xs text-slate-500 uppercase tracking-wide mt-1">Accuracy</div>
                  </div>
                </div>

                {/* Chat Preview */}
                <div className="bg-black/30 rounded-2xl p-4 mb-4 space-y-3">
                  <div className="flex gap-2.5">
                    <div className="w-7 h-7 bg-gradient-to-br from-[#4F46E5] to-[#7C3AED] rounded-lg flex items-center justify-center text-xs font-bold shrink-0">LR</div>
                    <div className="bg-[#4F46E5]/20 rounded-xl rounded-tl-sm px-3 py-2 text-sm text-slate-200 max-w-[80%]">
                      Hi! I'm Lenny's digital twin. Ask me anything about product management, growth, or startup advice.
                    </div>
                  </div>
                  <div className="flex gap-2.5 justify-end">
                    <div className="bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] rounded-xl rounded-tr-sm px-3 py-2 text-sm text-white max-w-[80%]">
                      What's your framework for prioritizing features?
                    </div>
                  </div>
                  <div className="flex gap-2.5">
                    <div className="w-7 h-7 bg-gradient-to-br from-[#4F46E5] to-[#7C3AED] rounded-lg flex items-center justify-center text-xs font-bold shrink-0">LR</div>
                    <div className="bg-[#4F46E5]/20 rounded-xl rounded-tl-sm px-3 py-2 text-sm text-slate-200 max-w-[80%]">
                      I use RICE (Reach, Impact, Confidence, Effort) combined with strategic bets...
                    </div>
                  </div>
                </div>

                {/* Input */}
                <div className="flex items-center gap-3 bg-white/5 border border-white/10 rounded-xl px-4 py-3">
                  <span className="text-sm text-slate-500 flex-1">Type your message...</span>
                  <button className="w-8 h-8 bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] rounded-lg flex items-center justify-center text-white hover:scale-110 transition-transform">
                    →
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Divider */}
      <div className="h-px bg-gradient-to-r from-transparent via-[#4F46E5]/30 to-transparent mx-12" />

      {/* How It Works */}
      <section id="how-it-works" className="py-24">
        <div className="max-w-6xl mx-auto px-6 lg:px-12">
          <div className="text-center mb-16 animate-on-scroll opacity-0 translate-y-10 transition-all duration-700">
            <div className="text-xs text-[#A5B4FC] uppercase tracking-[0.2em] mb-4">How It Works</div>
            <h2 className="text-4xl lg:text-5xl font-extrabold mb-4">Three steps to your AI twin</h2>
            <p className="text-lg text-slate-400">From content to conversation in minutes, not months</p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {/* ISSUE-001: Updated step 2 terminology from "Train" to "Capture" */}
            {[
              { num: '01', icon: '📤', title: 'Connect Your Content', desc: 'Upload documents, connect URLs, or paste text. We support PDFs, Notion, YouTube transcripts, and more.' },
              { num: '02', icon: '🧠', title: 'Capture Your Voice', desc: 'Answer a few questions to capture your voice, decision style, and expertise boundaries. Takes 5 minutes.' },
              { num: '03', icon: '🚀', title: 'Share Everywhere', desc: 'Get a shareable link, embed on your website, or integrate with Slack, Discord, or your API.' },
            ].map((step, i) => (
              <div 
                key={i} 
                className="animate-on-scroll opacity-0 translate-y-10 transition-all duration-700 relative bg-white/[0.03] border border-white/[0.08] rounded-2xl p-8 backdrop-blur-sm hover:-translate-y-1 hover:border-[#4F46E5]/30 hover:shadow-xl hover:shadow-indigo-500/10 transition-all"
                style={{ transitionDelay: `${i * 100}ms` }}
              >
                <div className="absolute top-4 right-4 text-7xl font-extrabold text-[#4F46E5]/10 leading-none">{step.num}</div>
                <div className="w-14 h-14 bg-gradient-to-br from-[#4F46E5]/20 to-[#7C3AED]/20 rounded-2xl flex items-center justify-center text-2xl mb-5 border border-[#4F46E5]/30">
                  {step.icon}
                </div>
                <h3 className="text-xl font-bold mb-2">{step.title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24">
        <div className="max-w-6xl mx-auto px-6 lg:px-12">
          <div className="text-center mb-16 animate-on-scroll opacity-0 translate-y-10 transition-all duration-700">
            <div className="text-xs text-[#A5B4FC] uppercase tracking-[0.2em] mb-4">Features</div>
            <h2 className="text-4xl lg:text-5xl font-extrabold mb-4">Built for trust, designed for scale</h2>
            <p className="text-lg text-slate-400">Everything you need to create a reliable AI twin</p>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            {/* Large Feature Card - Citations */}
            <div className="animate-on-scroll opacity-0 translate-y-10 transition-all duration-700 md:col-span-2 bg-white/[0.03] border border-white/[0.08] rounded-2xl p-8 hover:-translate-y-1 hover:border-[#4F46E5]/30 hover:shadow-xl hover:shadow-indigo-500/10 transition-all">
              <div className="w-12 h-12 bg-gradient-to-br from-[#4F46E5]/20 to-[#7C3AED]/20 rounded-xl flex items-center justify-center text-xl mb-4 border border-[#4F46E5]/30">📚</div>
              <h3 className="text-xl font-bold mb-2">Source Citations</h3>
              <p className="text-slate-400 mb-6">Every answer includes inline citations linking back to your original sources. Build trust with verified, traceable information.</p>
              <div className="bg-black/20 rounded-xl p-5 border border-white/5">
                <p className="text-sm text-slate-300">
                  I recommend focusing on customer retention first
                  <span className="inline-flex items-center justify-center w-5 h-5 bg-[#4F46E5]/30 text-[#A5B4FC] rounded text-xs mx-1 cursor-pointer hover:bg-[#4F46E5]/50 transition-colors">1</span>
                  then expansion revenue.
                  <span className="inline-flex items-center justify-center w-5 h-5 bg-[#4F46E5]/30 text-[#A5B4FC] rounded text-xs mx-1 cursor-pointer hover:bg-[#4F46E5]/50 transition-colors">2</span>
                </p>
              </div>
            </div>

            {/* Feature Cards */}
            {[
              { icon: '✓', title: 'Confidence Scoring', desc: 'See exactly how confident your twin is in each response. Low confidence triggers automatic clarification.' },
              { icon: '🎭', title: 'Voice Consistency', desc: 'Your twin learns your unique writing style, tone, and decision-making patterns from training.' },
              { icon: '🚨', title: 'Human Escalation', desc: 'Questions outside your expertise are automatically escalated to you with suggested responses.' },
              { icon: '🔒', title: 'Access Control', desc: 'Control who can chat with your twin. Public links, password protection, or invite-only access.' },
            ].map((feature, i) => (
              <div 
                key={i}
                className="animate-on-scroll opacity-0 translate-y-10 transition-all duration-700 bg-white/[0.03] border border-white/[0.08] rounded-2xl p-6 hover:-translate-y-1 hover:border-[#4F46E5]/30 hover:shadow-xl hover:shadow-indigo-500/10 transition-all"
                style={{ transitionDelay: `${(i + 1) * 100}ms` }}
              >
                <div className="w-12 h-12 bg-gradient-to-br from-[#4F46E5]/20 to-[#7C3AED]/20 rounded-xl flex items-center justify-center text-lg mb-4 border border-[#4F46E5]/30">
                  {feature.icon}
                </div>
                <h3 className="text-lg font-bold mb-2">{feature.title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed">{feature.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-24">
        <div className="max-w-6xl mx-auto px-6 lg:px-12">
          <div className="text-center mb-16 animate-on-scroll opacity-0 translate-y-10 transition-all duration-700">
            <div className="text-xs text-[#A5B4FC] uppercase tracking-[0.2em] mb-4">Pricing</div>
            <h2 className="text-4xl lg:text-5xl font-extrabold mb-4">Simple, transparent pricing</h2>
            <p className="text-lg text-slate-400">Start free, scale as you grow</p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {[
              { name: 'Starter', price: 'Free', period: '', desc: 'Perfect for trying out your first twin', features: ['1 digital twin', '100 messages/month', '3 knowledge sources', 'Basic embed widget', 'Community support'], cta: 'Get Started', featured: false },
              { name: 'Pro', price: '$29', period: '/month', desc: 'For creators ready to scale', features: ['3 digital twins', 'Unlimited messages', 'Unlimited sources', 'Custom branding', 'API access', 'Priority support'], cta: 'Start 14-Day Trial', featured: true },
              { name: 'Enterprise', price: 'Custom', period: '', desc: 'For teams with advanced needs', features: ['Unlimited twins', 'SSO / SAML', 'Custom integrations', 'SLA guarantee', 'Dedicated support', 'Audit logs'], cta: 'Contact Sales', featured: false },
            ].map((plan, i) => (
              <div 
                key={i}
                className={`animate-on-scroll opacity-0 translate-y-10 transition-all duration-700 relative rounded-3xl p-8 transition-all hover:-translate-y-1 ${
                  plan.featured 
                    ? 'bg-gradient-to-b from-[#4F46E5]/10 to-[#7C3AED]/10 border border-[#4F46E5]/30 shadow-xl shadow-indigo-500/20' 
                    : 'bg-white/[0.03] border border-white/[0.08] hover:border-white/[0.15]'
                }`}
                style={{ transitionDelay: `${i * 100}ms` }}
              >
                {plan.featured && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] text-white text-xs font-bold rounded-full">
                    Most Popular
                  </div>
                )}
                <h3 className="text-lg font-bold mb-2">{plan.name}</h3>
                <div className="mb-2">
                  <span className="text-4xl font-extrabold">{plan.price}</span>
                  {plan.period && <span className="text-slate-400">{plan.period}</span>}
                </div>
                <p className="text-sm text-slate-400 mb-6">{plan.desc}</p>
                <ul className="space-y-3 mb-8">
                  {plan.features.map((feature, j) => (
                    <li key={j} className="flex items-center gap-3 text-sm">
                      <span className="w-5 h-5 bg-emerald-500/10 text-emerald-400 rounded-full flex items-center justify-center text-xs">✓</span>
                      <span className="text-slate-300">{feature}</span>
                    </li>
                  ))}
                </ul>
                <Link
                  href={user ? "/dashboard" : "/auth/login?redirect=/onboarding"}
                  className={`block w-full py-3 text-center font-semibold rounded-xl transition-all hover:-translate-y-0.5 ${
                    plan.featured 
                      ? 'bg-white text-black hover:bg-slate-200' 
                      : 'bg-white/5 text-white border border-white/10 hover:bg-white/10'
                  }`}
                >
                  {user ? "Go to Dashboard" : plan.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="py-24">
        <div className="max-w-3xl mx-auto px-6 lg:px-12">
          <div className="text-center mb-16 animate-on-scroll opacity-0 translate-y-10 transition-all duration-700">
            <div className="text-xs text-[#A5B4FC] uppercase tracking-[0.2em] mb-4">FAQ</div>
            <h2 className="text-4xl lg:text-5xl font-extrabold">Frequently asked questions</h2>
          </div>

          <div className="space-y-4">
            {[
              { q: 'How is this different from ChatGPT?', a: 'Your twin only answers from your verified knowledge sources—no hallucinations, no generic answers. It learns your specific voice, decision style, and expertise boundaries through structured training, not just prompt engineering.' },
              { q: 'Can I update my twin\'s knowledge?', a: 'Yes! Add new documents, URLs, or text anytime. Your twin automatically incorporates new knowledge while maintaining version control—you can roll back to previous versions if needed.' },
              { q: 'Is my data private?', a: 'Absolutely. Your training data and knowledge sources are isolated per tenant with Row Level Security in PostgreSQL. We never use your data to train models for other users. Full export and deletion supported.' },
              { q: 'What platforms can I share to?', a: 'Share via public link, embed as a widget on your website, or integrate via API into Slack, Discord, WhatsApp, or your own application. Full white-label options available on Pro and Enterprise plans.' },
            ].map((faq, i) => (
              <div 
                key={i} 
                className="animate-on-scroll opacity-0 translate-y-10 transition-all duration-700 border-b border-white/[0.08]"
                style={{ transitionDelay: `${i * 100}ms` }}
              >
                <button 
                  className="w-full py-5 flex items-center justify-between text-left"
                  onClick={() => toggleFaq(i)}
                >
                  <span className="font-semibold pr-4">{faq.q}</span>
                  <svg 
                    className={`w-5 h-5 text-slate-400 shrink-0 transition-transform duration-300 ${activeFaq === i ? 'rotate-180' : ''}`} 
                    fill="none" 
                    stroke="currentColor" 
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                <div className={`overflow-hidden transition-all duration-300 ${activeFaq === i ? 'max-h-40 pb-5' : 'max-h-0'}`}>
                  <p className="text-slate-400 text-sm leading-relaxed">{faq.a}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-24 relative overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-[radial-gradient(circle,rgba(79,70,229,0.15)_0%,transparent_70%)] pointer-events-none" />
        <div className="max-w-4xl mx-auto px-6 lg:px-12 text-center relative">
          <h2 className="animate-on-scroll opacity-0 translate-y-10 transition-all duration-700 text-4xl lg:text-5xl font-extrabold mb-4">
            Ready to clone yourself?
          </h2>
          <p className="animate-on-scroll opacity-0 translate-y-10 transition-all duration-700 delay-100 text-lg text-slate-400 mb-8">
            Join 1,000+ creators who've already built their twins.
          </p>
          <Link 
            href={user ? "/dashboard" : "/auth/login?redirect=/onboarding"}
            className="animate-on-scroll opacity-0 translate-y-10 transition-all duration-700 delay-200 inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] text-white font-semibold rounded-xl shadow-lg shadow-indigo-500/30 hover:shadow-indigo-500/50 transition-all hover:-translate-y-0.5"
          >
            Build Your Digital Twin Free →
          </Link>
          <p className="animate-on-scroll opacity-0 translate-y-10 transition-all duration-700 delay-300 text-xs text-slate-500 mt-4">
            No credit card • 2-minute setup • Cancel anytime
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/[0.05] py-12">
        <div className="max-w-6xl mx-auto px-6 lg:px-12">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-12">
            {/* Brand */}
            <div className="col-span-2 md:col-span-1">
              <div className="flex items-center gap-2 mb-3">
                <svg viewBox="0 0 44 44" fill="none" className="w-8 h-8">
                  <path d="M22 2L40 12V32L22 42L4 32V12L22 2Z" fill="url(#footerLogoGradient)" stroke="rgba(255,255,255,0.2)" strokeWidth="1"/>
                  <circle cx="22" cy="16" r="4" fill="white" fillOpacity="0.9"/>
                  <circle cx="14" cy="26" r="3" fill="white" fillOpacity="0.7"/>
                  <circle cx="30" cy="26" r="3" fill="white" fillOpacity="0.7"/>
                  <circle cx="22" cy="32" r="2.5" fill="white" fillOpacity="0.8"/>
                  <path d="M22 20L14 23M22 20L30 23M14 29L22 30M30 29L22 30" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeOpacity="0.6"/>
                  <defs>
                    <linearGradient id="footerLogoGradient" x1="4" y1="2" x2="40" y2="42">
                      <stop stopColor="#4F46E5"/>
                      <stop offset="0.5" stopColor="#7C3AED"/>
                      <stop offset="1" stopColor="#EC4899"/>
                    </linearGradient>
                  </defs>
                </svg>
                <span className="font-bold">Digital Brains</span>
              </div>
              <p className="text-sm text-slate-400 leading-relaxed">
                Creating AI twins that actually know things—trained on your expertise, speaking with your voice.
              </p>
            </div>

            {/* Product */}
            <div>
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">Product</h4>
              <ul className="space-y-2">
                {['Features', 'Pricing', 'API', 'Integrations'].map((item) => (
                  <li key={item}>
                    <Link href="#" className="text-sm text-slate-400 hover:text-white transition-colors">{item}</Link>
                  </li>
                ))}
              </ul>
            </div>

            {/* Resources */}
            <div>
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">Resources</h4>
              <ul className="space-y-2">
                {['Documentation', 'Blog', 'Community', 'Help Center'].map((item) => (
                  <li key={item}>
                    <Link href="#" className="text-sm text-slate-400 hover:text-white transition-colors">{item}</Link>
                  </li>
                ))}
              </ul>
            </div>

            {/* Company */}
            <div>
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">Company</h4>
              <ul className="space-y-2">
                {['About', 'Careers', 'Contact', 'Privacy'].map((item) => (
                  <li key={item}>
                    <Link href="#" className="text-sm text-slate-400 hover:text-white transition-colors">{item}</Link>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Bottom */}
          <div className="flex flex-col md:flex-row items-center justify-between gap-4 pt-8 border-t border-white/[0.05]">
            <p className="text-sm text-slate-500">© 2026 Digital Brains. All rights reserved.</p>
            <div className="flex gap-3">
              {['Twitter', 'GitHub', 'Discord'].map((social) => (
                <a 
                  key={social} 
                  href="#" 
                  className="w-9 h-9 bg-white/5 rounded-lg flex items-center justify-center text-slate-400 hover:bg-[#4F46E5]/20 hover:text-white transition-all"
                >
                  <span className="text-xs font-bold">{social[0]}</span>
                </a>
              ))}
            </div>
          </div>
        </div>
      </footer>

      {/* Animation styles */}
      <style jsx>{`
        .animate-in {
          opacity: 1 !important;
          transform: translateY(0) !important;
        }
        @media (min-width: 1024px) {
          .lg\\:rotate-y-\\[-5deg\\] {
            transform: perspective(1000px) rotateY(-5deg) rotateX(2deg);
          }
          .lg\\:hover\\:rotate-y-0:hover {
            transform: perspective(1000px) rotateY(0deg) rotateX(0deg);
          }
        }
      `}</style>
    </div>
  );
}
