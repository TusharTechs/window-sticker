"""Original soundtrack for the demo video, synthesised from scratch and scored to timeline.json.

    uv run --no-project --with numpy --with scipy python music.py

A minor, 100 BPM. Every sound is generated here (no samples), so there is nothing to license.
"""

from __future__ import annotations

import json
import wave

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48_000
TL = json.load(open("timeline.json"))
TOTAL = TL["total"] + 2.0
S = {s["id"]: s for s in TL["scenes"]}
BEAT = 60 / 100
BAR = 4 * BEAT
N = int(TOTAL * SR)
L = np.zeros(N)
R = np.zeros(N)
rng = np.random.default_rng(7)


def hz(note: str) -> float:
    names = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3, "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}
    name, octave = note[:-1], int(note[-1])
    return 440.0 * 2 ** ((names[name] + 12 * (octave - 4)) / 12)


def t_arr(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR)) / SR


def env(n: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    sus = max(0, n - a_n - d_n - r_n)
    e = np.concatenate([np.linspace(0, 1, max(1, a_n)), np.linspace(1, s, max(1, d_n)), np.full(sus, s), np.linspace(s, 0, max(1, r_n))])
    return e[:n] if len(e) >= n else np.pad(e, (0, n - len(e)))


def lp(x: np.ndarray, cutoff: float, order: int = 2) -> np.ndarray:
    return sosfilt(butter(order, cutoff, "low", fs=SR, output="sos"), x)


def hp(x: np.ndarray, cutoff: float, order: int = 2) -> np.ndarray:
    return sosfilt(butter(order, cutoff, "high", fs=SR, output="sos"), x)


def bp(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return sosfilt(butter(2, [lo, hi], "band", fs=SR, output="sos"), x)


def saw(f: float, t: np.ndarray, harmonics: int = 10) -> np.ndarray:
    return sum(np.sin(2 * np.pi * f * k * t) / k for k in range(1, harmonics + 1)) * 0.6


def add(at: float, left: np.ndarray, right: np.ndarray | None = None) -> None:
    i = int(at * SR)
    if i >= N:
        return
    right = left if right is None else right
    n = min(len(left), N - i)
    L[i : i + n] += left[:n]
    R[i : i + n] += right[:n]


# ----------------------------------------------------------------------------- instruments
def pad(at: float, notes: list[str], dur: float, vol: float = 0.08, cutoff: float = 1800) -> None:
    t = t_arr(dur + 1.5)
    e = env(len(t), 0.6, 0.4, 0.8, 1.5)
    left = sum(saw(hz(n) * 0.997, t) for n in notes)
    right = sum(saw(hz(n) * 1.003, t) for n in notes)
    add(at, lp(left, cutoff) * e * vol, lp(right, cutoff) * e * vol)


def pluck(at: float, note: str, vol: float = 0.07, decay: float = 0.35, pan: float = 0.0) -> None:
    t = t_arr(decay * 4)
    f = hz(note)
    x = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t) + 0.12 * np.sin(2 * np.pi * 3 * f * t)) * np.exp(-t / decay)
    x = lp(x, 5000) * vol
    add(at, x * (1 - pan), x * (1 + pan))


def bass(at: float, note: str, dur: float, vol: float = 0.16) -> None:
    t = t_arr(dur)
    x = lp(saw(hz(note), t, 6), 400) * env(len(t), 0.01, 0.1, 0.7, 0.08) * vol
    add(at, x)


def kick(at: float, vol: float = 0.55) -> None:
    t = t_arr(0.45)
    f = 45 + 95 * np.exp(-t * 28)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7.5) * vol
    add(at, x)


def hat(at: float, vol: float = 0.05, open_: bool = False) -> None:
    t = t_arr(0.25 if open_ else 0.06)
    x = hp(rng.standard_normal(len(t)), 7000, 4) * np.exp(-t * (12 if open_ else 60)) * vol
    add(at, x * 0.8, x)


def clap(at: float, vol: float = 0.12) -> None:
    t = t_arr(0.3)
    burst = np.zeros(len(t))
    for k in range(3):
        i = int(k * 0.011 * SR)
        burst[i:] += np.exp(-t[: len(t) - i] * 40)
    x = bp(rng.standard_normal(len(t)), 900, 3500) * burst * vol
    add(at, x)


def impact(at: float, vol: float = 0.7) -> None:
    t = t_arr(4.0)
    boom = np.sin(2 * np.pi * (38 + 30 * np.exp(-t * 6)) * t) * np.exp(-t * 1.4)
    noise = lp(rng.standard_normal(len(t)), 900) * np.exp(-t * 2.2) * 0.4
    add(at, (boom + noise) * vol)


def riser(end: float, dur: float = 2.4, vol: float = 0.12) -> None:
    t = t_arr(dur)
    x = rng.standard_normal(len(t))
    out = np.zeros(len(t))
    chunks = 24
    for k in range(chunks):
        a, b = k * len(t) // chunks, (k + 1) * len(t) // chunks
        out[a:b] = bp(x[a:b], 300 + 5000 * (k / chunks) ** 2, 800 + 9000 * (k / chunks) ** 2)
    out *= np.linspace(0, 1, len(t)) ** 2 * vol
    add(end - dur, out)


def tick(at: float, vol: float = 0.05) -> None:
    t = t_arr(0.03)
    x = hp(rng.standard_normal(len(t)), 3000) * np.exp(-t * 200) * vol
    add(at, x)


