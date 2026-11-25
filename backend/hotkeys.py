from PySide6.QtCore import QObject, Signal


_QT_TO_KB = {
    "Ctrl": "ctrl", "Alt": "alt", "Shift": "shift", "Meta": "windows",
    "PgUp": "page up", "PgDown": "page down", "Del": "delete", "Ins": "insert",
    "Return": "enter", "Enter": "enter", "Esc": "esc", "Space": "space",
    "Backspace": "backspace", "Tab": "tab", "Home": "home", "End": "end",
    "Up": "up", "Down": "down", "Left": "left", "Right": "right",
}


def qt_to_kb(sequence):
    first = sequence.split(",")[0].strip()
    parts = [x.strip() for x in first.split("+") if x.strip()]
    return "+".join(_QT_TO_KB.get(x, x.lower()) for x in parts)


ACTIONS = {
    "add": "Agregar audio",
    "stop": "Detener todo",
    "toggle": "Mostrar / ocultar la app",
    "quit": "Cerrar la app",
}


_KB_TO_QT = {v: k for k, v in _QT_TO_KB.items()}


def kb_to_qt(combo):
    return "+".join(
        _KB_TO_QT.get(x, x.upper() if len(x) <= 2 else x.title()) for x in combo.split("+")
    )


class HotkeyManager(QObject):
    triggered = Signal(str)

    def __init__(self):
        super().__init__()
        self.handles = {}
        self.paused = False
        try:
            import keyboard
            self.kb = keyboard
        except Exception:
            self.kb = None

    @property
    def available(self):
        return self.kb is not None

    def register(self, sound_id, combo):
        if not self.available:
            return "Falta la librería keyboard (pip install keyboard)."
        self.unregister(sound_id)
        try:
            self.handles[sound_id] = self.kb.add_hotkey(
                combo, lambda sid=sound_id: self._fire(sid)
            )
        except Exception as e:
            return str(e)
        return None

    def _fire(self, key):
        if not self.paused:
            self.triggered.emit(key)

    def unregister(self, sound_id):
        handle = self.handles.pop(sound_id, None)
        if handle is not None and self.kb:
            try:
                self.kb.remove_hotkey(handle)
            except Exception:
                pass

    def clear(self):
        for sid in list(self.handles):
            self.unregister(sid)
