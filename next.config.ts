import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  outputFileTracingRoot: process.cwd(),
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
