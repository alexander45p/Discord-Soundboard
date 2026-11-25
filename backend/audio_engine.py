import threading

import numpy as np
import sounddevice as sd

from backend.audio_decoder import decode_audio
from backend.config import SAMPLE_RATE


def _wasapi_extra(dev):
    try:
        api = sd.query_hostapis(sd.query_devices(dev)["hostapi"])["name"]
        if "WASAPI" in api:
            return sd.WasapiSettings(auto_convert=True)
    except Exception:
        pass
    return None


class RingBuffer:

    def __init__(self, capacity=SAMPLE_RATE, max_latency=0.15):
        self.buf = np.zeros(capacity, dtype=np.float32)
        self.cap = capacity
        self.max_latency = int(max_latency * SAMPLE_RATE)
        self.r = self.w = self.count = 0
        self.lock = threading.Lock()

    def write(self, x):
        with self.lock:
            if len(x) >= self.cap:
                x = x[-self.cap:]
            n = len(x)
            self.buf[(self.w + np.arange(n)) % self.cap] = x
            self.w = (self.w + n) % self.cap
            self.count = min(self.cap, self.count + n)
            if self.count > self.max_latency:
                drop = self.count - self.max_latency
                self.r = (self.r + drop) % self.cap
                self.count -= drop

    def read(self, n):
        out = np.zeros(n, dtype=np.float32)
        with self.lock:
            m = min(n, self.count)
            if m:
                out[:m] = self.buf[(self.r + np.arange(m)) % self.cap]
                self.r = (self.r + m) % self.cap
                self.count -= m
        return out


class AudioEngine:

    def __init__(self):
        self.lock = threading.Lock()
        self.volume = 1.0
        self.streams = {}
        self.voices = {}
        self.cache = {}
        self.cable_dev = None
        self.cable_peak = 0.0
        self.mic_stream = None
        self.mic_ring = RingBuffer()
        self.mic_gain = 1.0
        self.mic_enabled = True

    def load(self, path):
        path = str(path)
        if path not in self.cache:
            self.cache[path] = decode_audio(path)
        return self.cache[path]

    def forget(self, path):
        self.cache.pop(str(path), None)


    def set_devices(self, cable, monitor):
        errors = []
        self.cable_dev = cable
        wanted = set(d for d in (cable, monitor) if d is not None)
        for dev in list(self.streams):
            if dev not in wanted:
                self._close(dev)
        for dev in wanted:
            if dev in self.streams:
                continue
            try:
                stream = sd.OutputStream(
                    samplerate=SAMPLE_RATE, channels=2, dtype="float32",
                    device=dev, latency="low", callback=self._make_callback(dev),
                    extra_settings=_wasapi_extra(dev),
                )
                stream.start()
                self.streams[dev] = stream
                self.voices[dev] = []
            except Exception as e:
                errors.append(f"{sd.query_devices(dev)['name']}: {e}")
        return errors

    def _close(self, dev):
        stream = self.streams.pop(dev, None)
        if stream:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        with self.lock:
            self.voices.pop(dev, None)


    def set_mic(self, dev):
        if self.mic_stream is not None:
            try:
                self.mic_stream.stop()
                self.mic_stream.close()
            except Exception:
                pass
            self.mic_stream = None
        if dev is None:
            return []
        last_error = None
        for channels in (1, 2):
            try:
                stream = sd.InputStream(
                    samplerate=SAMPLE_RATE, channels=channels, dtype="float32",
                    device=dev, latency="low", callback=self._mic_callback,
                    extra_settings=_wasapi_extra(dev),
                )
                stream.start()
                self.mic_stream = stream
                return []
            except Exception as e:
                last_error = e
        return [f"{sd.query_devices(dev)['name']}: {last_error}"]

    def _mic_callback(self, indata, frames, time_info, status):
        self.mic_ring.write(indata.mean(axis=1))


    def _make_callback(self, dev):
        def callback(outdata, frames, time_info, status):
            outdata.fill(0)
            with self.lock:
                voices = self.voices.get(dev, [])
                for voice in voices[:]:
                    data, pos = voice
                    chunk = data[pos:pos + frames]
                    outdata[:len(chunk)] += chunk * self.volume
                    voice[1] += frames
                    if voice[1] >= len(data):
                        voices.remove(voice)
            if dev == self.cable_dev and self.mic_stream is not None:
                mic = self.mic_ring.read(frames)
                if self.mic_enabled:
                    mic = mic * self.mic_gain
                    outdata[:, 0] += mic
                    outdata[:, 1] += mic
            np.clip(outdata, -1.0, 1.0, out=outdata)
            if dev == self.cable_dev:
                self.cable_peak = max(self.cable_peak, float(np.abs(outdata).max()))
        return callback

    def play(self, data):
        with self.lock:
            for dev in self.streams:
                self.voices[dev].append([data, 0])

    def stop_all(self):
        with self.lock:
            for dev in self.voices:
                self.voices[dev].clear()

    def shutdown(self):
        self.set_mic(None)
        for dev in list(self.streams):
            self._close(dev)
