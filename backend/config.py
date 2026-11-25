from pathlib import Path


APP_DIR = Path.home() / ".tableta_sonidos"


SOUNDS_DIR = APP_DIR / "sonidos"


LIBRARY_FILE = APP_DIR / "biblioteca.json"


SETTINGS_FILE = APP_DIR / "config.json"


MAX_SECONDS = 20


MAX_SOURCE_SECONDS = 15 * 60


SAMPLE_RATE = 48000


AUDIO_VIDEO_FILTER = (
    "Audio y video (*.wav *.mp3 *.ogg *.flac *.m4a *.aac *.opus "
    "*.mp4 *.mkv *.mov *.avi *.webm *.3gp);;Todos los archivos (*)"
)
