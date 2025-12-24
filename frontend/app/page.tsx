import Link from "next/link";

// Premium Landing Page - Dark Theme with Animations
export default function Home() {
  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white font-sans">
      {/* Animated Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[800px] h-[800px] bg-indigo-600/15 rounded-full blur-[120px] animate-pulse" />
        <div className="absolute bottom-0 right-1/4 w-[600px] h-[600px] bg-purple-600/15 rounded-full blur-[100px] animate-pulse" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 left-1/2 w-[400px] h-[400px] bg-pink-600/10 rounded-full blur-[80px] animate-pulse" style={{ animationDelay: '2s' }} />
      </div>

      {/* Navigation */}
      <nav className="relative z-50 flex items-center justify-between px-6 lg:px-12 py-6">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-500/30 group-hover:scale-110 transition-transform">
            <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <span className="text-xl font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
            Verified Twin
          </span>
        </Link>

        <div className="hidden md:flex items-center gap-8">
          <a href="#features" className="text-sm text-slate-400 hover:text-white transition-colors">Features</a>
          <a href="#how-it-works" className="text-sm text-slate-400 hover:text-white transition-colors">How It Works</a>
          <a href="#pricing" className="text-sm text-slate-400 hover:text-white transition-colors">Pricing</a>
          <Link href="/auth/login" className="text-sm text-slate-400 hover:text-white transition-colors">Sign In</Link>
          <Link
            href="/onboarding"
            className="px-5 py-2.5 bg-white text-black text-sm font-semibold rounded-full hover:bg-slate-200 transition-all hover:scale-105"
          >
            Get Started Free
          </Link>
        </div>

        {/* Mobile Menu Button */}
        <button className="md:hidden p-2 text-slate-400">
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      </nav>

      {/* Hero Section */}
      <section className="relative z-10 max-w-6xl mx-auto px-6 pt-16 pb-24 text-center">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 rounded-full mb-8 backdrop-blur-sm">
          <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
          <span className="text-xs font-medium text-slate-300">Trusted by 1,000+ creators</span>
        </div>

        {/* Headline */}
        <h1 className="text-5xl md:text-7xl font-black tracking-tight leading-tight mb-6">
          Create Your
          <span className="block bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
            Digital Twin
          </span>
        </h1>

        {/* Subheadline */}
        <p className="text-xl md:text-2xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
          Train an AI clone with your knowledge. Get verified answers with citations.
          <span className="text-white font-medium"> No hallucinations, just facts.</span>
        </p>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
          <Link
            href="/onboarding"
            className="group px-8 py-4 bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-bold text-lg rounded-2xl shadow-2xl shadow-indigo-500/30 hover:shadow-indigo-500/50 transition-all hover:scale-105 flex items-center gap-2"
          >
            Start Building Free
            <svg className="w-5 h-5 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
            </svg>
          </Link>
          <a
            href="#how-it-works"
            className="px-8 py-4 text-slate-300 font-semibold text-lg hover:text-white transition-colors flex items-center gap-2"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Watch Demo
          </a>
        </div>

        {/* Product Preview */}
        <div className="relative max-w-4xl mx-auto">
          <div className="absolute inset-0 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-3xl blur-xl opacity-20" />
          <div className="relative bg-slate-900/80 backdrop-blur-xl border border-white/10 rounded-3xl p-2 shadow-2xl">
            <div className="bg-[#0f0f15] rounded-2xl p-6 min-h-[400px] flex items-center justify-center">
              {/* Mock Dashboard Preview */}
              <div className="w-full max-w-3xl space-y-4">
                <div className="flex items-center gap-4 p-4 bg-white/5 rounded-xl border border-white/10">
                  <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full flex items-center justify-center text-lg font-bold">
                    JD
                  </div>
                  <div className="flex-1">
                    <p className="font-semibold">John Doe</p>
                    <p className="text-sm text-slate-400">AI/ML Expert & Startup Advisor</p>
                  </div>
                  <span className="px-3 py-1 bg-emerald-500/20 text-emerald-400 text-xs font-bold rounded-full flex items-center gap-1">
                    <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
                    Online
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  {[
                    { label: 'Conversations', value: '2,847', icon: '💬' },
                    { label: 'Accuracy', value: '98.5%', icon: '✓' },
                    { label: 'Response Time', value: '1.2s', icon: '⚡' },
                  ].map((stat, i) => (
                    <div key={i} className="p-4 bg-white/5 rounded-xl border border-white/10 text-center">
                      <p className="text-2xl font-bold text-white">{stat.value}</p>
                      <p className="text-xs text-slate-400 mt-1">{stat.label}</p>
                    </div>
                  ))}
                </div>

                <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 bg-slate-700 rounded-full flex items-center justify-center text-sm">U</div>
                    <div className="flex-1">
                      <p className="text-sm text-slate-300">What&apos;s your view on AI startups in 2025?</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3 mt-4 pl-11">
                    <div className="flex-1 p-3 bg-indigo-500/10 rounded-xl border border-indigo-500/20">
                      <p className="text-sm text-slate-200">Based on my analysis, AI startups in 2025 will focus on...</p>
                      <div className="flex items-center gap-2 mt-2">
                        <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 text-[10px] font-bold rounded">98% Confidence</span>
                        <span className="text-[10px] text-slate-500">2 sources cited</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Social Proof */}
      <section className="relative z-10 py-16 border-y border-white/5">
        <div className="max-w-6xl mx-auto px-6">
          <p className="text-center text-sm text-slate-500 mb-8">Trusted by professionals from</p>
          <div className="flex flex-wrap items-center justify-center gap-12 opacity-50">
            {['Google', 'Microsoft', 'Amazon', 'Meta', 'OpenAI'].map((company) => (
              <span key={company} className="text-xl font-bold text-slate-400">{company}</span>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="relative z-10 py-24">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center mb-16">
            <span className="text-sm font-bold text-indigo-400 uppercase tracking-widest">Features</span>
            <h2 className="text-4xl md:text-5xl font-black mt-4 mb-4">
              Your Knowledge, <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-purple-400">Supercharged</span>
            </h2>
            <p className="text-xl text-slate-400 max-w-2xl mx-auto">
              Everything you need to create, train, and deploy your AI twin
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                icon: '🔍',
                title: 'Source Citations',
                description: 'Every answer highlights exactly which document it came from. Complete transparency.',
                gradient: 'from-blue-500/20 to-cyan-500/20'
              },
              {
                icon: '📊',
                title: 'Confidence Scores',
                description: 'See real-time confidence percentages. Know when to trust your twin.',
                gradient: 'from-emerald-500/20 to-teal-500/20'
              },
              {
                icon: '🛡️',
                title: 'Human Escalation',
                description: 'When unsure, your twin flags an expert instead of guessing. Pure accuracy.',
                gradient: 'from-purple-500/20 to-pink-500/20'
              },
              {
                icon: '🧠',
                title: 'Cognitive Graph',
                description: 'Build a structured knowledge map through conversational interviews.',
                gradient: 'from-orange-500/20 to-red-500/20'
              },
              {
                icon: '🔐',
                title: 'Access Groups',
                description: 'Segment your audience. Different answers for different users.',
                gradient: 'from-indigo-500/20 to-violet-500/20'
              },
              {
                icon: '⚡',
                title: 'Actions Engine',
                description: 'Trigger workflows, send emails, and automate tasks from conversations.',
                gradient: 'from-yellow-500/20 to-orange-500/20'
              },
            ].map((feature, i) => (
              <div
                key={i}
                className="group p-6 bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl hover:bg-white/10 hover:border-white/20 transition-all duration-300"
              >
                <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${feature.gradient} flex items-center justify-center text-2xl mb-4 group-hover:scale-110 transition-transform`}>
                  {feature.icon}
                </div>
                <h3 className="text-xl font-bold text-white mb-2">{feature.title}</h3>
                <p className="text-slate-400 leading-relaxed">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="relative z-10 py-24 bg-gradient-to-b from-transparent via-indigo-950/20 to-transparent">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center mb-16">
            <span className="text-sm font-bold text-indigo-400 uppercase tracking-widest">How It Works</span>
            <h2 className="text-4xl md:text-5xl font-black mt-4">
              3 Simple Steps
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                step: '01',
                title: 'Define Your Identity',
                description: 'Create your digital persona with a name, expertise areas, and personality settings.',
                icon: '✨'
              },
              {
                step: '02',
                title: 'Add Your Knowledge',
                description: 'Upload documents, add URLs, or conduct an interview to build your knowledge base.',
                icon: '📚'
              },
              {
                step: '03',
                title: 'Launch & Share',
                description: 'Deploy your twin instantly. Share via link, embed on your website, or integrate via API.',
                icon: '🚀'
              },
            ].map((item, i) => (
              <div key={i} className="relative">
                {i < 2 && (
                  <div className="hidden md:block absolute top-16 left-full w-full h-0.5 bg-gradient-to-r from-indigo-500/50 to-transparent -translate-x-1/2" />
                )}
                <div className="text-center">
                  <div className="w-20 h-20 mx-auto bg-gradient-to-br from-indigo-600 to-purple-600 rounded-full flex items-center justify-center text-3xl shadow-xl shadow-indigo-500/30 mb-6">
                    {item.icon}
                  </div>
                  <span className="text-xs font-bold text-indigo-400 uppercase tracking-widest">Step {item.step}</span>
                  <h3 className="text-xl font-bold text-white mt-2 mb-3">{item.title}</h3>
                  <p className="text-slate-400">{item.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="relative z-10 py-24">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center mb-16">
            <span className="text-sm font-bold text-indigo-400 uppercase tracking-widest">Pricing</span>
            <h2 className="text-4xl md:text-5xl font-black mt-4 mb-4">
              Start Free, Scale When Ready
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {[
              {
                name: 'Starter',
                price: 'Free',
                description: 'Perfect for trying out',
                features: ['1 Digital Twin', '100 messages/month', 'Basic knowledge base', 'Share link'],
                cta: 'Get Started',
                featured: false
              },
              {
                name: 'Pro',
                price: '$29',
                period: '/month',
                description: 'For serious creators',
                features: ['Unlimited twins', 'Unlimited messages', 'Advanced analytics', 'Custom branding', 'API access', 'Priority support'],
                cta: 'Start Pro Trial',
                featured: true
              },
              {
                name: 'Enterprise',
                price: 'Custom',
                description: 'For teams & orgs',
                features: ['Everything in Pro', 'SSO/SAML', 'Custom integrations', 'SLA guarantee', 'Dedicated support', 'On-premise option'],
                cta: 'Contact Sales',
                featured: false
              },
            ].map((plan, i) => (
              <div
                key={i}
                className={`relative p-8 rounded-3xl border transition-all duration-300 ${plan.featured
                    ? 'bg-gradient-to-b from-indigo-600/20 to-purple-600/20 border-indigo-500/50 scale-105 shadow-2xl shadow-indigo-500/20'
                    : 'bg-white/5 border-white/10 hover:border-white/20'
                  }`}
              >
                {plan.featured && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-gradient-to-r from-indigo-500 to-purple-500 text-white text-xs font-bold rounded-full">
                    Most Popular
                  </span>
                )}
                <h3 className="text-xl font-bold text-white">{plan.name}</h3>
                <div className="mt-4 mb-2">
                  <span className="text-4xl font-black text-white">{plan.price}</span>
                  {plan.period && <span className="text-slate-400">{plan.period}</span>}
                </div>
                <p className="text-sm text-slate-400 mb-6">{plan.description}</p>
                <ul className="space-y-3 mb-8">
                  {plan.features.map((feature, j) => (
                    <li key={j} className="flex items-center gap-2 text-sm text-slate-300">
                      <svg className="w-4 h-4 text-emerald-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                      </svg>
                      {feature}
                    </li>
                  ))}
                </ul>
                <Link
                  href="/onboarding"
                  className={`block w-full py-3 text-center font-semibold rounded-xl transition-all ${plan.featured
                      ? 'bg-white text-black hover:bg-slate-200'
                      : 'bg-white/10 text-white hover:bg-white/20'
                    }`}
                >
                  {plan.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="relative z-10 py-24">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <div className="p-12 bg-gradient-to-br from-indigo-600/20 via-purple-600/20 to-pink-600/20 border border-indigo-500/30 rounded-3xl backdrop-blur-sm">
            <h2 className="text-3xl md:text-5xl font-black mb-4">
              Ready to Build Your Digital Twin?
            </h2>
            <p className="text-xl text-slate-400 mb-8">
              Join thousands of experts who scale their knowledge with AI
            </p>
            <Link
              href="/onboarding"
              className="inline-flex items-center gap-2 px-8 py-4 bg-white text-black font-bold text-lg rounded-2xl hover:bg-slate-200 transition-all hover:scale-105"
            >
              Get Started Free
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
              </svg>
            </Link>
            <p className="text-sm text-slate-500 mt-4">No credit card required</p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/10 py-12">
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <span className="font-bold text-white">Verified Twin</span>
            </div>
            <div className="flex items-center gap-6 text-sm text-slate-400">
              <a href="#" className="hover:text-white transition-colors">Privacy</a>
              <a href="#" className="hover:text-white transition-colors">Terms</a>
              <a href="#" className="hover:text-white transition-colors">Contact</a>
            </div>
            <p className="text-sm text-slate-500">© 2025 Verified Twin. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
