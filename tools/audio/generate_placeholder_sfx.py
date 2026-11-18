"""Generates ORIGINAL placeholder sound effects (pure synthesis, no samples).

Run: python3 tools/audio/generate_placeholder_sfx.py audio/sfx
Every file is labelled placeholder_*.wav and must be replaced by final audio
(sound designer) before release — see LICENSES.md / assets/PLACEHOLDERS.md.
Deterministic (fixed random seed) so re-running produces identical files.
"""
import math
import random
import struct
import sys
import wave

RATE = 22050
rng = random.Random(1234)


def env(t, attack, decay):
    return min(1.0, t / attack) * math.exp(-t / decay) if attack > 0 else math.exp(-t / decay)


def noise_lp(n, alpha):
    out, y = [], 0.0
    for _ in range(n):
        y += alpha * (rng.uniform(-1, 1) - y)
        out.append(y)
    return out


def write(path, samples, gain=0.9):
    peak = max(1e-6, max(abs(s) for s in samples))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(s / peak * gain * 32767)) for s in samples))


def tone(freq_fn, dur, attack, decay, noise_mix=0.0, alpha=0.3):
    n = int(dur * RATE)
    nz = noise_lp(n, alpha) if noise_mix else [0.0] * n
    phase, out = 0.0, []
    for i in range(n):
        t = i / RATE
        phase += 2 * math.pi * freq_fn(t) / RATE
        out.append(env(t, attack, decay) * ((1 - noise_mix) * math.sin(phase) + noise_mix * nz[i] * 3))
    return out


def main(folder):
    sfx = {
        "placeholder_hit_light": tone(lambda t: 180 - 300 * t, 0.12, 0.002, 0.035, 0.6, 0.5),
        "placeholder_hit_heavy": tone(lambda t: 110 - 120 * t, 0.25, 0.003, 0.07, 0.55, 0.35),
        "placeholder_block": tone(lambda t: 900 + 200 * math.sin(t * 90), 0.10, 0.001, 0.025, 0.25, 0.8),
        "placeholder_whiff": tone(lambda t: 300, 0.16, 0.04, 0.05, 1.0, 0.08),
        "placeholder_special": tone(lambda t: 220 + 900 * t, 0.35, 0.02, 0.15, 0.3, 0.4),
        "placeholder_surge": tone(lambda t: 90 + 260 * t, 0.9, 0.15, 0.4, 0.35, 0.2),
        "placeholder_ultimate": tone(lambda t: 70 - 30 * t, 0.9, 0.005, 0.3, 0.6, 0.25),
        "placeholder_knockdown": tone(lambda t: 70, 0.4, 0.005, 0.12, 0.7, 0.15),
        "placeholder_ko": tone(lambda t: 55 - 20 * t, 1.1, 0.01, 0.45, 0.5, 0.15),
        "placeholder_ui_round": tone(lambda t: 660 if t < 0.08 else 880, 0.22, 0.005, 0.12),
    }
    for name, samples in sfx.items():
        write(f"{folder}/{name}.wav", samples)
        print("wrote", name, len(samples) / RATE, "s")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "audio/sfx")
