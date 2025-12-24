import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Disable React Compiler to avoid lint errors from experimental rules
  reactCompiler: false,
};

export default nextConfig;
