# Window Sticker against the judging criteria

Where each criterion is demonstrated, with a link a judge can open. Everything listed runs on
the live deployment: https://107-191-39-70.sslip.io (start at `/tour`).

## 1. Application of Technology: how effectively the models are integrated

Vultr Serverless Inference does four separate jobs, each with a measured result:

| Model role | Models | Where to see it |
|---|---|---|
| **Agents under test** | `deepseek-v4.1-flash`, `qwen3.8-27b`, `qwen3.8-flash-next`, `glm-5.3`, `mimo-v2.6-pro`, `minimax-m3.1-flash` | `/leaderboard`: 9 configurations, 576 runs on Trap Suite v2 |
| **Agent running inside the microVM** | OpenCode 1.19.5 on `deepseek-v4.1-flash`, reaching the model through a host-side lane that holds the key, pins the model, enforces a token budget and meters tokens | any OpenCode replay; escape matrix 22/22 at `/methodology` |
| **Decision-model jury** | System One `clef` and `d3`, typed questions answered with probabilities | `/methodology`: AUC 0.98 on 370 runs, catching 29–31 of 40 incidents at 0.5; the jury triages, never decides |
| **Incident analyst** | a chat model explains each incident: what happened, why it matters, how to prevent it | the "In plain English" box on any incident replay |

| **Trap variant writer** | a chat model rewords every trap's prose under strict checks, producing private suites a vendor cannot tune against | README, "Ratings on traps nobody has seen" |

Infrastructure: one Vultr VX1 host runs a libkrun microVM per run (boot about 0.5 s), on four
operating-system images (`/environments`, escape matrix 17/17 on each); every run's evidence is
archived in Vultr Object Storage with its SHA-256; the Vultr API creates the host, its SSH key and
firewall group. Costs are computed from the live model catalogue plus VX1 host time.

## 2. Presentation: clarity and effectiveness

- **A guided tour** (`/tour`): nine steps, from the question to CI, with a **live crash test the
  judge starts**: pick a model, guardrails and an operating system, and watch six real microVM
  runs land in about a minute.
- **A hero replay** of real crash tests on the landing page: every tile is one stored run.
- **Every number is checkable:** each sticker links to its runs, each run to a step-by-step replay
  with "What the lab stopped", the Egress Warden log, tripwires, jury and the analyst's explanation.
- **Works everywhere:** Playwright checks every page in Chromium, Firefox, WebKit and on phone
  sizes (60 checks).

## 3. Business Value: impact and practical value

- **Buyers:** platform and security teams choosing which agent touches their code; agent vendors
  stuck in security reviews; teams shipping prompt and guardrail changes.
- **Security-review ready:** OWASP Top 10 for LLM Applications coverage on every sticker, and a
  one-click PDF packet per test for vendor security questionnaires.
- **Product surfaces:** a sticker and README badge, an A/B comparison with Fisher's exact test, a
  GitHub Action that fails a pull request only on a measurable regression.
- **Unit economics, measured:** a 96-run rating costs about $0.50–0.80 all-in; the live demo
  about $0.05. Every run is Vultr compute and inference, and CI repeats it on every pull request.
- **A finding a buyer would pay for:** on held-out traps, six tool-level guardrails added nothing
  measurable over one system prompt; the lab, not the guardrails, stopped every fetch from an
  unknown package index.

## 4. Originality: uniqueness and the ability to demonstrate behaviours

- **A rating of the agent, not a test of the cage.** Other entries contain agents; this one
  measures what an agent does when contained, with exact confidence intervals.
- **Behaviour across environments.** The same agent and traps on Debian, slim Debian, Alpine and
  an older Python, with a statistical test of whether the machine changed the agent's behaviour.
- **Held-out traps** written after the guardrails were frozen, and **private variant suites**
  reworded by a model, so a rating cannot be tuned against the published traps.
- **Honest grading:** every grader bug found is published with the verdicts it changed
  (`docs/VALIDATION.md`), and stored runs are re-graded from immutable evidence.
