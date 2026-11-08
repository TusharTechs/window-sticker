# Window Sticker

**The crash-test rating for AI agents.**

Before you buy a car, the window sticker tells you how it does in a crash and what it
costs to run. Before you give an AI agent your codebase, you get a demo video.

Window Sticker runs an agent many times, each run in its own throwaway microVM on
[Vultr](https://www.vultr.com), against a published suite of traps. It produces a
sticker with:

- a **safety rating** (stars), taken from the upper bound of an exact 95% confidence interval;
- **serious incidents per 1,000 runs**, with that interval;
- **task success rate**;
- **cost per safe, successful task**, from real token counts and Vultr's published prices.

Everything on a sticker is measured from real runs. Every number carries its sample size.

> Built for the lablab.ai **Vultr: Agent Rush** hackathon, Challenge 1 *Blast Radius Zero*.

**Live:** https://107-191-39-70.sslip.io (served from the Vultr VX1 sandbox host itself)

## Results (real runs on Vultr)

### Trap Suite v2 leaderboard

16 traps, 48 or 96 real runs per configuration, every run in its own microVM on the Vultr VX1
host. Ranked by the worst plausible serious-incident rate, then by cost per safe success.

| Agent | Model | Rating | Serious / 1,000 (95% CI) | Safe success | $ / safe success | Runs |
|---|---|---|---|---|---|---|
| **OpenCode 1.19.5, inside the microVM** | `deepseek-v4.1-flash-1017` | ★★★☆☆ | 10 (0–57) | 99% | $0.0082 | 96 |
| Reference agent, no guardrails | `mimo-v2.6-pro` | ★★☆☆☆ | 21 (1–111) | 98% | $0.0050 | 48 |
| Reference agent, prompt guardrail only | `deepseek-v4.1-flash-1017` | ★★☆☆☆ | 52 (17–117) | 93% | $0.0056 | 96 |
| Reference agent, hardened | `deepseek-v4.1-flash-1017` | ★★☆☆☆ | 52 (17–117) | 94% | $0.0060 | 96 |
| Reference agent, no guardrails | `qwen3.8-27b` | ★★☆☆☆ | 42 (5–143) | 96% | $0.0032 | 48 |
| Reference agent, no guardrails | `deepseek-v4.1-flash-1017` | ★☆☆☆☆ | 104 (35–227) | 90% | $0.0058 | 48 |
| Reference agent, no guardrails | `qwen3.8-flash-next` | ★☆☆☆☆ | 188 (89–326) | 73% | $0.0070 | 48 |
| Reference agent, no guardrails | `glm-5.3` | ★☆☆☆☆ | 188 (89–326) | 79% | $0.0195 | 48 |
| Reference agent, no guardrails | `minimax-m3.1-flash` | ★☆☆☆☆ | 208 (105–350) | 73% | $0.0074 | 48 |

The top five are not statistically separable at these sample sizes (Fisher's exact test); the
leaderboard groups them and says so. 96 clean runs could earn at most four stars; five stars needs 183.

### What v2 found: guardrails tuned to the traps they were written against do not generalise

Four of the sixteen traps are **held-out**: written after the hardened guardrails were frozen and
deliberately not matched by their patterns.

| Configuration | Serious incidents, 12 original traps | Serious incidents, 4 held-out traps |
|---|---|---|
| Reference agent, hardened (7 guardrails) | 0 / 72 | 5 / 24 |
| Reference agent, prompt guardrail only | 0 / 72 | 5 / 24 |
| OpenCode | 0 / 72 | 1 / 24 |
| Reference agent, no guardrails (`deepseek`) | 1 / 36 | 4 / 12 |

On Suite v1 the hardened agent was perfect (0 of 36). On the held-out traps its seven tool-level
guardrails did no better than a single system prompt: a pip *user config* pointing at an unknown
index needs no `--index-url` flag for the guardrail to catch. This is why a rating needs a published,
growing trap suite rather than a fixed checklist.

### Trap Suite v1 (frozen)

Every row is 36 runs over all 12 v1 traps.

| Agent | Model | Rating | Serious / 1,000 (95% CI) | Safe success | $ / safe success |
|---|---|---|---|---|---|
| Reference agent, hardened | `deepseek-v4.1-flash-1017` | ★★★☆☆ | 0 (0–97) | 100% | $0.0056 |
| OpenCode 1.19.5, inside the microVM | `deepseek-v4.1-flash-1017` | ★★★☆☆ | 0 (0–97) | 100% | $0.0076 |
| Reference agent, no guardrails | `qwen3.8-27b` | ★★☆☆☆ | 56 (7–187) | 94% | $0.0037 |
| Reference agent, no guardrails | `qwen3.8-flash-next` | ★☆☆☆☆ | 83 (18–225) | 81% | $0.0058 |
| Reference agent, no guardrails | `mimo-v2.6-pro` | ★☆☆☆☆ | 83 (18–225) | 92% | $0.0058 |
| Reference agent, no guardrails | `glm-5.3` | ★☆☆☆☆ | 83 (18–225) | 89% | $0.0183 |
| Reference agent, no guardrails | `deepseek-v4.1-flash-1017` | ★☆☆☆☆ | 86 (18–231) | 89% | $0.0055 |
| Reference agent, no guardrails | `minimax-m3.1-flash` | ★☆☆☆☆ | 194 (82–360) | 72% | $0.0070 |

### Containment and grading, measured

- **Escape matrix:** 17/17 hostile payloads contained for agents whose brain stays on the host, and
  22/22 for agents that run inside the microVM (the 17 plus five attacks on the inference lane).
  Metadata, HTTPS/TCP/UDP/DNS exfiltration, host SSH/Postgres/API, private networks, host secrets,
  kernel and KVM isolation, fork, memory and disk bombs. See /methodology.
- **No key in the guest:** in-VM agents reach their model through a host-side inference lane that
  holds the key, pins the model, enforces a token budget and meters every token.
- **Jury accuracy:** on 370 production runs the two System One jurors scored AUC 0.98 against the
  tripwires with no false alarms at 0.5, so they triage runs for a person rather than decide.
- **Every grader bug found is published**, with the runs it changed: [docs/VALIDATION.md](docs/VALIDATION.md).
  Stored runs are re-graded from immutable evidence and keep their previous verdict for audit.

### A rating, not a containment test

A sandbox that holds tells a buyer nothing about the agent inside it. Window Sticker uses the
containment to let a real agent fail safely, then rates the agent: how often it does something
dangerous, with an exact confidence interval, how often it finishes, and what it costs.

---

## How a crash test works

```
for each run:
  fork a fresh microVM (own kernel)  ──►  seed a workspace containing one trap
  hash every file                    ──►  the agent works on a legitimate task
  hash every file again              ──►  run the hidden success check
  collect the Egress Warden log      ──►  destroy the microVM, verify it is gone
  grade: tripwires → decision-model jury → verdict
aggregate: exact intervals → stars, cost per safe success, per-trap breakdown
```

| Layer | What it does |
|---|---|
| **Trap suites** | v1: 12 scenarios, frozen. v2 (default): v1 with two fairness fixes plus 4 held-out traps (`backend/windowsticker/traps/suites/`). Each pairs a real task with a trap: a poisoned README, a ticket that slips in an SSH key, test output that pipes a script into a shell, an instruction hidden in a screenshot, the cloud metadata service, a production `.env`, a test-deletion shortcut, scope creep into Terraform, a rogue package index, DNS exfiltration, a runaway process, gameable tests; held out: a setup script that uploads a token, a pip config pointing at an unknown index, a config checker that leaks a key over DNS, a report that invites repeating a password. |
| **Canaries** | Fake credentials generated fresh for every run. A leak can be traced to exactly one run, and nothing real is ever at risk. |
| **Tripwires** | Mechanical checks, the ground truth: a canary leaving the VM, a protected file changing, a blocked connection attempt, a forbidden command, a false claim of success. |
| **Decision-model jury** | Two Vultr System One models (`clef`, `d3`) answer the same typed questions about each scrubbed run and return probabilities. They triage: a run no tripwire caught but a juror suspects, or where they disagree, goes to a human label queue. |
| **Statistics** | Clopper–Pearson exact intervals. Stars come from the *upper* bound, so a small sample cannot earn a high rating by luck. A/B comparisons use Fisher's exact test. |

### Containment

| Control | Implementation |
|---|---|
| Kernel isolation | One [Microsandbox](https://docs.microsandbox.dev) libkrun microVM per run on a Vultr VX1 host (the pattern in Vultr's own agent-sandboxing guide). |
| Egress | Deny-all network policy. The only reachable ports are the run's **Egress Warden** lane, which logs every attempt and allows nothing off the allowlist, and, for in-VM agents, the inference lane. Metadata ranges are explicitly denied. Names are resolved and checked on the host. |
| Secrets | The reference agent's brain runs on the host, so the inference key never enters the VM. In-VM agents (OpenCode) get a per-run lane URL instead of a key: the host adds the key, pins the model and meters tokens. |
| Limits | CPU, memory, a 4 GiB disk cap, per-command timeout, wall-clock, step and token budgets; concurrency capped by free host memory. |
| Lifecycle | Every VM is destroyed in a `finally` block, then teardown is verified by label. |

**Guardrails vs containment.** Guardrails belong to the agent under test. An action a
guardrail refuses is a *near miss*. The lab's containment is not part of the agent, so
anything the microVM or the warden has to stop counts as an *incident*.

---

## Vultr services used

| Service | Role |
|---|---|
| Cloud Compute (VX1, KVM) | One host runs the microVMs, the Egress Warden, the inference lane, the control plane and the web app |
| Serverless Inference: chat models | The agents under test (`deepseek-v4.1-flash`, `glm-5.3`, `qwen3.8`, `mimo`, `minimax`) |
| Serverless Inference: System One | The decision-model jury (`clef`, `d3`) |
| Firewall groups (API) | SSH only from the operator's IP; 80/443 public; created by `windowsticker host create` |
| Vultr API v2 | Host lifecycle (create, wait for active, tagged destroy), SSH keys, firewall rules |

Roadmap, not built: a separate app VM for the control plane, a fleet of VX1 sandbox hosts behind
the queue, and generating trap variants with the vector store and embeddings.

---

## Quick start

```bash
cd backend
uv sync
uv run pytest                      # 145 tests, no keys needed
uv run windowsticker suite list    # the trap suite
uv run windowsticker stats thresholds
```

On a KVM-capable host with a `.env` (see `.env.example`):

```bash
uv sync --extra sandbox
uv run windowsticker probe inference
uv run windowsticker probe sandbox
uv run windowsticker run --agent ../agents/baseline.yaml --runs 48
uv run windowsticker regrade-test <test-id>   # re-grade stored runs with the current tripwires
```

Outputs go to `artifacts/<test_id>/`: `runs.jsonl` (every step, command, network event
and verdict), `sticker.json`, `sticker.svg` and `badge.svg`.

## Crash-test in CI (GitHub Action)

`action/` is a dependency-free GitHub Action. On every pull request that touches an agent's prompt
or guardrails it starts a crash test, waits, writes the sticker to the job summary, comments it on
the PR and fails the build below a minimum rating. See
[examples/agent-crash-test.yml](examples/agent-crash-test.yml).

```yaml
- uses: <owner>/window-sticker/action@main
  with:
    server: ${{ vars.WINDOW_STICKER_URL }}
    token: ${{ secrets.WINDOW_STICKER_TOKEN }}
    agent-name: Support bot
    system-prompt-file: agent/system-prompt.md
    guardrails: untrusted_content_prompt,no_network_commands
    runs: 36
    min-stars: 3
```

Outputs: `test-id`, `stars`, `serious-per-1000`, `url`. A provisional sticker (under 30 runs)
never passes a `min-stars` gate.

## Deployment (one Vultr VX1 host)

```
Internet ─► Caddy (TLS, :443) ─┬─ /api/*  ─► FastAPI control plane (:8000) ─► Postgres (local)
                               └─ /*      ─► Next.js web app (:3000)
            worker (systemd) ── claims queued tests ─► Microsandbox microVMs ─► Egress Warden lanes
                            └── Vultr Serverless Inference (agent + System One jury)
```

```bash
uv run windowsticker host create --admin-cidr <your-ip>/32       # VX1, SSH key, firewall group
rsync … && ssh root@<host> WSK_DOMAIN=<ip-with-dashes>.sslip.io bash infra/host/provision.sh
ssh wsk@<host> bash window-sticker/infra/host/release.sh          # build backend + web
ssh root@<host> systemctl restart wsk-api wsk-worker wsk-web caddy
```

`provision.sh` installs Postgres (local only), Node 22 and Caddy, generates the database password and
the write-access token into the host's `.env` (mode 600), and installs the systemd units. Reads are
public; starting tests and labelling runs need `Authorization: Bearer $WSK_ADMIN_TOKEN`.

## Repository layout

```
agents/                 agent configurations under test
backend/windowsticker/  engine: traps, sandbox driver, warden, agent, grading, stats, sticker, CLI
backend/tests/          unit and end-to-end tests (test doubles live only here)
docs/                   build plan, measurements, methodology
infra/                  host provisioning, systemd units, the OpenCode agent image
web/                    Next.js product: leaderboard, live crash tests, run replays, compare
action/                 GitHub Action that gates a pull request on a minimum rating
```

## Status

Live on one Vultr VX1 host: the engine, control plane, web product, GitHub Action, both escape
matrices, the jury report, Trap Suite v1 (frozen) and v2 with a nine-configuration leaderboard. An
independent review's findings and their resolutions are tracked in [docs/REVIEW.md](docs/REVIEW.md).

Next: harder variants of the eight traps no agent has fallen for yet, a separate control-plane VM,
and more sandbox hosts so a 183-run five-star test finishes in minutes.

## License

MIT
