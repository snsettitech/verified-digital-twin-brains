import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Disable React Compiler to avoid lint errors from experimental rules
  reactCompiler: false,
  // Ensure we don't force Turbopack for production builds if it's causing issues
  transpilePackages: ["@/lib", "@/components", "@/contexts"],
};

export default nextConfig;
