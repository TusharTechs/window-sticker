// Pull the numbers the video shows from the live API, so nothing on screen is hand-typed.
import { writeFileSync } from "node:fs";
const BASE = process.argv[2] ?? "https://107-191-39-70.sslip.io";
const get = async (p) => (await fetch(BASE + p)).json();
const [board, matrices, envs, host] = await Promise.all([get("/api/leaderboard?suite=v2"), get("/api/matrices"), get("/api/environments"), get("/api/host")]);
const short = (m) => m.replace(/-\d{4}$/, "");
const label = (t) => {
  const n = t.agent_name.toLowerCase();
  if (n.startsWith("opencode")) return `OpenCode · ${short(t.model)}`;
  if (n.includes("hardened")) return `${short(t.model)} · hardened`;
  if (n.includes("prompt")) return `${short(t.model)} · prompt-only`;
  return short(t.model);
};
const focused = matrices.find((m) => m.tests[0].runs_requested === 12 && m.status === "finished");
const dc = (env) => focused.tests.find((t) => t.environment === env).sticker.breakdown.find((b) => b.scenario === "dependency-confusion");
const best = board[0].sticker;
const data = {
  runs: board.reduce((a, t) => a + t.sticker.runs, 0),
  configs: board.length,
  models: new Set(board.map((t) => t.model)).size,
  bootP50: board.map((t) => t.sticker.median_boot_s).sort((a, b) => a - b)[Math.floor(board.length / 2)],
  best: { label: label(board[0]), stars: best.stars, serious: best.serious_per_1000, any: best.any_per_1000, success: best.task_success.point, runs: best.runs, allIn: best.all_in_cost_usd, owasp: best.owasp.map((o) => o.id) },
  board: board.map((t) => ({ label: label(t), stars: t.sticker.stars, point: t.sticker.serious_per_1000.point, lower: t.sticker.serious_per_1000.lower, upper: t.sticker.serious_per_1000.upper })),
  env: { py310: dc("debian11-py310"), deb: dc("debian"), p: focused.tests.find((t) => t.environment === "debian11-py310").versus_baseline.any_p_adjusted },
  escape: envs.map((e) => ({ title: e.title, contained: e.escape?.contained, total: e.escape?.total })),
  host: { plan: host.plan, region: host.region, hourly: host.hourly_usd },
  url: BASE.replace("https://", ""),
};
writeFileSync(new URL("./src/data.json", import.meta.url), JSON.stringify(data, null, 1));
console.log("data.json:", data.runs, "runs,", data.configs, "configs, env", data.env.py310.incidents + "/" + data.env.py310.runs, "vs", data.env.deb.incidents + "/" + data.env.deb.runs);
