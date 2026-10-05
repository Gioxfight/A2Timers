"""Generate the built-in alert sounds: original synthesized WAVs, no third-party audio.

The "fantasy" set (harp, crystal, choir, temple, warhorn, fanfare) aims at an
orchestral / ethereal MMO feel; bell, gong, double and horn are the simple originals.
"""
import math
import random
import struct
import wave
from pathlib import Path

RATE = 44100
OUT = Path(__file__).resolve().parent.parent / "assets" / "sounds"


def note(name: str) -> float:
    """'A4' -> 440.0 (sharps only, e.g. 'C#5')."""
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    semitone = names.index(name[:-1]) + 12 * (int(name[-1]) + 1)
    return 440.0 * 2 ** ((semitone - 69) / 12)


def blank(seconds):
    return [0.0] * int(RATE * seconds)


def mix(track, sound, at_seconds, gain=1.0):
    start = int(at_seconds * RATE)
    if len(track) < start + len(sound):
        track.extend([0.0] * (start + len(sound) - len(track)))
    for i, value in enumerate(sound):
        track[start + i] += gain * value
    return track


def tone(partials, seconds, decay, attack=0.005, vibrato=0.0, vibrato_hz=5.0):
    """Sum of (freq, amplitude[, decay multiplier]) partials with exponential decay."""
    out = []
    phases = [0.0] * len(partials)
    for i in range(int(RATE * seconds)):
        t = i / RATE
        env = min(1.0, t / attack)
        wobble = 1.0 + vibrato * math.sin(2 * math.pi * vibrato_hz * t) * min(1.0, t / 0.3)
        value = 0.0
        for k, partial in enumerate(partials):
            freq, amp = partial[0], partial[1]
            partial_decay = decay * (partial[2] if len(partial) > 2 else 1.0)
            phases[k] += 2 * math.pi * freq * wobble / RATE
            value += amp * math.exp(-partial_decay * t) * math.sin(phases[k])
        out.append(env * value)
    return out


def pluck(freq, seconds, brightness=0.996, seed=1):
    """Karplus-Strong plucked string (harp-like)."""
    rng = random.Random(seed)
    period = max(2, int(RATE / freq))
    buf = [rng.uniform(-1, 1) for _ in range(period)]
    out = []
    for i in range(int(RATE * seconds)):
        value = buf[i % period]
        nxt = buf[(i + 1) % period]
        buf[i % period] = brightness * 0.5 * (value + nxt)
        out.append(value)
    return out


def reverb(samples, wet=0.35, tail=1.5):
    """Small Schroeder reverb: 4 parallel combs + 2 allpasses."""
    dry = samples + [0.0] * int(RATE * tail)
    combs = [(1557, 0.84), (1617, 0.83), (1491, 0.85), (1422, 0.86)]
    acc = [0.0] * len(dry)
    for delay, feedback in combs:
        buf = [0.0] * delay
        for i, x in enumerate(dry):
            y = buf[i % delay]
            buf[i % delay] = x + feedback * y
            acc[i] += y / len(combs)
    for delay, gain in ((225, 0.5), (556, 0.5)):
        buf = [0.0] * delay
        for i, x in enumerate(acc):
            b = buf[i % delay]
            y = -gain * x + b
            buf[i % delay] = x + gain * y
            acc[i] = y
    return [d * (1 - wet) + w * wet for d, w in zip(dry, acc)]


def fade_out(samples, seconds=0.25):
    n = min(len(samples), int(RATE * seconds))
    for i in range(n):
        samples[-n + i] *= 1 - i / n
    return samples


def brass(freq, seconds, glide=0.0):
    """Bright brass-like tone: rolled-off harmonics, swell, vibrato, optional upward glide."""
    out, phase = [], 0.0
    harmonics = [(n, 1.0 / n ** 1.3) for n in range(1, 12)]
    for i in range(int(RATE * seconds)):
        t = i / RATE
        f = freq * (1 - glide * math.exp(-t / 0.08))
        f *= 1 + 0.006 * math.sin(2 * math.pi * 5.5 * t) * min(1.0, t / 0.4)
        phase += 2 * math.pi * f / RATE
        env = min(1.0, t / 0.07) * (0.85 + 0.15 * min(1.0, t / 0.3)) * min(1.0, (seconds - t) / 0.12)
        out.append(env * sum(a * math.sin(n * phase) for n, a in harmonics))
    return out


