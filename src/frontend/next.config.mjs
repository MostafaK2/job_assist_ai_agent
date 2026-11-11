/** @type {import('next').NextConfig} */

// Security headers sent with every page (see your report's security section).
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },          // no MIME-type guessing
  { key: "X-Frame-Options", value: "DENY" },                     // can't be embedded (clickjacking)
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

// Where the Python backend runs. Server-side only: the browser never sees this address.
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig = {
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
  images: {
    // Google profile photos (shown in the account menu after sign-in).
    remotePatterns: [{ protocol: "https", hostname: "lh3.googleusercontent.com" }],
  },
  
  // The browser calls /api/... on this site, and Next.js forwards it to the backend.
  // Same origin = login cookies will just work later, and no CORS setup is needed.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
