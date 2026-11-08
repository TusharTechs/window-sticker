// Capture crisp screenshots of the live product for the deck and the video.
//   node submission/shots.mjs https://<host>
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const base = process.argv[2] ?? "https://107-191-39-70.sslip.io";
const out = new URL("./shots/", import.meta.url).pathname;
mkdirSync(out, { recursive: true });

const shots = [
  { name: "home", path: "/", wait: 2500 },
  { name: "home-replay", path: "/", scrollTo: "text=Same traps. Different agents.", wait: 9000 },
  { name: "home-findings", path: "/", scrollTo: "text=What Trap Suite v2 found", wait: 1500 },
  { name: "tour", path: "/tour", wait: 1500 },
  { name: "tour-live", path: "/tour#live", wait: 2000 },
  { name: "replay-dns", path: "/runs/run_6970f519ab05", wait: 1500 },
  { name: "replay-dns-explained", path: "/runs/run_6970f519ab05", scrollTo: "text=In plain English", wait: 1500 },
  { name: "leaderboard", path: "/leaderboard", wait: 2000 },
  { name: "heatmap", path: "/leaderboard", scrollTo: "text=Which traps catch which agents", wait: 1500 },
  { name: "environments", path: "/environments", wait: 2000 },
  { name: "methodology", path: "/methodology", wait: 1500 },
  { name: "packet", path: "/tests/test_f90ffdc425/packet", wait: 1500 },
];

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2 });
for (const s of shots) {
  const page = await ctx.newPage();
  await page.goto(base + s.path, { waitUntil: "networkidle" });
  if (s.scrollTo) {
    await page.locator(s.scrollTo).first().scrollIntoViewIfNeeded();
    await page.evaluate(() => window.scrollBy(0, -90));
  }
  await page.waitForTimeout(s.wait);
  await page.screenshot({ path: `${out}${s.name}.png` });
  await page.close();
  console.log("shot", s.name);
}
await browser.close();
