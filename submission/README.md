# Submission materials

| File | What it is |
|---|---|
| `docs/submission/window-sticker-demo.mp4` | The 2:58 demo video (not in git: upload it; rebuild below) |
| `docs/submission/window-sticker-thumbnail.png` | Video thumbnail |
| `docs/submission/window-sticker-deck.pdf` | 12-slide pitch deck, numbers pulled live from the API |
| `docs/submission/security-review-packet-example.pdf` | A security-review packet, as a vendor would attach it |

## Rebuilding the video

Everything is generated, nothing is licensed: footage is recorded from the live site, the voiceover
is a macOS neural voice, and the soundtrack is synthesised from scratch.

```bash
cd submission/video
pnpm install
node record.mjs all          # footage from the live site (starts one real live demo)
node fetch-data.mjs          # the numbers shown on screen, from the live API
# voiceover: see vo-script.json (macOS `say -v Tara -r 168`), then timeline.json
uv run --no-project --with numpy --with scipy python music.py
npx remotion render src/index.ts Main out/window-sticker-demo.mp4 --codec=h264 --crf=16
```

The deck: `node submission/deck/build.mjs` (run from a directory with `@playwright/test`).
