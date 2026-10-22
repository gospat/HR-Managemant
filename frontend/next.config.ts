import type { NextConfig } from "next";
const backend = process.env.HR_BACKEND_URL || "http://127.0.0.1:8000";
const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // Django endpoints require their trailing slash; preserve it through the proxy.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return {
      beforeFiles: [],
      afterFiles: [],
      fallback:
        process.env.HR_DISABLE_BACKEND_PROXY === "1"
          ? []
          : [
              { source: "/:path*/", destination: `${backend}/:path*/` },
              { source: "/:path*", destination: `${backend}/:path*` },
            ],
    };
  },
};
export default config;
