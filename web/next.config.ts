import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  // The repo root has its own package.json (the Python pipeline's), so Next.js
  // would otherwise guess the repo root as the workspace and resolve modules
  // from there -- which is how the site came to depend on a package it never
  // declared. Pin it to this folder so web/ is self-contained.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
