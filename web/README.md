# Window Sticker web app

Next.js (App Router) front end for the control plane.

```bash
pnpm install
WSK_API_ORIGIN=http://127.0.0.1:8765 pnpm dev   # API from `windowsticker serve --port 8765`
```

| Route | What it shows |
|---|---|
| `/` | Landing page with the latest real sticker and findings |
| `/new` | Configure an agent (model, prompt, guardrails) and start a crash test |
| `/tests`, `/tests/[id]` | Live Grid of microVM runs (WebSocket) and the sticker |
| `/runs/[id]` | Crash replay: step timeline, tripwires, warden log, jury, hidden check |
| `/compare` | Before/after with Fisher's exact test |
| `/leaderboard` | Safety per dollar across agent configurations |
| `/suite` | Trap Suite v1 |
| `/methodology` | Measured containment, grading rules, star thresholds |
