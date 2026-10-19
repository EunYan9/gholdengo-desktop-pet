"""Generate our own short two-note completion sound (no external recording)."""
import math
from pathlib import Path
import struct
import wave


def generate(path):
    rate = 44100
    samples = []
    duration = .72
    for index in range(round(rate*duration)):
        t = index/rate
        value = 0.
        for began, frequency, gain in ((0., 880., .23), (.19, 1318.51, .18)):
            age = t-began
            if age < 0:
                continue
            envelope = (1-math.exp(-age/0.004))*math.exp(-age/0.15)
            partials = (math.sin(2*math.pi*frequency*age)
                        + .16*math.sin(2*math.pi*frequency*2*age)*math.exp(-age/.06))
            value += gain*envelope*partials
        value *= min(1., (duration-t)/.05)
        samples.append(struct.pack('<h', round(max(-1., min(1., value))*32767)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(rate)
        stream.writeframes(b''.join(samples))


if __name__ == '__main__':
    generate(Path(__file__).resolve().parent/'sounds'/'task-complete.wav')
