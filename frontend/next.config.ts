import type { NextConfig } from "next";
import path from "path";
import { fileURLToPath } from "url";

const configDir = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Monorepo-style layout: repo root + frontend/ each have lockfiles; trace from frontend.
  outputFileTracingRoot: configDir,
  experimental: {
    // LLM routes can exceed the default 30s rewrite proxy timeout.
    proxyTimeout: 120_000
  },
  async rewrites() {
    // Project API calls use app/api/v1/[...path]/route.ts so session cookies are
    // forwarded as X-Session-Token. Keep rewrite disabled to avoid bypassing it.
    return [];
  }
};

export default nextConfig;
