import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Spotify album art is fetched straight from the CDN; keep it unoptimized so no
  // remote-pattern config is needed.
  images: { unoptimized: true },
};

export default nextConfig;