def drone(at: float, dur: float, note: str = "A1", vol: float = 0.12) -> None:
    t = t_arr(dur)
    swell = 0.75 + 0.25 * np.sin(2 * np.pi * 0.12 * t)
    x = lp(saw(hz(note), t, 8), 320) * swell * env(len(t), 1.5, 0.5, 1.0, 1.5) * vol
    add(at, x)


# ----------------------------------------------------------------------------- arrangement
PROG_A = [["A3", "C4", "E4", "B4"], ["F3", "A3", "C4", "E4"], ["C3", "E3", "G3", "D4"], ["G3", "B3", "D4", "A4"]]
ROOTS_A = ["A1", "F1", "C2", "G1"]
PROG_B = [["F3", "A3", "C4", "G4"], ["G3", "B3", "D4", "A4"], ["A3", "C4", "E4", "B4"], ["C3", "E3", "G3", "E4"]]
ROOTS_B = ["F1", "G1", "A1", "C2"]


def section(start: float, end: float, prog, roots, kick_mode: str | None, arp: bool, bassline: bool, claps: bool, pad_vol=0.07):
    t = start
    bar = 0
    while t < end - 0.05:
        chord = prog[bar % len(prog)]
        pad(t, chord, min(BAR, end - t), vol=pad_vol)
        if bassline:
            for b in range(4):
                if t + b * BEAT < end:
                    bass(t + b * BEAT, roots[bar % len(roots)], BEAT * 0.9)
        for b in range(4):
            beat_t = t + b * BEAT
            if beat_t >= end:
                break
            if kick_mode == "half" and b in (0, 2):
                kick(beat_t, 0.42)
            if kick_mode == "four":
                kick(beat_t, 0.5)
            if kick_mode == "heart" and b in (0, 1):
                kick(beat_t + (0.18 if b == 1 else 0), 0.4)
            if claps and b in (1, 3):
                clap(beat_t)
            if kick_mode in ("half", "four"):
                hat(beat_t + BEAT / 2, 0.04)
        if arp:
            notes = chord + [chord[1].replace("3", "5").replace("4", "5")]
            for k in range(8):
                at = t + k * BEAT / 2
                if at < end:
                    pluck(at, notes[k % len(notes)], 0.05, 0.3, pan=0.3 if k % 2 else -0.3)
        t += BAR
        bar += 1


cold, logo = S["cold"], S["logo"]
drone(0.0, logo["start"] + 0.5, "A1", 0.13)
for k in range(int(logo["start"] / BEAT)):
    tick(k * BEAT, 0.035 + 0.02 * (k / (logo["start"] / BEAT)))
riser(logo["start"], 3.0, 0.14)
impact(logo["start"], 0.75)
pad(logo["start"], ["A2", "E3", "A3", "B3", "E4"], logo["length"], vol=0.08, cutoff=3200)
for k, n in enumerate(["E5", "A5", "B5", "E6"]):
    pluck(logo["start"] + 0.4 + k * 0.18, n, 0.05, 0.6, pan=0.4 * (-1) ** k)

section(S["idea"]["start"], S["how"]["start"], PROG_A, ROOTS_A, None, True, False, False)
section(S["how"]["start"], S["live"]["start"], PROG_A, ROOTS_A, "half", True, True, False)
riser(S["live"]["start"], 2.4)
section(S["live"]["start"], S["contain"]["start"], PROG_A, ROOTS_A, "four", True, True, True, pad_vol=0.06)
impact(S["contain"]["start"], 0.5)
drone(S["contain"]["start"], S["contain"]["length"], "A1", 0.12)
section(S["contain"]["start"], S["results"]["start"], [["A3", "C4", "E4"], ["D3", "F3", "A3"]], ["A1", "D1"], "heart", False, False, False, pad_vol=0.05)
riser(S["results"]["start"], 2.4, 0.14)
impact(S["results"]["start"], 0.45)
section(S["results"]["start"], S["vultr"]["start"], PROG_B, ROOTS_B, "four", True, True, True)
section(S["vultr"]["start"], S["close"]["start"], PROG_B, ROOTS_B, "half", True, True, False, pad_vol=0.06)
riser(S["close"]["start"], 2.0, 0.12)
impact(S["close"]["start"], 0.7)
pad(S["close"]["start"], ["A2", "E3", "A3", "C4", "E4", "B4"], S["close"]["length"] + 1.0, vol=0.09, cutoff=3500)
pluck(S["close"]["start"] + 0.2, "A5", 0.06, 1.2)
pluck(S["close"]["start"] + 0.5, "E6", 0.05, 1.2)

# ----------------------------------------------------------------------------- master
ir_t = t_arr(1.9)
ir = rng.standard_normal(len(ir_t)) * np.exp(-ir_t * 3.2)
ir /= np.abs(ir).sum() / 30
wetL = fftconvolve(L, ir)[:N] * 0.18
wetR = fftconvolve(R, ir[::-1].copy())[:N] * 0.18
mixL, mixR = L + wetL, R + wetR
fade = int(1.8 * SR)
for ch in (mixL, mixR):
    ch[-fade:] *= np.linspace(1, 0, fade)
peak = max(np.abs(mixL).max(), np.abs(mixR).max())
stereo = np.stack([mixL, mixR], axis=1) / peak * 0.89
pcm = (np.tanh(stereo * 1.1) / np.tanh(1.1) * 32767).astype(np.int16)
with wave.open("public/music.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print(f"music.wav: {TOTAL:.1f} s")
