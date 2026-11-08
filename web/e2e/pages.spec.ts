import { expect, test } from "@playwright/test";

const PAGES: { path: string; heading: RegExp }[] = [
  { path: "/", heading: /crash-test rating/i },
  { path: "/tour", heading: /step by step/i },
  { path: "/leaderboard", heading: /safety per dollar/i },
  { path: "/environments", heading: /different machines/i },
  { path: "/suite", heading: /trap suite/i },
  { path: "/methodology", heading: /methodology/i },
  { path: "/tests", heading: /crash tests/i },
  { path: "/compare", heading: /compare two tests/i },
];

for (const { path, heading } of PAGES) {
  test(`${path} renders cleanly`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => {
      if (m.type() === "error" && !/favicon|Failed to load resource/i.test(m.text())) errors.push(m.text());
    });
    const res = await page.goto(path, { waitUntil: "networkidle" });
    expect(res?.status(), "HTTP status").toBeLessThan(400);
    await expect(page.getByRole("heading", { level: 1 }).first()).toContainText(heading);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, "page scrolls sideways").toBeLessThanOrEqual(1);
    expect(errors, "console or page errors").toEqual([]);
  });
}

test("the brand mark and navigation are present", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Window Sticker home" })).toBeVisible();
  await expect(page.locator('link[rel="icon"]').first()).toHaveAttribute("href", /icon/);
});

test("the crash-test replay plays to the end", async ({ page }) => {
  await page.goto("/");
  const tabs = page.getByRole("tablist", { name: /crash test to replay/i });
  await tabs.scrollIntoViewIfNeeded();
  await expect(page.getByRole("button", { name: "Replay" })).toBeVisible({ timeout: 20_000 });
});

test("an incident replay explains itself", async ({ page, request }) => {
  const board = await (await request.get("/api/leaderboard?suite=v2")).json();
  const worst = board[board.length - 1];
  const runs = await (await request.get(`/api/tests/${worst.id}/runs`)).json();
  const incident = runs.find((r: { incident: boolean }) => r.incident);
  await page.goto(`/runs/${incident.id}`);
  await expect(page.getByRole("heading", { name: "What the lab stopped" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "In plain English" })).toBeVisible();
});

test("the live demo form is ready (without starting a test)", async ({ page }) => {
  await page.goto("/tour#live");
  await expect(page.getByRole("button", { name: "Start a live crash test" })).toBeVisible();
  await expect(page.getByText("Machine (microVM image)")).toBeVisible();
});
