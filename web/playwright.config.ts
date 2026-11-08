import { defineConfig, devices } from "@playwright/test";

/**
 * Cross-browser and cross-device checks of the product, run against a deployment:
 *   WSK_E2E_URL=https://<host> pnpm e2e
 * Every page must render without errors, show its main content and never scroll sideways,
 * in Chromium, Firefox and WebKit (Safari's engine), on desktop and on phones.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  retries: 1,
  reporter: [["list"], ["json", { outputFile: "e2e-results.json" }]],
  use: {
    baseURL: process.env.WSK_E2E_URL ?? "http://localhost:3000",
    trace: "off",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
    { name: "mobile-chrome", use: { ...devices["Pixel 7"] } },
    { name: "mobile-safari", use: { ...devices["iPhone 14"] } },
  ],
});
