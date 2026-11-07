import type { NextConfig } from "next";

// Local development runs the control plane on 8765; production sets WSK_API_ORIGIN.
const API = process.env.WSK_API_ORIGIN ?? "http://127.0.0.1:8765";
const dev = process.env.NODE_ENV !== "production";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  env: {
    // Rewrites do not carry WebSockets, so in development the browser connects directly.
    NEXT_PUBLIC_WS_ORIGIN: process.env.NEXT_PUBLIC_WS_ORIGIN ?? (dev ? API.replace(/^http/, "ws") : ""),
  },
  async rewrites() {
    // In production Caddy routes /api to the control plane; this keeps dev identical.
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};

export default nextConfig;
