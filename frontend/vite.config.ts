import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "HAIUN_");
  return {
    plugins: [react()],
    server: {
      host: env.HAIUN_FRONTEND_HOST || "0.0.0.0",
      port: Number(env.HAIUN_FRONTEND_PORT || 5173),
      proxy: { "/api": "http://127.0.0.1:8765" },
    },
    test: {
      include: ["src/test/**/*.{test,spec}.{ts,tsx}"],
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts",
      css: true,
      globals: true,
    },
  };
});
