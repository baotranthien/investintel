import type { NextConfig } from "next";

const defaultBackendUrl =
  process.env.NODE_ENV === "production"
    ? "https://investintel-api.onrender.com"
    : "http://127.0.0.1:8000";

const backendUrl =
  process.env.INTERNAL_BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  defaultBackendUrl;

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl.replace(/\/$/, "")}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
