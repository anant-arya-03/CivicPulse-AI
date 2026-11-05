import type { NextConfig } from "next";

// The FastAPI backend. Server-side only: this value is never sent to the browser.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  experimental: {
    // Next.js keeps a copy of every request body while routing rewrites, and by default cuts it
    // off at 10 MB. Photos may be up to 10 MB (MAX_UPLOAD_MB) plus form-data overhead, so allow
    // a little more. Larger requests are refused by the backend (or the browser, before upload).
    proxyClientMaxBodySize: "12mb",
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // Security headers for every page. The Content-Security-Policy only sets rules that can't
  // break Next.js's own inline scripts or the map tiles: no framing (clickjacking), no plugins,
  // and forms and <base> may only point back to this site.
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // Camera: photo capture on phones. Location: "Use my current location".
          { key: "Permissions-Policy", value: "camera=(self), geolocation=(self), microphone=()" },
          {
            key: "Content-Security-Policy",
            value: "frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'",
          },
        ],
      },
    ];
  },
  // The browser calls /api/v1/... on this same origin, and Next.js forwards the request
  // to FastAPI. Same origin means session cookies just work and no CORS setup is needed.
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${BACKEND_URL}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
