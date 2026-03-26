/** @type {import('next').NextConfig} */
const nextConfig = {
  // output: "standalone" нужен только для Docker-деплоя.
  // Для Vercel — убираем (Vercel сам управляет билдом).
  reactStrictMode: true,
};

module.exports = nextConfig;
