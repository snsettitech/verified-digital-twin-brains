import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Turbopack is now default in Next.js 16, no config needed
  experimental: {
    // Disable React Compiler to avoid lint errors from experimental rules
    reactCompiler: false,
  },
};

export default nextConfig;
