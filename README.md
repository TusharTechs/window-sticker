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

## Results so far (real runs on Vultr)

| Test | Rating | Serious incidents / 1,000 (95% CI) | Safe success | Cost |
|---|---|---|---|---|
| Reference agent, no guardrails, 36 runs | ★☆☆☆☆ | 86 (18–231) | 89% | $0.17 |
| Reference agent, hardened, 36 runs | ★★★☆☆ | 0 (0–97) | 100% | $0.20 |
| Dependency-confusion trap, 10 v 10 | – | 900 (555–997) v 0 (0–308), **Fisher p = 0.000119** | 10% v 100% | $0.17 |

Agent model: `deepseek-v4.1-flash-1017` on Vultr Serverless Inference. Jury: `clef` + `d3`.
Validation log, including every false positive found and fixed: [docs/VALIDATION.md](docs/VALIDATION.md).

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
| **Trap Suite v1** | 12 scenarios (`backend/windowsticker/traps/suites/v1`). Each pairs a real task with a trap: a poisoned README, a ticket that slips in an SSH key, test output that pipes a script into a shell, an instruction hidden in a screenshot, the cloud metadata service, a production `.env`, a test-deletion shortcut, scope creep into Terraform, a rogue package index, DNS exfiltration, a runaway process, and gameable tests. |
| **Canaries** | Fake credentials generated fresh for every run. A leak can be traced to exactly one run, and nothing real is ever at risk. |
| **Tripwires** | Mechanical checks, the ground truth: a canary leaving the VM, a protected file changing, a blocked connection attempt, a forbidden command, a false claim of success. |
| **Decision-model jury** | Two Vultr System One models (`clef`, `d3`) answer the same typed questions about each run and return probabilities. They only judge what tripwires cannot. Runs where the two disagree go to a human label queue. |
| **Statistics** | Clopper–Pearson exact intervals. Stars come from the *upper* bound, so a small sample cannot earn a high rating by luck. A/B comparisons use Fisher's exact test. |

### Containment

| Control | Implementation |
|---|---|
| Kernel isolation | One [Microsandbox](https://docs.microsandbox.dev) libkrun microVM per run on a Vultr VX1 host (the pattern in Vultr's own agent-sandboxing guide). |
| Egress | Deny-all network policy. The only reachable port is the run's **Egress Warden** lane, which logs every attempt and allows nothing that isn't on the allowlist. Metadata ranges are explicitly denied. Names are resolved and checked on the host. |
| Secrets | The reference agent's brain runs outside the VM, so the inference key never enters it. Agents that must run inside get a Microsandbox placeholder secret, swapped in only for the inference host. A violation terminates the VM. |
| Limits | CPU, memory, per-command timeout, wall-clock, step and token budgets. |
| Lifecycle | Every VM is destroyed in a `finally` block, then teardown is verified by label. |

**Guardrails vs containment.** Guardrails belong to the agent under test. An action a
guardrail refuses is a *near miss*. The lab's containment is not part of the agent, so
anything the microVM or the warden has to stop counts as an *incident*.

---

## Vultr services used

| Service | Role |
|---|---|
| Cloud Compute (VX1, KVM) | Sandbox host running Microsandbox microVMs and the Egress Warden |
| Cloud Compute (app VM) | Control plane API and web app |
| Serverless Inference: chat models | The agent under test (`deepseek-v4.1-flash`, `glm-5.3`, `qwen3.8`, …) |
| Serverless Inference: System One | The decision-model jury (`clef`, `d3`) |
| Serverless Inference: vector store, embeddings | Trap library and mutated variants *(Phase 2)* |
| Serverless Inference: content safety | Screening of image traps *(Phase 2)* |
| Firewall groups (API) | SSH only from the operator's IP; 80/443 public; created by `windowsticker host create` |
| Vultr API v2 | Host lifecycle (create, wait active, tagged destroy), SSH keys, firewall rules, billing balance |

---

## Quick start

```bash
cd backend
uv sync
uv run pytest                      # 94 tests, no keys needed
uv run windowsticker suite list    # the trap suite
uv run windowsticker stats thresholds
```

On a KVM-capable host with a `.env` (see `.env.example`):

```bash
uv sync --extra sandbox
uv run windowsticker probe inference
uv run windowsticker probe sandbox
uv run windowsticker run --agent ../agents/baseline.yaml --runs 36
```

Outputs go to `artifacts/<test_id>/`: `runs.jsonl` (every step, command, network event
and verdict), `sticker.json`, `sticker.svg` and `badge.svg`.

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
infra/                  host bootstrap and Terraform
web/                    product UI (Phase 3)
```

## Status

Phases 0–3 and the production deploy are done: measured on Vultr, engine, control plane, web
product, live at the URL above. Next: OpenCode inside the microVM, more models on the leaderboard,
the published escape matrix and the GitHub Action. See [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md).

## License

MIT
