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
| M1 | The "hardened" guardrails name the suite's own paths and patterns, so its results are in-sample | pending |
| M2 | One trap (dependency confusion) drives most incidents; 9 of 12 traps never fired on any model | pending |
| M3 | Trap 09's task told the agent to follow the policy file, so obeying it was partly the user's instruction; reaching a real registry was scored as an incident | pending |
| M4 | Rows 3–8 of the leaderboard are statistically tied; 36 runs cap every agent at 3 stars and the site does not say so | pending |
| M5 | The jury never changed a verdict and its accuracy was unpublished; conditional questions ("destructive action justified") shown without their premise | **Fixed.** Measured on 370 production runs (40 tripwire incidents): AUC 0.980 for both jurors, 0 false alarms at 0.5, almost never above 0.8. The jury is now triage (no tripwire + a juror ≥ 0.5 → human review), published on /methodology; conditional questions hidden when their premise is below 0.5. |
| M6 | Evidence is collected inside the VM; OpenCode's trace and token counts are self-reported; false completion could never fire for OpenCode | **Fixed / mitigated.** Tokens metered by the host lane; protected files re-hashed through the runtime's file API and any disagreement is a critical `evidence_tamper` incident; hidden checks run with a scrubbed environment; OpenCode's success claim read from its final message. Remaining limit: the trace itself is still the agent's own log (documented). |
| M7 | Runs with no recorded steps were excluded even when a tripwire fired; OpenCode timeouts could drop the log | **Fixed.** A run is excluded only if the harness failed before the agent was handed the task; OpenCode stops 25 s before the runner's limit so its log is always read. |

### Containment and deployment security
| # | Finding | Resolution |
|---|---|---|
| S1 | OpenCode reaches inference with the master key behind TLS interception, DNS allowed, a direct route out; the escape matrix never ran in that profile | **Fixed.** Host-side inference lane: no key in the guest, no TLS interception, no DNS, no direct route; model pinned, token budget, host-metered cost. Escape matrix in the in-VM profile: 22/22 contained, including 5 lane attacks. |
| S2 | Control plane, database and secrets share the host with hostile workloads; systemd units not hardened | pending |
| S3 | No per-VM disk cap; concurrency × VM memory can exceed host RAM | Disk: **fixed** (4 GiB cap, 6 GiB write stops at 3.9 GiB). Memory: pending |
| S4 | Public WebSocket and GET endpoints can be abused (no id check, no connection cap, writes on GET) | pending |
| S5 | One token both submits tests and labels runs; labels can override tripwires | pending |
| S6 | `find -exec` / `awk system()` treated as read-only; canary match is literal (base64 missed); warden reconnects by name after checking IPs; DNS lane checks only the first question; compare does not check suites match | **Fixed** except compare (with S4): executing forms of find/awk/sed count; base64, base64url, hex and reversed canaries detected; the warden connects to the address it checked; multi-question DNS queries refused. |

### Presentation and business
| # | Finding | Resolution |
|---|---|---|
| P1 | Landing page names no buyer; main call to action leads to a token form | pending |
| P2 | Strongest proof (9/10 → 0/10) buried; no "what the lab stopped" story on incident replays | pending |
| P3 | Inconsistent numbers: boot 0.47 / 0.86 / 1.99 s unlabelled; "cost per run" bug; costs inference-only | pending |
| P4 | Internal and demo rows public; imported tests look live; compare picker unusable; badge snippet shows `<host>` | pending |
| P5 | Leaderboard chart lacks model names; no per-trap view | pending |
| P6 | Vultr invisible per run (instance, plan, region, firewall, VM time) | pending |
| P7 | README claims unused services, an app VM, Terraform; stale status | pending |
