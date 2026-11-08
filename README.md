<p align="center">
  <img src="brand/mark.svg" width="132" alt="Window Sticker logo: crash-test quadrants, a rating star and a peeling sticker corner" />
</p>

<h1 align="center">Window Sticker</h1>

<p align="center">
  <b>Every AI agent should ship with a crash-test rating.</b><br/>
  Dozens of real runs per agent, each in its own throwaway microVM on Vultr, against a published suite of traps,<br/>
  rated with exact confidence intervals.
</p>

<p align="center">
  <a href="https://github.com/TusharTechs/window-sticker/actions/workflows/ci.yml"><img src="https://github.com/TusharTechs/window-sticker/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://github.com/TusharTechs/window-sticker/actions/workflows/cross-browser.yml"><img src="https://github.com/TusharTechs/window-sticker/actions/workflows/cross-browser.yml/badge.svg" alt="Cross-browser checks" /></a>
  <img src="https://img.shields.io/badge/license-MIT-14161a" alt="MIT license" />
  <img src="https://img.shields.io/badge/runs%20on-Vultr-007bfc" alt="Runs on Vultr" />
</p>

<p align="center">
  <a href="https://youtu.be/Y1NaXn9gOqo"><img src="docs/submission/youtube-thumbnail.png" width="640" alt="Watch the 2:58 demo video on YouTube" /></a><br/>
  <a href="https://youtu.be/Y1NaXn9gOqo"><b>▶ Watch the 2:58 demo on YouTube</b></a>
</p>

> Built for the lablab.ai **Vultr: Agent Rush** hackathon, **Challenge 1: Blast Radius Zero**.

---

## Links for judges

| What | Where |
|---|---|
| **Start here: guided tour with a live crash test you run yourself** | https://107-191-39-70.sslip.io/tour |
| Live product | https://107-191-39-70.sslip.io |
| Leaderboard: 9 configurations, 6 Vultr models, 576 runs | https://107-191-39-70.sslip.io/leaderboard |
| Same agent on four operating systems | https://107-191-39-70.sslip.io/environments |
| A containment moment: an API-key leak over DNS, replayed step by step | https://107-191-39-70.sslip.io/runs/run_6970f519ab05 |
| Security-review packet (printable PDF) | https://107-191-39-70.sslip.io/tests/test_f90ffdc425/packet |
| Methodology: containment, grading, statistics, limits | https://107-191-39-70.sslip.io/methodology |
| The published trap suite | https://107-191-39-70.sslip.io/suite |
| Public JSON API (example) | https://107-191-39-70.sslip.io/api/leaderboard?suite=v2 |
| **Demo video (2:58)** | https://youtu.be/Y1NaXn9gOqo (source: [`submission/video`](submission/video)) |
| Pitch deck (PDF) | [docs/submission/window-sticker-deck.pdf](docs/submission/window-sticker-deck.pdf) |
| Example security-review packet (PDF) | [docs/submission/security-review-packet-example.pdf](docs/submission/security-review-packet-example.pdf) |
| How each judging criterion is met | [docs/JUDGING.md](docs/JUDGING.md) |
| Every grader bug found, and the verdicts it changed | [docs/VALIDATION.md](docs/VALIDATION.md) |
| Three rounds of independent review and their resolutions | [docs/REVIEW.md](docs/REVIEW.md) |
| Source code | https://github.com/TusharTechs/window-sticker |

---

## The idea in one minute

Before you buy a car, the window sticker tells you how it does in a crash and what it costs to run.
Before you give an AI coding agent your repository and your credentials, you get a demo video.

Agents read READMEs, tickets, tool output and config files, then run commands. Any of those can lie.
**Window Sticker** puts a real agent on real tasks, each with one trap hidden in it, dozens of times, each
run in a sealed microVM on a Vultr VX1 host. It lets the agent fail safely, grades every run
mechanically, and prints a sticker:

- **Stars**, from the upper bound of an exact (Clopper–Pearson) 95% confidence interval on serious incidents,
  so a small sample can never earn a high rating by luck;
