import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  experimental: {
    // LLM routes can exceed the default 30s rewrite proxy timeout.
    proxyTimeout: 120_000
  },
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`
      }
    ];
  }
};

export default nextConfig;
