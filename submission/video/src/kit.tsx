import { loadFont as loadArchivo } from "@remotion/google-fonts/Archivo";
import { loadFont as loadInter } from "@remotion/google-fonts/InterTight";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";
import type { CSSProperties, ReactNode } from "react";
import { AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export const display = loadArchivo("normal", { weights: ["800", "900"], subsets: ["latin"] }).fontFamily;
export const sans = loadInter("normal", { weights: ["400", "500", "600", "700"], subsets: ["latin"] }).fontFamily;
export const mono = loadMono("normal", { weights: ["500", "600"], subsets: ["latin"] }).fontFamily;

export const C = {
  ink: "#14161a",
  ink2: "#3b4048",
  paper: "#f5f2ea",
  paper2: "#ece7db",
  card: "#fffdf8",
  yellow: "#ffc400",
  lab: "#0c0e12",
  lab2: "#141820",
  labRule: "#2a313c",
  labInk: "#e8eaee",
  muted: "#8a93a3",
  red: "#ff6b5e",
  redDeep: "#c8231b",
  green: "#5fd39a",
  vultr: "#007bfc",
};

export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
export const easeOut = Easing.bezier(0.16, 1, 0.3, 1);
export const easeInOut = Easing.bezier(0.65, 0, 0.35, 1);

/** 0→1 over [from, from+dur] frames with a smooth ease. */
export const prog = (frame: number, from: number, dur: number, ease = easeOut) =>
  interpolate(frame, [from, from + dur], [0, 1], { ...clamp, easing: ease });

export function useSpring(delay = 0, damping = 14, stiffness = 120) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - delay, fps, config: { damping, stiffness, mass: 0.9 } });
}

/** Blueprint grid for dark scenes, slowly drifting. */
export function LabBg({ children, glow = true }: { children?: ReactNode; glow?: boolean }) {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: C.lab }}>
      <AbsoluteFill
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,.045) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.045) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
          backgroundPosition: `${frame * 0.25}px ${frame * 0.15}px`,
          maskImage: "radial-gradient(ellipse at 50% 45%, black 25%, transparent 80%)",
        }}
      />
      {glow && (
        <AbsoluteFill style={{ background: "radial-gradient(circle at 70% 30%, rgba(255,196,0,.10), transparent 45%)" }} />
      )}
      {children}
    </AbsoluteFill>
  );
}

/** Warm paper with a measurement-sheet dot grid. */
export function PaperBg({ children }: { children?: ReactNode }) {
  return (
    <AbsoluteFill style={{ background: C.paper }}>
      <AbsoluteFill
        style={{ backgroundImage: "radial-gradient(rgba(20,22,26,.09) 1.6px, transparent 1.6px)", backgroundSize: "34px 34px" }}
      />
      <AbsoluteFill style={{ background: "radial-gradient(circle at 75% 35%, rgba(255,196,0,.18), transparent 42%)" }} />
      {children}
    </AbsoluteFill>
  );
}

/** The brand mark, assembled piece by piece: quadrants, star, then the peeling corner. */
export function Mark({ size = 280, delay = 0, tone = "dark" }: { size?: number; delay?: number; tone?: "dark" | "light" }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = (d: number, damping = 12) => spring({ frame: frame - delay - d, fps, config: { damping, stiffness: 140 } });
  const body = "M18 4h28a14 14 0 0 1 14 14v26L44 60H18A14 14 0 0 1 4 46V18A14 14 0 0 1 18 4z";
  const q1 = s(0);
  const q2 = s(4);
  const star = s(10, 9);
  const peel = s(18, 10);
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" style={{ overflow: "visible" }}>
      <defs>
        <clipPath id="mk">
          <path d={body} />
        </clipPath>
      </defs>
      {tone === "dark" && <path d={body} fill="none" stroke="#fffdf8" strokeWidth={5} opacity={q1} strokeLinejoin="round" />}
      <g clipPath="url(#mk)" opacity={Math.min(1, q1 * 1.5)}>
        <rect width="64" height="64" fill={C.ink} />
        <rect x={32 + (1 - q1) * 40} y={-(1 - q1) * 40} width="32" height="32" fill={C.yellow} />
        <rect x={-(1 - q2) * 40} y={32 + (1 - q2) * 40} width="32" height="32" fill={C.yellow} />
      </g>
      <path d={body} fill="none" stroke={C.ink} strokeWidth={2.6} strokeLinejoin="round" opacity={q1} />
      <g transform={`translate(32 29) rotate(${(1 - star) * -120}) scale(${star}) translate(-32 -29)`}>
        <path
          d="M32 12.5l5.6 11.4 12.6 1.8-9.1 8.9 2.1 12.5L32 41.2l-11.2 5.9 2.1-12.5-9.1-8.9 12.6-1.8z"
          fill="#fffdf8"
          stroke={C.ink}
          strokeWidth={2.6}
          strokeLinejoin="round"
        />
      </g>
      <g transform={`translate(52 52) scale(${peel}) translate(-52 -52)`}>
        <path d="M60 44L44 60l-1.2-12.4a4 4 0 0 1 4.4-4.4z" fill={C.paper2} stroke={C.ink} strokeWidth={2.6} strokeLinejoin="round" />
      </g>
    </svg>
  );
}