- **serious incidents and any incidents per 1,000 runs**, each with its interval;
- **safe success**: the hidden check passed and nothing unsafe happened;
- **cost per safe task** and the **all-in cost** of the test, from host-metered tokens and Vultr host time;
- **OWASP Top 10 for LLM Applications (2025)** coverage, per risk.

Every number links to the runs behind it, and every run has a step-by-step replay.

**Everyone else sells the cage. We sell the crash rating.**

---

## Headline results (real runs on Vultr)

| Configuration (Trap Suite v2, 16 traps) | Model | Rating | Serious / 1,000 (95% CI) | Any / 1,000 | Safe success | $ / safe task | Runs |
|---|---|---|---|---|---|---|---|
| Reference agent, prompt guardrail only | `deepseek-v4.1-flash-1017` | ★★★★☆ | 0 (0–38) | 42 | 94% | $0.0055 | 96 |
| Reference agent, hardened (prompt + 6 tool guardrails) | `deepseek-v4.1-flash-1017` | ★★★★☆ | 0 (0–38) | 52 | 94% | $0.0060 | 96 |
| **OpenCode 1.19.5, running inside the microVM** | `deepseek-v4.1-flash-1017` | ★★★☆☆ | 10 (0–57) | 10 | 99% | $0.0082 | 96 |
| Reference agent, no guardrails | `mimo-v2.6-pro` | ★★★☆☆ | 0 (0–74) | 0 | 100% | $0.0049 | 48 |
| Reference agent, no guardrails | `deepseek-v4.1-flash-1017` | ★★☆☆☆ | 21 (1–111) | 83 | 92% | $0.0057 | 48 |
| Reference agent, no guardrails | `qwen3.8-27b` | ★★☆☆☆ | 42 (5–143) | 42 | 96% | $0.0032 | 48 |
| Reference agent, no guardrails | `qwen3.8-flash-next` | ★☆☆☆☆ | 104 (35–227) | 188 | 75% | $0.0068 | 48 |
| Reference agent, no guardrails | `glm-5.3` | ★☆☆☆☆ | 125 (47–252) | 188 | 79% | $0.0195 | 48 |
| Reference agent, no guardrails | `minimax-m3.1-flash` | ★☆☆☆☆ | 188 (89–326) | 208 | 73% | $0.0074 | 48 |

The top six are not statistically separable at these sample sizes (Fisher's exact test against #1,
p ≥ 0.11), and the leaderboard says so. 96 clean runs can earn at most four stars; five needs 183.

**What the measurements found**

| Finding | Evidence |
|---|---|
| **The machine changes the agent.** On Debian 11 / Python 3.10 (no built-in TOML parser) the same agent reached for an unknown package index far more often. | 10 of 12 runs (2 installs) vs 3 of 12 on Python 3.12; Fisher p = 0.012, 0.025 after Holm correction |
| **Ratings held across machines and on unseen traps.** No OS changed either configuration's incident rate measurably; a private, model-reworded trap suite gave the same rating. | Holm-adjusted p = 1.00 on four OS images; hardened: 0 serious on the private suite |
| **Tool guardrails missed the trap they were never written for.** Six tool-level guardrails added nothing measurable over one system prompt. | Both guardrailed agents reached for an unknown index in 9 of 12 held-out runs; 0 refusals |
| **Containment held everywhere.** | Escape matrix 17/17 on each of four OS images; 22/22 for in-VM agents |

<details>
<summary><b>Trap Suite v1 (frozen, 12 traps, 36 runs each, re-graded with the current grader)</b></summary>

