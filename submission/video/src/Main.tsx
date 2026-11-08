import type { FC } from "react";
import { AbsoluteFill, Audio, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";
import durations from "../public/vo/durations.json";
import { C, Finish, HazardWipe, clamp, sans } from "./kit";
import { Business, Close, Cold, Contain, Findings, How, Idea, Live, Logo, Results, Vultr } from "./scenes";
import timeline from "./timeline.json";
import script from "./vo-script.json";

const SCENES: Record<string, FC<{ dur: number }>> = {
  cold: Cold,
  logo: Logo as FC<{ dur: number }>,
  idea: Idea,
  how: How,
  live: Live,
  contain: Contain,
  results: Results,
  findings: Findings,
  vultr: Vultr,
  business: Business,
  close: Close,
};

// Spoken spellings back to their written form, for the subtitles.
const WRITTEN: [RegExp, string][] = [
  [/micro V Ms/g, "microVMs"],
  [/micro V M/g, "microVM"],
  [/\bV X 1\b/g, "VX1"],
  [/\bA P I\b/g, "API"],
  [/\bD N S\b/g, "DNS"],
  [/\bL L Ms\b/g, "LLMs"],
  [/\bC I\b/g, "CI"],
  [/\bV M\b/g, "VM"],
  [/oh-wasp top ten/g, "OWASP Top 10"],
  [/crash test rating/g, "crash-test rating"],
  [/security review packet/g, "security-review packet"],
  [/five hundred and seventy six/g, "576"],
];
const written = (s: string) => WRITTEN.reduce((acc, [re, to]) => acc.replace(re, to), s);

type Cue = { from: number; to: number; text: string };

function cues(): Cue[] {
  const out: Cue[] = [];
  const fps = timeline.fps;
  for (const scene of timeline.scenes) {
    const line = (script as [string, string][]).find(([id]) => id === scene.vo);
    if (!line) continue;
    const text = written(line[1]);
    // Sentences, with long ones split at a comma so a cue never runs past two lines.
    const parts: string[] = [];
    for (const sentence of text.match(/[^.?!]+[.?!]?/g) ?? [text]) {
      const s = sentence.trim();
      if (s.length > 95 && s.includes(",")) {
        const mid = s.indexOf(",", Math.floor(s.length / 2) - 20);
        const cut = mid > 0 ? mid : s.indexOf(",");
        parts.push(s.slice(0, cut + 1).trim(), s.slice(cut + 1).trim());
      } else if (s) parts.push(s);
    }
    const total = parts.reduce((a, p) => a + p.length, 0);
    const voFrames = (durations as Record<string, number>)[scene.vo] * fps;
    let at = scene.voFrom;
    for (const p of parts) {
      const len = (p.length / total) * voFrames;
      out.push({ from: Math.round(at), to: Math.round(at + len), text: p });
      at += len;
    }
  }
  return out;
}
const CUES = cues();

function Subtitles() {
  const frame = useCurrentFrame();
  const cue = CUES.find((c) => frame >= c.from && frame < c.to);
  if (!cue) return null;
  const p = interpolate(frame, [cue.from, cue.from + 5], [0, 1], clamp);
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 46, pointerEvents: "none" }}>
      <div
        style={{
          maxWidth: 1440,
          background: "rgba(12,14,18,.82)",
          color: "#fff",
          fontFamily: sans,
          fontWeight: 600,
          fontSize: 36,
          lineHeight: 1.32,
          padding: "12px 26px",
          borderRadius: 14,
          textAlign: "center",
          opacity: p,
          transform: `translateY(${(1 - p) * 8}px)`,
          boxShadow: "0 10px 30px rgba(0,0,0,.35)",
        }}
      >
        {cue.text}
      </div>
    </AbsoluteFill>
  );
}

// Music sits under the voice: full between lines, ducked while someone is speaking.
function musicVolume(f: number): number {
  const fps = timeline.fps;
  let duck = 0;
  for (const s of timeline.scenes) {
    const a = s.voFrom;
    const b = a + (durations as Record<string, number>)[s.vo] * fps;
    duck = Math.max(duck, interpolate(f, [a - 10, a, b, b + 14], [0, 1, 1, 0], clamp));
  }
  const fadeIn = interpolate(f, [0, 20], [0, 1], clamp);
  return fadeIn * interpolate(duck, [0, 1], [0.62, 0.2]);
}

const CUTS_WITH_TAPE = ["logo", "live", "results", "close"];

export const Main = () => {
  return (
    <AbsoluteFill style={{ background: C.lab }}>
      {timeline.scenes.map((s) => {
        const Scene = SCENES[s.id];
        return (
          <Sequence key={s.id} from={s.from} durationInFrames={s.frames} name={s.id}>
            <Scene dur={s.frames} />
          </Sequence>
        );
      })}
      {timeline.scenes
        .filter((s) => CUTS_WITH_TAPE.includes(s.id))
        .map((s) => (
          <HazardWipe key={`w-${s.id}`} at={s.from} />
        ))}
      <Subtitles />
      <Finish />
      <Audio src={staticFile("music.wav")} volume={musicVolume} />
      {timeline.scenes.map((s) => (
        <Sequence key={`vo-${s.id}`} from={s.voFrom} name={`vo ${s.vo}`}>
          <Audio src={staticFile(`vo/${s.vo}.wav`)} volume={1} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
