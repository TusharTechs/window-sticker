// Record crisp footage of the live product for the demo video.
//   node record.mjs <clip|all> [https://host]
// Uses Chrome's own screencast (JPEG frames at near-lossless quality) instead of the default
// low-bitrate recorder, then assembles constant-frame-rate H.264 clips with ffmpeg.
import { chromium } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const OUT = join(here, "public", "footage");
const BASE = process.argv[3] ?? "https://107-191-39-70.sslip.io";
// A 1440x810 viewport at 4/3 pixel density fills 1920x1080 with larger, crisper text.
const VW = 1440;
const VH = 810;
const W = 1920;
const H = 1080;
mkdirSync(OUT, { recursive: true });

// A visible cursor: Chrome's screencast does not paint the real pointer.
const CURSOR = `
(() => {
  if (window.__wskCursor) return; window.__wskCursor = 1;
  const c = document.createElement('div');
  c.style.cssText = 'position:fixed;left:0;top:0;width:28px;height:28px;z-index:2147483647;pointer-events:none;transition:transform 60ms linear;transform:translate(-100px,-100px)';
  c.innerHTML = '<svg width="28" height="28" viewBox="0 0 28 28"><path d="M4 2 L4 22 L9.5 17 L13 25 L16.5 23.5 L13 15.8 L20.5 15.8 Z" fill="#14161a" stroke="#fffdf8" stroke-width="2" stroke-linejoin="round"/></svg>';
  const ring = document.createElement('div');
  ring.style.cssText = 'position:fixed;left:0;top:0;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;border:3px solid #ffc400;z-index:2147483646;pointer-events:none;opacity:0;transform:scale(.4)';
  const add = () => { document.body.appendChild(ring); document.body.appendChild(c); };
  if (document.body) add(); else addEventListener('DOMContentLoaded', add);
  addEventListener('mousemove', e => { c.style.transform = 'translate(' + (e.clientX-4) + 'px,' + (e.clientY-2) + 'px)'; ring.style.left = e.clientX + 'px'; ring.style.top = e.clientY + 'px'; }, true);
  addEventListener('mousedown', () => { ring.animate([{opacity:.9, transform:'scale(.4)'},{opacity:0, transform:'scale(1.4)'}], {duration: 520, easing: 'ease-out'}); }, true);
})();`;

async function record(name, fn) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: VW, height: VH }, deviceScaleFactor: W / VW });
  await ctx.addInitScript(CURSOR);
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  // Frames go straight to disk: a minute of 1080p frames is too much to hold in memory.
  const dir = join(OUT, `.${name}`);
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
  const frames = [];
  cdp.on("Page.screencastFrame", async (f) => {
    const file = join(dir, `${String(frames.length).padStart(6, "0")}.jpg`);
    frames.push({ file, t: f.metadata.timestamp });
    writeFileSync(file, Buffer.from(f.data, "base64"));
    await cdp.send("Page.screencastFrameAck", { sessionId: f.sessionId }).catch(() => {});
  });
  await page.goto("about:blank");
  await cdp.send("Page.startScreencast", { format: "jpeg", quality: 95, maxWidth: W, maxHeight: H, everyNthFrame: 1 });
  try {
    await fn(page);
  } finally {
    await page.waitForTimeout(400);
    await cdp.send("Page.stopScreencast").catch(() => {});
    await browser.close();
  }
  // Frames arrive only when the page repaints; hold each one until the next (variable frame
  // durations), then resample to a constant 30 fps.
  const first = frames.findIndex((f) => f.t > 0);
  const kept = frames.slice(first);
  const list = [];
  kept.forEach((f, i) => {
    const next = kept[i + 1]?.t ?? f.t + 0.5;
    list.push(`file '${f.file}'\nduration ${Math.max(1 / 60, next - f.t).toFixed(4)}`);
  });
  list.push(`file '${kept[kept.length - 1].file}'`);
  writeFileSync(join(dir, "list.txt"), list.join("\n"));
  const mp4 = join(OUT, `${name}.mp4`);
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", join(dir, "list.txt"), "-vf", `fps=30,scale=${W}:${H}:flags=lanczos,format=yuv420p`, "-c:v", "libx264", "-preset", "slow", "-crf", "14", mp4]);
  rmSync(dir, { recursive: true, force: true });
  const dur = execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4]).toString().trim();
  console.log(`${name}: ${kept.length} frames, ${Number(dur).toFixed(1)} s -> ${mp4}`);
}

const glide = async (page, x, y, steps = 28) => page.mouse.move(x, y, { steps });
const smoothScroll = async (page, dy, ms = 1800) =>
  page.evaluate(
    ([dy, ms]) =>
      new Promise((res) => {
        const start = scrollY;
        const t0 = performance.now();
        const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
        const step = (now) => {
          const k = Math.min(1, (now - t0) / ms);
          scrollTo(0, start + dy * ease(k));
          k < 1 ? requestAnimationFrame(step) : res();
        };
        requestAnimationFrame(step);
      }),
    [dy, ms],
  );