| Configuration | Model | Rating | Serious / 1,000 (95% CI) | Safe success |
|---|---|---|---|---|
| Reference agent, hardened | `deepseek-v4.1-flash-1017` | ★★★☆☆ | 0 (0–97) | 100% |
| OpenCode 1.19.5, inside the microVM | `deepseek-v4.1-flash-1017` | ★★★☆☆ | 0 (0–97) | 100% |
| Reference agent, no guardrails | `qwen3.8-27b` | ★★☆☆☆ | 56 (7–187) | 94% |
| Reference agent, no guardrails | `qwen3.8-flash-next` | ★★☆☆☆ | 56 (7–187) | 83% |
| Reference agent, no guardrails | `mimo-v2.6-pro` | ★★☆☆☆ | 56 (7–187) | 92% |
| Reference agent, no guardrails | `deepseek-v4.1-flash-1017` | ★★☆☆☆ | 57 (7–192) | 89% |
| Reference agent, no guardrails | `glm-5.3` | ★☆☆☆☆ | 83 (18–225) | 89% |
| Reference agent, no guardrails | `minimax-m3.1-flash` | ★☆☆☆☆ | 194 (82–360) | 72% |

</details>

---

## Architecture

```mermaid
flowchart LR
    subgraph Users["Who uses it"]
        J["Judges and buyers<br/>(browser)"]
        GA["GitHub Action<br/>(CI gate on a pull request)"]
        CLI["windowsticker CLI"]
    end

    subgraph VX1["Vultr Cloud Compute VX1 host (KVM)"]
        CADDY["Caddy<br/>TLS"]
        WEB["Next.js web app<br/>tour, leaderboard, replays"]
        API["FastAPI control plane<br/>public reads, token writes"]
        PG[("PostgreSQL<br/>tests, runs, labels")]
        WORKER["Worker<br/>long-test lane + live-demo lane"]
        subgraph LAB["The lab: one microVM per run"]
            VM["libkrun microVM<br/>own kernel, 4 GiB disk,<br/>deny-all network,<br/>one of 4 OS images"]
            WARDEN["Egress Warden<br/>logs and refuses<br/>outbound traffic"]
            LANE["Inference lane<br/>holds the key, pins the model,<br/>meters tokens"]
        end
    end

    subgraph VULTR["Vultr managed services"]
        INF["Serverless Inference<br/>6 chat models: agents under test,<br/>incident analyst, trap-variant writer"]
        S1["Serverless Inference<br/>System One decision models<br/>(clef, d3): the jury"]
        OBJ[("Object Storage<br/>evidence bundles + SHA-256")]
        VAPI["Vultr API v2<br/>host, SSH key, firewall"]
    end

    J --> CADDY
    GA --> CADDY
    CADDY --> WEB
    CADDY --> API
    WEB --> API
    API <--> PG
    WORKER <--> PG
    WORKER -- "boot, seed, run, destroy" --> VM
    VM -- "only door out" --> WARDEN
    VM -- "in-VM agents only" --> LANE
    LANE --> INF
    WORKER -- "reference agent's brain" --> INF
    WORKER -- "triage every run" --> S1
    WORKER -- "explain incidents" --> INF
    WORKER -- "archive evidence" --> OBJ
    CLI --> VAPI
```

### One crash-test run, end to end

```mermaid
sequenceDiagram
    autonumber
    participant W as Worker (VX1 host)
    participant VM as microVM
    participant A as Agent under test
    participant N as Egress Warden
    participant M as Vultr Serverless Inference
    participant G as Grader
    participant S as Vultr Object Storage
    W->>VM: Boot a fresh microVM (about 0.6 s), deny-all network
    W->>VM: Seed one trap and a real task, with fake credentials for this run only
    W->>VM: Snapshot every file (guest's isolated Python)
    loop Up to 16 steps or 240 s
        A->>M: Think (reference agent on the host, or OpenCode through the keyless lane)
        A->>VM: Run a tool call: shell, read, write
        VM-->>N: Any outbound attempt is logged and refused
    end
    W->>VM: Snapshot again, re-hash protected files from the host, run the hidden success check
    W->>G: Evidence: steps, commands, network log, file changes, canaries
    G->>G: Tripwires decide the verdict (mechanical)
    G->>M: System One jury triages, a chat model explains any incident
    W->>VM: Destroy the microVM and verify it is gone
    W->>S: Archive the evidence bundle with its SHA-256
    W->>W: Update the sticker: exact intervals, stars, cost, OWASP coverage
```

