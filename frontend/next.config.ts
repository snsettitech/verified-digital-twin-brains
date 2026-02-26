import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      { source: '/onboarding/v2', destination: '/onboarding', permanent: true },
    ];
  },
  // Environment variables that should be available at build time
  env: {
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://jvtffdbuwyhmcynauety.supabase.co',
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp2dGZmZGJ1d3lobWN5bmF1ZXR5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjYwMTY1MzksImV4cCI6MjA4MTU5MjUzOX0.tRpBHBhL2GM9s6sSncrVrNnmtwxrzED01SzwjKRb37E',
    NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL || 'https://verified-digital-twin-brains.onrender.com',
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'https://verified-digital-twin-brains.onrender.com',
    NEXT_PUBLIC_FRONTEND_URL: process.env.NEXT_PUBLIC_FRONTEND_URL || 'https://digitalbrains.vercel.app',
  },
  // Output as static for optimal Vercel deployment
  output: 'standalone',
};

export default nextConfig;