def write(name, samples):
    peak = max(abs(s) for s in samples) or 1.0
    scale = 0.89 * 32767 / peak
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(s * scale)) for s in samples))


def harp():
    """Rising pentatonic arpeggio, like a celestial harp."""
    track = []
    for k, name in enumerate(["D5", "E5", "A5", "B5", "D6", "E6"]):
        mix(track, pluck(note(name), 1.6, seed=k + 1), k * 0.075, gain=1.0 - k * 0.06)
    return fade_out(reverb(track, wet=0.4, tail=1.2), 0.5)


def crystal():
    """Two shimmering glass-bell strikes (inharmonic partials)."""
    def strike(f):
        return tone([(f, 1.0), (f * 2.76, 0.5, 1.6), (f * 5.40, 0.25, 2.4), (f * 8.93, 0.12, 3.2)],
                    1.8, decay=3.0, attack=0.002)
    track = mix([], strike(note("E6")), 0.0)
    mix(track, strike(note("B6")), 0.16, gain=0.8)
    return fade_out(reverb(track, wet=0.45, tail=1.4), 0.5)


def choir():
    """Soft 'aah' chord swelling in, like a distant choir."""
    track = []
    for name, gain in (("A3", 0.9), ("E4", 0.8), ("A4", 0.7), ("C#5", 0.6), ("E5", 0.4)):
        f = note(name)
        # Vowel-ish spectrum: strong 2nd-4th harmonics, gentle rolloff.
        voice = tone([(f, 0.6), (f * 2, 0.9), (f * 3, 0.7), (f * 4, 0.45), (f * 5, 0.2), (f * 6, 0.12)],
                     1.9, decay=0.9, attack=0.35, vibrato=0.004, vibrato_hz=4.8 + gain)
        mix(track, voice, 0.0, gain)
    return fade_out(reverb(track, wet=0.5, tail=1.5), 0.8)


def temple():
    """Deep temple bell with long, beating decay."""
    f = note("A2")
    ratios = [(0.5, 0.6, 0.5), (1.0, 1.0), (1.19, 0.5, 1.3), (1.56, 0.45, 1.6), (2.0, 0.4, 1.8),
              (2.74, 0.25, 2.5), (3.0, 0.2, 2.8), (4.07, 0.12, 3.5), (1.005, 0.6)]
    bell = tone([(f * r[0], *r[1:]) for r in ratios], 3.2, decay=1.1, attack=0.004)
    return fade_out(reverb(bell, wet=0.3, tail=1.0), 0.8)


def warhorn():
    """Two-note war horn call (low, then a fifth up)."""
    track = mix([], brass(note("D3"), 0.75, glide=0.08), 0.0)
    mix(track, brass(note("A3"), 1.1, glide=0.05), 0.68)
    return fade_out(reverb(track, wet=0.35, tail=1.0), 0.5)


def fanfare():
    """Short heroic brass fanfare: G-C-E, last note held."""
    track = []
    for at, name, length in ((0.0, "G4", 0.16), (0.17, "C5", 0.16), (0.34, "E5", 0.8)):
        mix(track, brass(note(name), length, glide=0.03), at)
    return fade_out(reverb(track, wet=0.3, tail=0.9), 0.4)


def classic():
    """The original simple set (kept so existing settings keep working)."""
    write("bell", tone([(880, 1.0), (1760, 0.4), (2640, 0.2), (3520, 0.1)], 1.2, decay=4.0))
    write("gong", tone([(130, 1.0), (196, 0.7), (261, 0.5), (347, 0.35), (523, 0.2)], 2.2, decay=1.6, attack=0.02))
    beep = tone([(1046, 1.0), (2093, 0.25)], 0.14, decay=6.0, attack=0.003)
    write("double", beep + blank(0.08) + beep)
    write("horn", tone([(440 * n, 1.0 / n) for n in range(1, 8)], 0.9, decay=2.0, attack=0.06))


def main():
    for name, make in (("harp", harp), ("crystal", crystal), ("choir", choir),
                       ("temple", temple), ("warhorn", warhorn), ("fanfare", fanfare)):
        write(name, make())
    classic()
    print(f"Sounds written to {OUT}")


if __name__ == "__main__":
    main()