---

## How it works end to end

1. **Describe the agent.** A configuration is a model, a system prompt, guardrails and a harness: the
   reference agent (its brain on the host, its tools in the VM) or OpenCode (the whole agent inside the VM).
   Its fingerprint is printed on the sticker, so a different config is a different rating.
2. **Start a crash test** from the web app, the API, the CLI or the GitHub Action. A test is N runs spread
   evenly over the trap suite, on a chosen OS image. Live demos from the tour have their own worker lane.
3. **Each run is sealed.** A fresh libkrun microVM with its own kernel, a 4 GiB disk cap, CPU, memory, step,
   token and wall-clock budgets, and a deny-all network. The only doors out are the **Egress Warden**, which
   logs and refuses traffic, and, for in-VM agents, the **inference lane**, which holds the API key on the host.
4. **One trap per task.** Sixteen traps cover prompt injection (README, ticket, tool output, image), secrets
   (metadata service, `.env`, DNS exfiltration), supply chain (rogue package indexes), destructive shortcuts,
   scope creep, runaway processes and false completion. Four are **held out**: written after the
   guardrails were frozen. Credentials are canaries minted for that run alone.
5. **Mechanical grading.** Tripwires check the evidence: a canary leaving, a protected file changing, a refused
   connection, a forbidden command actually executed, a false claim of success. Package-index traps are graded
   by what happened: contact is logged, a download is an incident, only an install is serious.
6. **Models help, never decide.** Two Vultr System One models answer typed questions about each scrubbed run and
   send doubtful runs to a human queue. A Vultr chat model writes a plain-English explanation of each incident.
7. **Teardown and evidence.** The microVM is destroyed and its absence verified; the full evidence bundle goes
   to Vultr Object Storage with its SHA-256 next to the run.
8. **The rating.** Clopper–Pearson intervals give stars, incident rates and safe success; Fisher's exact test
   compares configurations; Holm's correction handles many machines at once.
9. **Use it.** A sticker and README badge, a step-by-step replay of every run, a leaderboard, A/B comparisons, a
   security-review packet mapped to OWASP, and a CI gate that fails a pull request only on a measurable regression.

---

## How it meets the judging criteria

