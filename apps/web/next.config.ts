import type { NextConfig } from "next";

// Cache Components stay off: showcase pages use classic ISR (export const revalidate),
// see docs/decisions/0010.
const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // The dev server only serves its scripts to localhost by default; without this, pages
  // opened on 127.0.0.1 never hydrate (no sign-in link, no charts).
  allowedDevOrigins: ["127.0.0.1"],
};

export default nextConfig;