const scrollToText = async (page, text, offset = 110, ms = 1600) => {
  const y = await page.locator(`text=${text}`).first().evaluate((el) => el.getBoundingClientRect().top + scrollY);
  const cur = await page.evaluate(() => scrollY);
  await smoothScroll(page, y - offset - cur, ms);
};

const CLIPS = {
  // The landing page: hero, then the replay band playing.
  async landing(page) {
    await page.goto(BASE + "/", { waitUntil: "networkidle" });
    await glide(page, 900, 390, 20);
    await page.waitForTimeout(2600);
    await glide(page, 1012, 315, 30);
    await page.waitForTimeout(1200);
    await scrollToText(page, "Same traps. Different agents.", 70, 2200);
    await page.waitForTimeout(10500);
    await glide(page, 570, 450, 30);
    await page.mouse.click(570, 450).catch(() => {});
    await page.waitForTimeout(800);
  },
  // A judge starts a live crash test from the tour and watches it land.
  async live(page) {
    await page.goto(BASE + "/tour#live", { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    const sel = page.locator("select").first();
    const env = page.locator("select").nth(1);
    const sb = await sel.boundingBox();
    await glide(page, sb.x + sb.width / 2, sb.y + sb.height / 2);
    await page.mouse.down(); await page.mouse.up();
    await sel.selectOption("minimax-m3.1-flash");
    await page.waitForTimeout(700);
    const eb = await env.boundingBox();
    await glide(page, eb.x + eb.width / 2, eb.y + eb.height / 2);
    await page.mouse.down(); await page.mouse.up();
    await env.selectOption("debian11-py310");
    await page.waitForTimeout(700);
    const none = page.getByRole("button", { name: "No guardrails" });
    const nb = await none.boundingBox();
    await glide(page, nb.x + nb.width / 2, nb.y + nb.height / 2);
    await none.click();
    await page.waitForTimeout(600);
    const start = page.getByRole("button", { name: "Start a live crash test" });
    const stb = await start.boundingBox();
    await glide(page, stb.x + stb.width / 2, stb.y + stb.height / 2, 36);
    await page.waitForTimeout(300);
    await start.click();
    await page.waitForTimeout(900);
    // Keep the demo panel framed while the runs land.
    const top = await page.locator("#live").evaluate((el) => el.getBoundingClientRect().top + scrollY);
    const cur = await page.evaluate(() => scrollY);
    await smoothScroll(page, top + 150 - cur, 1200);
    await glide(page, 1035, 570, 30);
    // Wait for every run to land (or ten minutes at most).
    await page.getByText("Open the full test").waitFor({ timeout: 600_000 });
    await page.waitForTimeout(3500);
  },
  // The containment moment: a DNS key leak, replayed.
  async replay(page) {
    await page.goto(BASE + "/runs/run_6970f519ab05", { waitUntil: "networkidle" });
    await glide(page, 720, 225, 20);
    await page.waitForTimeout(2500);
    await glide(page, 1050, 420, 30);
    await page.waitForTimeout(3000);
    await glide(page, 525, 420, 40);
    await page.waitForTimeout(3500);
    await smoothScroll(page, 560, 2200);
    await glide(page, 1065, 285, 30);
    await page.waitForTimeout(3000);
    await smoothScroll(page, 700, 2400);
    await page.waitForTimeout(2500);
  },
  // Results: the leaderboard and the trap heatmap.
  async leaderboard(page) {
    await page.goto(BASE + "/leaderboard", { waitUntil: "networkidle" });
    await page.waitForTimeout(3500);
    await glide(page, 975, 390, 30);
    await page.waitForTimeout(2000);
    await scrollToText(page, "Which traps catch which agents", 90, 2400);
    await page.waitForTimeout(3500);
  },
  // Environments: same agent, different machines.
  async environments(page) {
    await page.goto(BASE + "/environments", { waitUntil: "networkidle" });
    await page.waitForTimeout(3000);
    await glide(page, 450, 390, 30);
    await page.waitForTimeout(2500);
    await smoothScroll(page, 620, 2400);
    await page.waitForTimeout(3000);
  },
  // The security-review packet.
  async packet(page) {
    await page.goto(BASE + "/tests/test_f90ffdc425/packet", { waitUntil: "networkidle" });
    await page.waitForTimeout(2200);
    await smoothScroll(page, 700, 2600);
    await page.waitForTimeout(2200);
  },
};

const which = process.argv[2] ?? "all";
for (const [name, fn] of Object.entries(CLIPS)) {
  if (which === "all" || which === name) await record(name, fn);
}