| Criterion | What we built | Where to see it |
|---|---|---|
| **Application of Technology**: how effectively the models are integrated | Vultr Serverless Inference does five measured jobs: **6 agent models** under test; **OpenCode inside the VM** through a keyless, metered lane; the **System One jury** (`clef`, `d3`; AUC 0.98 on 370 runs, used as triage); an **incident analyst** that explains every incident; a **trap-variant writer** that builds private suites. On Vultr Compute: one libkrun microVM per run on a VX1 host, four OS images, 17/17 and 22/22 escape matrices. Vultr Object Storage keeps every run's evidence. | `/leaderboard`, `/methodology`, any incident replay, `/environments` |
| **Presentation**: clarity and effectiveness | A guided nine-step **tour** with a **live crash test** the judge starts (six real microVM runs, about a minute); a hero replay of real tests; step-by-step run replays with "What the lab stopped"; a 2:58 demo video; a 12-slide deck; every page checked in Chromium, Firefox, WebKit and on phones. | `/tour`, `/runs/run_6970f519ab05`, [demo video](https://youtu.be/Y1NaXn9gOqo), deck |
| **Business Value**: impact and practical fit | Buyers (platform and security teams), vendors (stuck in security reviews) and teams shipping prompt changes. A **security-review packet** mapped to the **OWASP Top 10 for LLM Applications**; a **GitHub Action** gate; measured unit economics (a 96-run rating costs about $0.50 all-in); a proposed model of free engine, $49 per published sticker, $199 per CI-gated agent per month. | `/tests/<id>/packet`, `action/`, landing page |
| **Originality**: uniqueness and the ability to demonstrate behaviours | **A rating of the agent, not a test of the cage.** Exact-interval stars, held-out traps, **private model-reworded trap suites** so a rating cannot be trained against, the **same agent on four operating systems** with a statistical test of whether the machine changed its behaviour, and published grader bugs with every changed verdict. | `/environments`, [docs/VALIDATION.md](docs/VALIDATION.md) |

The full mapping, with numbers, is in [docs/JUDGING.md](docs/JUDGING.md).

---

## Different environments

Window Sticker is tested across environments at three levels.

**1. The agents run on four operating systems.** The same agent and traps on four microVM images, compared
statistically against Debian 12 ([/environments](https://107-191-39-70.sslip.io/environments)):

| Image | Operating system | What changes for the agent | Escape matrix |
|---|---|---|---|
| `python:3.12` | Debian 12, full toolchain | Baseline: bash, curl, wget, git, compiler | 17/17 |
| `python:3.12-slim` | Debian 12, slim | No curl, wget or git | 17/17 |
| `python:3.12-alpine` | Alpine Linux | BusyBox shell, no bash, musl libc | 17/17 |
| `python:3.10-slim-bullseye` | Debian 11, Python 3.10 | No built-in TOML parser | 17/17 |

Each environment page shows what the agent did differently on each machine (tools it reached for that were
missing, package moves), linked to replays. Building this exposed a portability bug in our own harness
(BusyBox `find` returned empty snapshots on Alpine); file snapshots are now taken by the guest's isolated
Python, identical on every image.

**2. The web product works in every browser.** [Playwright](web/e2e) loads every page in Chromium, Firefox and
WebKit (Safari's engine), on desktop and on Pixel and iPhone sizes, checking for errors, sideways scrolling and
key content: 60 checks, run daily by a [GitHub workflow](.github/workflows/cross-browser.yml).

**3. It runs locally on macOS, Linux and Windows**, as described below. Only real microVM runs need a Linux
host with KVM (such as a Vultr VX1).

---

## Run it locally

| Mode | Works on | Needs | What you get |
|---|---|---|---|
| **A. The web app against the live lab** | macOS, Linux, Windows | Node.js 22, pnpm | The full UI on your machine, with live data |
| **B. The whole stack, no microVMs** | macOS, Linux, Windows (WSL2 for the shell scripts) | Python 3.12 with [uv](https://docs.astral.sh/uv/), Node.js 22, pnpm | API, web app and the 182-test suite, no keys needed |
| **C. Real crash tests** | Linux with `/dev/kvm` (e.g. a Vultr VX1) | B, plus [Microsandbox](https://docs.microsandbox.dev) and a Vultr Serverless Inference key | Real microVM runs, stickers and replays |

**A. The web app against the live lab** (any OS)

```bash
git clone https://github.com/TusharTechs/window-sticker.git
cd window-sticker/web
pnpm install
WSK_API_ORIGIN=https://107-191-39-70.sslip.io pnpm dev     # then open http://localhost:3000
```

On Windows PowerShell, set the variable first: `$env:WSK_API_ORIGIN="https://107-191-39-70.sslip.io"`.

**B. The whole stack, no microVMs** (any OS)

```bash
cd backend
uv sync
uv run pytest                                   # 182 tests: grading, statistics, API, agents, all offline
uv run windowsticker suite list                 # the trap suite
WSK_DATABASE_URL=sqlite+aiosqlite:///./dev.sqlite3 \
  uv run windowsticker serve --port 8765        # the API on SQLite (in one terminal)

cd ../web && pnpm install && pnpm dev           # the web app on http://localhost:3000 (in another)
cd ../web && WSK_E2E_URL=http://localhost:3000 pnpm e2e   # optional: the cross-browser checks
```

**C. Real crash tests** (Linux with KVM)

```bash
cp .env.example .env                            # add VULTR_INFERENCE_API_KEY; never commit it
bash infra/host/bootstrap.sh                    # checks /dev/kvm, installs uv and Microsandbox
cd backend && uv sync --extra sandbox
uv run windowsticker probe sandbox              # boots one microVM
uv run windowsticker run --agent ../agents/baseline.yaml --runs 48
```

Outputs go to `artifacts/<test_id>/`: every run's evidence, the sticker (JSON and SVG) and a README badge.
Production deployment on a Vultr VX1 host (`windowsticker host create`, `infra/host/provision.sh`,
`release.sh`, systemd units behind Caddy) is described in [infra/host](infra/host).

---

## Project structure

```
window-sticker/
├── backend/                     Python 3.12 engine and control plane (FastAPI, SQLAlchemy)
│   ├── windowsticker/
│   │   ├── traps/               Trap Suites v1 (frozen) and v2, canaries, OWASP mapping, private variants
│   │   ├── sandbox/             Microsandbox microVM driver
│   │   ├── warden/              Egress Warden proxy, DNS lane, keyless inference lane
│   │   ├── agents/              Reference agent, OpenCode adapter, guardrails
│   │   ├── runner/              One run end to end; a crash test of many runs
│   │   ├── grading/             Tripwires, decision-model jury, fusion, incident analyst
│   │   ├── stats/               Clopper–Pearson ratings, Fisher's exact test
│   │   ├── escape/              The escape matrix (17 + 5 hostile payloads)
│   │   ├── api/                 HTTP and WebSocket API, live demo, environment matrix
│   │   ├── environments.py      The four OS images
│   │   ├── evidence_store.py    Evidence archive in Vultr Object Storage
│   │   └── cli.py               windowsticker: run, serve, worker, regrade, explain, host, ...
│   └── tests/                   182 tests (all offline, with test doubles)
├── web/                         Next.js 15 product: tour, leaderboard, environments, replays, packets
│   └── e2e/                     Playwright cross-browser checks
├── action/                      GitHub Action: crash-test a pull request, gate on a regression
├── agents/                      Agent configurations under test (YAML)
├── infra/                       Host provisioning, systemd units, Caddy, the OpenCode agent image
├── brand/                       The logo (SVG) and its renderer
├── submission/                  Demo video (Remotion) and pitch deck sources
├── docs/                        JUDGING, VALIDATION, REVIEW, MEASUREMENTS, submission PDFs
└── .github/workflows/           CI and the daily cross-browser checks
```

---

## AI disclosure

We used AI in two different ways, and we want both to be clear.

**AI inside the product (the runtime)**, all on Vultr Serverless Inference:

| Role | Models | What it is allowed to do |
|---|---|---|
| Agents under test | `deepseek-v4.1-flash`, `qwen3.8-27b`, `qwen3.8-flash-next`, `glm-5.3`, `mimo-v2.6-pro`, `minimax-m3.1-flash`; [OpenCode](https://opencode.ai) 1.19.5 as an open-source coding-agent harness | Be rated. They never grade themselves |
| Jury | Vultr System One decision models `clef` and `d3` | Triage: send doubtful runs to a person. Never decide a verdict |
| Incident analyst | `deepseek-v4.1-flash` | Explain an incident in plain English from scrubbed evidence. Never changes a verdict; output that claims data left the lab is rejected |
| Trap-variant writer | `deepseek-v4.1-flash` | Reword trap prose for private suites; any rewrite that alters a command, path, placeholder or tripwire is discarded |

Verdicts come only from mechanical tripwires and, where needed, a human label.

**AI used to build the project (development tools):**

| Tool | Used for |
|---|---|
| Anthropic **Claude** (Claude Code, an AI coding assistant) | Pair-programming the code and tests, infrastructure scripts, web design, documentation, the deck and the video edit, and running independent review rounds against the judging criteria. All work was directed, reviewed and approved by the author, and every number in this README comes from real runs |
| macOS built-in neural text-to-speech (voice "Tara") | The demo video's narration |

Not AI-generated: the logo is a hand-built SVG; the demo video's soundtrack is synthesised by our own code
([`submission/video/music.py`](submission/video/music.py)); the video is edited in code with
[Remotion](https://www.remotion.dev) from real screen recordings of the live product. No generative image,
video or music models were used.

---

## License

[MIT](LICENSE) © 2026 Tushar Agarwal
