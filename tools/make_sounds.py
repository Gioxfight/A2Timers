"""Generate the built-in alert sounds (original synthesized WAVs, no third-party audio)."""
import math
import struct
import wave
from pathlib import Path

RATE = 44100
OUT = Path(__file__).resolve().parent.parent / "assets" / "sounds"


def tone(freqs, seconds, decay, attack=0.005, volume=0.6):
    """Sum of partials [(freq, amplitude)] with exponential decay."""
    samples = []
    for i in range(int(RATE * seconds)):
        t = i / RATE
        env = min(1.0, t / attack) * math.exp(-decay * t)
        samples.append(volume * env * sum(a * math.sin(2 * math.pi * f * t) for f, a in freqs))
    return samples


def silence(seconds):
    return [0.0] * int(RATE * seconds)


def write(name, samples):
    peak = max(abs(s) for s in samples) or 1.0
    scale = 0.9 * 32767 / peak
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(s * scale)) for s in samples))


def main():
    write("bell", tone([(880, 1.0), (1760, 0.4), (2640, 0.2), (3520, 0.1)], 1.2, decay=4.0))
    write("gong", tone([(130, 1.0), (196, 0.7), (261, 0.5), (347, 0.35), (523, 0.2)], 2.2, decay=1.6, attack=0.02))
    beep = tone([(1046, 1.0), (2093, 0.25)], 0.14, decay=6.0, attack=0.003)
    write("double", beep + silence(0.08) + beep)
    write("horn", tone([(440 * n, 1.0 / n) for n in range(1, 8)], 0.9, decay=2.0, attack=0.06))
    print(f"Sounds written to {OUT}")


if __name__ == "__main__":
    main()
