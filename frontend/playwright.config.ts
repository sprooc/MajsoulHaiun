import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  retries: 0,
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:8765",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "../scripts/start.sh",
    url: "http://127.0.0.1:8765/api/health",
    reuseExistingServer: true,
    timeout: 120_000,
    env: {
      HAIUN_HOST: "127.0.0.1",
      HAIUN_PORT: "8765",
      HAIUN_OPEN_BROWSER: "0",
      HAIUN_DATA_DIR: "/tmp/haiun-playwright-data",
    },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
