import type { NextConfig } from "next";

// Cache Components stay off: showcase pages use classic ISR (export const revalidate),
// see docs/decisions/0010.
const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
};

export default nextConfig;
