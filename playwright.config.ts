import { defineConfig, devices } from "@playwright/test";

const backendPort = 8000;
const frontendPort = 3000;

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: {
    timeout: 15_000,
  },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
      cwd: "./backend",
      url: `http://127.0.0.1:${backendPort}/api/v1/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        DATABASE_URL: "sqlite:///./e2e/playwright.db",
        STORAGE_DIR: "./e2e/storage",
      },
    },
    {
      command: "npm run dev -- --port 3000",
      cwd: "./frontend",
      url: `http://127.0.0.1:${frontendPort}`,
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
      env: {
        NEXT_PUBLIC_API_BASE_URL: `http://127.0.0.1:${backendPort}/api/v1`,
      },
    },
  ],
});
