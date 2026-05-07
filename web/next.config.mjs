/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack(config) {
    // Avoid a Webpack ConcatenationScope JSON.parse failure in production builds.
    config.optimization.concatenateModules = false;
    return config;
  },
};

export default nextConfig;
