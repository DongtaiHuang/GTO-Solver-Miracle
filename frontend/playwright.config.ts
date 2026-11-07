import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e", timeout: 90000, workers: 1,
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure" },
  webServer: [
    { command: `"${process.env.PYTHON ?? "python"}" -m uvicorn poker_lab.api:app --app-dir ../backend/src --host 127.0.0.1 --port 8000`,
      url: "http://127.0.0.1:8000/health", reuseExistingServer: !process.env.CI },
    { command: "npm run start", url: "http://localhost:3000", reuseExistingServer: !process.env.CI },
  ],
});
