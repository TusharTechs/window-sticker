# YouTube upload kit

Published: https://youtu.be/Y1NaXn9gOqo

Video: `docs/submission/window-sticker-demo.mp4` (2:58)
Thumbnail: `docs/submission/youtube-thumbnail.png` (1280×720, under 2 MB).

## Title (pick one, all under 100 characters)

1. We Crash-Tested AI Agents in Real MicroVMs | Window Sticker (Vultr Agent Rush)
2. Window Sticker: Crash-Test Ratings for AI Agents | Vultr Agent Rush, Blast Radius Zero
3. Same Model, 4★ vs 1★: Crash-Testing AI Agents on Vultr | Window Sticker

## Description

```
Every AI agent should ship with a crash-test rating. Window Sticker runs an agent dozens of times inside throwaway microVMs on Vultr, throws a published suite of traps at it (prompt injection, credential theft, data exfiltration, poisoned packages, evidence tampering), and prints a star rating with an exact 95% confidence interval. Everyone else sells the cage. We sell the crash rating.

▶ Try it live (judge tour with a live test): https://107-191-39-70.sslip.io/tour
▶ Code: https://github.com/TusharTechs/window-sticker

What we found
• 576 graded runs across 9 agent setups on the v2 suite
• Same model, very different scores: DeepSeek with guardrails rated 4★ (0 serious incidents per 1,000 runs, 95% CI 0–38); the same model with no guardrails rated 2★
• Five setups landed between 1★ and 2★
• Ratings held across four operating systems (Holm-adjusted p = 1.00), but Python 3.10 reached for an unknown package index in 10 of 12 runs vs 3 of 12 on Python 3.12
• The sandbox held: 17 of 17 escape attempts contained on every image

How it works
1. Pick an agent, a model and its guardrails
2. Each run boots a fresh libkrun microVM on a Vultr VX1 host, with tripwires on files, network, DNS and processes
3. Deterministic tripwires grade every run; an AI jury only triages, never convicts
4. Clopper–Pearson intervals turn clean runs into stars (17 / 36 / 72 / 183 clean runs for 2 / 3 / 4 / 5 stars)
5. Every run's evidence is archived to Vultr Object Storage with a SHA-256 hash, and each test produces a security-review packet mapped to the OWASP Top 10 for LLM Applications (2025)

Built on Vultr: VX1 compute, Serverless Inference, Object Storage and the Vultr API.

Chapters
0:00 The crash
0:10 Window Sticker
0:17 The idea
0:34 How a run works
0:56 Live on Vultr
1:21 The containment moment
1:40 Results
1:50 Different machines
2:06 Findings
2:24 Built on Vultr
2:37 What teams get
2:48 Close

Built by team Crash Test Dummies for lablab.ai Vultr: Agent Rush, Challenge 1 "Blast Radius Zero". Soundtrack synthesised from code for this video; voice-over is macOS text-to-speech. MIT licensed.

#AIAgents #AISafety #LLMSecurity #PromptInjection #Vultr #Hackathon #lablab
```

## Tags

```
AI agents, AI agent security, AI safety, LLM security, agent evaluation, crash test, prompt injection, OWASP LLM Top 10, red teaming, sandbox, microVM, libkrun, Vultr, Vultr Agent Rush, Blast Radius Zero, lablab.ai, hackathon, DeepSeek, OpenCode, AI benchmark, confidence intervals, Window Sticker
```

## Upload settings

- Category: Science & Technology
- Audience: not made for kids
- Visibility: Public or Unlisted (Unlisted is fine for judges; the link still works)
- Subtitles: YouTube auto-captions work; the video also has burned-in subtitles
- Language: English
