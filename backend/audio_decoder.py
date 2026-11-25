import numpy as np
import soundfile as sf

from backend.config import MAX_SOURCE_SECONDS, SAMPLE_RATE


class TooLong(Exception):
    pass


def _resample(data, sr):
    if sr == SAMPLE_RATE:
        return data
    n_new = int(len(data) * SAMPLE_RATE / sr)
    x_old = np.linspace(0, 1, len(data), endpoint=False)
    x_new = np.linspace(0, 1, n_new, endpoint=False)
    return np.stack(
        [np.interp(x_new, x_old, data[:, c]) for c in range(data.shape[1])], axis=1
    ).astype("float32")


def _to_stereo(data):
    if data.shape[1] == 1:
        return np.repeat(data, 2, axis=1)
    return data[:, :2]


def _decode_av(path, max_seconds):
    import av

    chunks = []
    with av.open(path) as container:
        streams = [s for s in container.streams if s.type == "audio"]
        if not streams:
            raise ValueError("El archivo no tiene pista de audio.")
        if container.duration and container.duration / av.time_base > max_seconds:
            raise TooLong()
        resampler = av.AudioResampler(format="flt", layout="stereo", rate=SAMPLE_RATE)

        def collect(out):
            if out is None:
                return
            for frame in (out if isinstance(out, list) else [out]):
                chunks.append(frame.to_ndarray().reshape(-1, 2).astype("float32"))

        for frame in container.decode(streams[0]):
            collect(resampler.resample(frame))
        collect(resampler.resample(None))
    if not chunks:
        raise ValueError("No se pudo leer el audio del archivo.")
    return np.concatenate(chunks)


def decode_audio(path, max_seconds=MAX_SOURCE_SECONDS):
    path = str(path)
    try:
        if sf.info(path).duration > max_seconds:
            raise TooLong()
        data, sr = sf.read(path, dtype="float32", always_2d=True)
        return _resample(_to_stereo(data), sr)
    except TooLong:
        raise
    except Exception:
        return _decode_av(path, max_seconds)
