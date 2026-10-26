"""Audio loudness over time, for the speaking goop's mouth bar. Stdlib only (int16 mono PCM bytes in)."""
import array, math

REF_RMS = 0.18   # speech at this loudness fills the bar


def envelope(pcm, sample_rate, hz=30):
    """Per-frame levels in 0..1, one every 1/hz seconds."""
    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) // 2 * 2])
    step = max(1, sample_rate // hz)
    out = []
    for i in range(0, len(samples), step):
        frame = samples[i:i + step]
        rms = math.sqrt(sum(s * s for s in frame) / len(frame)) / 32768.0
        out.append(min(1.0, (rms / REF_RMS) ** 0.8))
    return out