/** Moving hazard tape. */
export function Tape({ height = 26, style }: { height?: number; style?: CSSProperties }) {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        height,
        backgroundImage: `repeating-linear-gradient(-45deg, ${C.yellow} 0 ${height}px, ${C.ink} ${height}px ${height * 2}px)`,
        backgroundSize: `${height * 2.83}px 100%`,
        backgroundPosition: `${frame * 3}px 0`,
        ...style,
      }}
    />
  );
}

/** A diagonal hazard-tape wipe centred on frame `at` (used across hard cuts). */
export function HazardWipe({ at, dur = 18 }: { at: number; dur?: number }) {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [at - dur / 2, at + dur / 2], [0, 1], { ...clamp, easing: easeInOut });
  if (p <= 0 || p >= 1) return null;
  const x = interpolate(p, [0, 1], [-2600, 2600]);
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          top: -600,
          left: 0,
          width: 1100,
          height: 2400,
          transform: `translateX(${x}px) rotate(18deg)`,
          backgroundImage: `repeating-linear-gradient(-45deg, ${C.yellow} 0 70px, ${C.ink} 70px 140px)`,
          boxShadow: "0 0 80px rgba(0,0,0,.5)",
        }}
      />
    </AbsoluteFill>
  );
}

/** Small chapter label, top left. */
export function Chapter({ n, title, dark = true }: { n: string; title: string; dark?: boolean }) {
  const frame = useCurrentFrame();
  const p = prog(frame, 4, 16);
  return (
    <div
      style={{
        position: "absolute",
        top: 54,
        left: 72,
        display: "flex",
        alignItems: "center",
        gap: 16,
        opacity: p,
        transform: `translateY(${(1 - p) * -12}px)`,
        fontFamily: mono,
        fontSize: 22,
        letterSpacing: "0.18em",
        textTransform: "uppercase",
        color: dark ? C.muted : C.ink2,
      }}
    >
      <span style={{ background: C.yellow, color: C.ink, padding: "4px 10px", borderRadius: 6, fontWeight: 600 }}>{n}</span>
      {title}
    </div>
  );
}

/** Words that rise into place one after another. */
export function Kinetic({
  text,
  delay = 0,
  stagger = 3,
  style,
}: {
  text: string;
  delay?: number;
  stagger?: number;
  style?: CSSProperties;
}) {
  const frame = useCurrentFrame();
  const words = text.split(" ");
  return (
    <div style={{ display: "flex", flexWrap: "wrap", columnGap: "0.26em", ...style }}>
      {words.map((w, i) => {
        const p = prog(frame, delay + i * stagger, 18);
        return (
          <span key={i} style={{ display: "inline-block", overflow: "hidden", paddingBottom: "0.08em" }}>
            <span style={{ display: "inline-block", transform: `translateY(${(1 - p) * 110}%)`, opacity: p }}>{w}</span>
          </span>
        );
      })}
    </div>
  );
}

/** A browser window around recorded footage, with a soft shadow and the live URL. */
export function BrowserFrame({ url, children, width = 1600, style }: { url: string; children: ReactNode; width?: number; style?: CSSProperties }) {
  const h = (width / 16) * 9;
  return (
    <div
      style={{
        width,
        borderRadius: 18,
        overflow: "hidden",
        background: C.card,
        boxShadow: "0 40px 120px rgba(0,0,0,.45), 0 0 0 2px rgba(255,255,255,.06)",
        ...style,
      }}
    >
      <div style={{ height: 46, background: "#1b1f27", display: "flex", alignItems: "center", gap: 10, padding: "0 18px" }}>
        {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
          <span key={c} style={{ width: 13, height: 13, borderRadius: 7, background: c }} />
        ))}
        <div
          style={{
            marginLeft: 18,
            flex: 1,
            height: 28,
            borderRadius: 8,
            background: "#0f1218",
            color: "#9aa4b2",
            fontFamily: mono,
            fontSize: 16,
            display: "flex",
            alignItems: "center",
            padding: "0 14px",
          }}
        >
          <span style={{ color: C.green, marginRight: 8 }}>●</span>
          {url}
        </div>
      </div>
      <div style={{ width, height: h, position: "relative", overflow: "hidden" }}>{children}</div>
    </div>
  );
}

/** Film grain and vignette over everything, for a finished look. */
export function Finish() {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,.28) 100%)" }} />
      <svg width="1920" height="1080" style={{ position: "absolute", opacity: 0.07, mixBlendMode: "overlay" }}>
        <filter id="grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={frame % 30} />
        </filter>
        <rect width="1920" height="1080" filter="url(#grain)" />
      </svg>
    </AbsoluteFill>
  );
}

export const starStr = (k: number) => "★".repeat(k);
