import type { NextConfig } from "next";

const backendUrl = process.env.ACIOS_BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [
      {
        source: "/api/system/:path*",
        destination: `${backendUrl}/api/system/:path*`,
      },
      {
        source: "/api/settings",
        destination: `${backendUrl}/api/settings`,
      },
      {
        source: "/api/verification/:path*",
        destination: `${backendUrl}/api/verification/:path*`,
      },
      {
        source: "/api/drafts/:path*",
        destination: `${backendUrl}/api/drafts/:path*`,
      },
      {
        source: "/api/queue/:path*",
        destination: `${backendUrl}/api/queue/:path*`,
      },
      {
        source: "/api/mailbox/:path*",
        destination: `${backendUrl}/api/mailbox/:path*`,
      },
      {
        source: "/api/resume/:path*",
        destination: `${backendUrl}/api/resume/:path*`,
      },
      {
        source: "/api/database/:path*",
        destination: `${backendUrl}/api/database/:path*`,
      },
    ];
  },
};

export default nextConfig;
