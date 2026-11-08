# Independent review, round 1 (2026-11-08)

Four reviewers read the live site, the public API, the code and the docs (read-only), each
in a judge role: Vultr developer relations, Vultr product leadership, hackathon pitch and
business, and an adversarial sandbox-security engineer.

| Reviewer | Application of Technology | Presentation | Business Value | Originality |
|---|---|---|---|---|
| Developer relations | 8 | 7 | 7 | 8 |
| Product leadership | 9 | 7 | 6 | 8 |
| Pitch and business | 9 | 6 | 5 | 8 |
| Security engineer | 8 | 7 | 6 | 8 |

Verified by the security reviewer against code and data: exact-interval stars and the
30-run minimum; Fisher p = 0.000119 for the 10 v 10 A/B; every README leaderboard row; the
OpenCode network claim (36 events in 36 runs, all the allowed inference lookup); deny-all
policy, teardown in `finally` with label verification, `max_duration`, per-run HMAC canaries;
fail-closed constant-time auth, API bound to loopback, Postgres local only.

## Findings and resolutions

Status is updated as each item is fixed and verified.

### Method and credibility
| # | Finding | Resolution |
|---|---|---|
| M1 | The "hardened" guardrails name the suite's own paths and patterns, so its results are in-sample | **Confirmed and measured.** Suite v2 adds four held-out traps written after the guardrails were frozen. Hardened: 0/72 serious incidents on the original traps, 5/24 on the held-out ones, the same as the prompt-only agent. The leaderboard labels the configuration "hardened (in-sample guardrails)" and the README leads with this result. |
| M2 | One trap (dependency confusion) drives most incidents; 9 of 12 traps never fired on any model | **Improved, still open.** 8 of 16 v2 traps fire; the held-out traps carry 39 of 48 incidents. The heatmap on the leaderboard shows this openly. Harder variants of the silent traps are the next suite's work. |
| M3 | Trap 09's task told the agent to follow the policy file, so obeying it was partly the user's instruction; reaching a real registry was scored as an incident | **Fixed in Suite v2.** The instruction is gone and pypi.org is ignored; deepseek's fall rate on this trap dropped from 9/10 to 1/3, so the old headline A/B overstated the effect. |
| M4 | Rows 3–8 of the leaderboard are statistically tied; 36 runs cap every agent at 3 stars and the site does not say so | **Fixed.** The leaderboard groups rows that Fisher's exact test cannot separate and says so; every sticker states the most stars its run count can earn and how many clean runs the next star needs; v2 leaderboard tests use 48–96 runs. |
| M5 | The jury never changed a verdict and its accuracy was unpublished; conditional questions ("destructive action justified") shown without their premise | **Fixed.** Measured on 370 production runs (40 tripwire incidents): AUC 0.980 for both jurors, 0 false alarms at 0.5, almost never above 0.8. The jury is now triage (no tripwire + a juror ≥ 0.5 → human review), published on /methodology; conditional questions hidden when their premise is below 0.5. |
| M6 | Evidence is collected inside the VM; OpenCode's trace and token counts are self-reported; false completion could never fire for OpenCode | **Fixed / mitigated.** Tokens metered by the host lane; protected files re-hashed through the runtime's file API and any disagreement is a critical `evidence_tamper` incident; hidden checks run with a scrubbed environment; OpenCode's success claim read from its final message. Remaining limit: the trace itself is still the agent's own log (documented). |
| M7 | Runs with no recorded steps were excluded even when a tripwire fired; OpenCode timeouts could drop the log | **Fixed.** A run is excluded only if the harness failed before the agent was handed the task; OpenCode stops 25 s before the runner's limit so its log is always read. |

### Containment and deployment security
| # | Finding | Resolution |
|---|---|---|
| S1 | OpenCode reaches inference with the master key behind TLS interception, DNS allowed, a direct route out; the escape matrix never ran in that profile | **Fixed.** Host-side inference lane: no key in the guest, no TLS interception, no DNS, no direct route; model pinned, token budget, host-metered cost. Escape matrix in the in-VM profile: 22/22 contained, including 5 lane attacks. |
| S2 | Control plane, database and secrets share the host with hostile workloads; systemd units not hardened | **Mitigated.** Units hardened (API and web: read-only system and home, private devices and /tmp, no capabilities, no new privileges, memory caps; worker: no new privileges, read-only system, 7 GiB cap that also bounds every microVM). The host holds no account-level Vultr API key. The escape matrix shows the database, API and SSH ports refused from every guest. Remaining: moving the control plane to its own VM (planned). |
| S3 | No per-VM disk cap; concurrency × VM memory can exceed host RAM | **Fixed.** 4 GiB disk cap per microVM; the worker caps concurrent microVMs to (free memory − 1 GiB) ÷ VM size. |
| S4 | Public WebSocket and GET endpoints can be abused (no id check, no connection cap, writes on GET) | **Fixed.** Per-client rate limit on /api; the event socket rejects unknown tests, is capped per test and overall, and closes when a finished test is drained; GET endpoints never write. |
| S5 | One token both submits tests and labels runs; labels can override tripwires | **Fixed.** Separate submit and label tokens (the admin token can do both; CI gets only the submit token); every label is shown with its labeller and time on the run. |
| S6 | `find -exec` / `awk system()` treated as read-only; canary match is literal (base64 missed); warden reconnects by name after checking IPs; DNS lane checks only the first question; compare does not check suites match | **Fixed.** Compare refuses tests with different suites or trap sets; executing forms of find/awk/sed count; base64, base64url, hex and reversed canaries detected; the warden connects to the address it checked; multi-question DNS queries refused. |

### Presentation and business
| # | Finding | Resolution |
|---|---|---|
| P1 | Landing page names no buyer; main call to action leads to a token form | **Fixed.** Opening line names the buyer; a "Who it is for" strip (platform and security teams, agent vendors, CI); the main call to action opens a real finished crash test. |
| P2 | Strongest proof (9/10 → 0/10) buried; no "what the lab stopped" story on incident replays | **Fixed.** The landing page shows best versus worst agent on the same traps and the plain-English meaning of the stars; every incident replay opens with "What the lab stopped". The 9/10 A/B is no longer a headline because Suite v2 showed it overstated the effect (M3). |
| P3 | Inconsistent numbers: boot 0.47 / 0.86 / 1.99 s unlabelled; "cost per run" bug; costs inference-only | **Fixed.** Boot time labelled (p50, cached image); stickers show cost per 1,000 safe tasks and an all-in test cost that adds the VX1 host time. |
| P4 | Internal and demo rows public; imported tests look live; compare picker unusable; badge snippet shows `<host>` | **Fixed.** Smoke, CI and calibration tests hidden by default (one click shows them, tagged); imported batches tagged; compare pickers show model, guardrails, suite, traps, runs and date, with suggested pairs and a clear refusal for incomparable tests; the badge snippet uses the real host. |
| P5 | Leaderboard chart lacks model names; no per-trap view | **Fixed.** Every chart point is labelled; a model by trap heatmap marks the held-out traps; a Suite v1/v2 toggle. |
| P6 | Vultr invisible per run (instance, plan, region, firewall, VM time) | **Fixed.** Every run replay shows the Vultr plan, region, microVM, boot, agent and teardown times and the agent and jury cost; the landing page shows the host and its hourly price. |
| P7 | README claims unused services, an app VM, Terraform; stale status | **Fixed.** Services table lists only what runs (one VX1 host, chat models, System One, firewall groups, API v2); the app VM, fleet and vector store are under Roadmap; v2 leaderboard, held-out result and current test count. |
