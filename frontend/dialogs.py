import time

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QKeySequence
from PySide6.QtWidgets import (
    QComboBox, QDialog, QGridLayout, QHBoxLayout, QKeySequenceEdit, QLabel, QLineEdit,
    QMessageBox, QSlider, QVBoxLayout,
)

from backend.config import MAX_SECONDS, SAMPLE_RATE
from backend.hotkeys import ACTIONS, kb_to_qt, qt_to_kb
from frontend.theme import T
from frontend.widgets import CyberButton, WaveformView, single_chord


class TrimDialog(QDialog):
    def __init__(self, parent, src_name, data, suggested_name, preview_device):
        super().__init__(parent)
        self.setWindowTitle("Recortar audio")
        self.resize(780, 470)
        self.data = data
        self.preview_device = preview_device
        self._t0 = 0.0

        lay = QVBoxLayout(self)
        title = QLabel("RECORTAR AUDIO" if T["caps"] else "Recortar audio")
        tf = QFont(self.font())
        tf.setPointSize(15)
        tf.setBold(True)
        title.setFont(tf)
        title.setStyleSheet(f"color:{T['accent']};")
        lay.addWidget(title)
        lay.addWidget(QLabel(f"Archivo: {src_name}"))

        self.wave = WaveformView(data)
        self.wave.changed.connect(self._update_info)
        lay.addWidget(self.wave, 1)

        hint = QLabel("Arrastrá los bordes amarillos para recortar · arrastrá el centro "
                      "para mover · rueda: zoom · Shift + rueda: desplazar")
        hint.setStyleSheet(f"color:{T['muted']};")
        lay.addWidget(hint)

        row = QHBoxLayout()
        self.btn_play = CyberButton("▶  Escuchar")
        self.btn_play.clicked.connect(self.toggle_play)
        self.info = QLabel()
        row.addWidget(self.btn_play)
        row.addWidget(self.info, 1)
        row.addWidget(QLabel("Volumen:"))
        self.gain = QSlider(Qt.Horizontal)
        self.gain.setRange(0, 200)
        self.gain.setValue(100)
        self.gain.setFixedWidth(150)
        row.addWidget(self.gain)
        lay.addLayout(row)

        lay.addWidget(QLabel("Nombre del sonido:"))
        self.name = QLineEdit(suggested_name)
        self.name.textChanged.connect(self._update_info)
        lay.addWidget(self.name)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        btn_cancel = CyberButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        self.btn_save = CyberButton("Guardar", accent=True)
        self.btn_save.clicked.connect(self.accept)
        buttons.addWidget(btn_cancel)
        buttons.addWidget(self.btn_save)
        lay.addLayout(buttons)

        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._tick)
        self._update_info()

    def _update_info(self):
        length = self.wave.sel_end - self.wave.sel_start
        self.info.setText(f"Duración: {length:.2f} s / {MAX_SECONDS} s")
        self.btn_save.setEnabled(bool(self.name.text().strip()) and length > 0)

    def _segment(self):
        s = int(round(self.wave.sel_start * SAMPLE_RATE))
        e = int(round(self.wave.sel_end * SAMPLE_RATE))
        return self.data[s:e]

    def toggle_play(self):
        if self.timer.isActive():
            self._stop()
            return
        seg = np.clip(self._segment() * (self.gain.value() / 100), -1, 1)
        try:
            sd.play(seg, SAMPLE_RATE, device=self.preview_device)
        except Exception as e:
            QMessageBox.warning(self, "Error de audio", str(e))
            return
        self._t0 = time.monotonic()
        self.btn_play.setText("■  Detener")
        self.timer.start()

    def _tick(self):
        t = self.wave.sel_start + (time.monotonic() - self._t0)
        if t >= self.wave.sel_end:
            self._stop()
            return
        self.wave.playhead = t
        self.wave.update()

    def _stop(self):
        self.timer.stop()
        sd.stop()
        self.wave.playhead = None
        self.wave.update()
        self.btn_play.setText("▶  Escuchar")

    def done(self, result):
        self._stop()
        super().done(result)

    def result_sound(self):
        seg = np.clip(self._segment() * (self.gain.value() / 100), -1, 1)
        return self.name.text().strip(), seg.astype("float32")


class HotkeyDialog(QDialog):
    def __init__(self, parent, sound_name):
        super().__init__(parent)
        self.setWindowTitle("Asignar atajo")
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"Presioná la combinación de teclas para «{sound_name}»:"))
        self.edit = QKeySequenceEdit()
        try:
            self.edit.setMaximumSequenceLength(1)
        except AttributeError:
            pass
        lay.addWidget(self.edit)
        hint = QLabel("Conviene usar Ctrl / Alt / Shift para que no choque con lo que escribís "
                      "o con tus juegos. Dejalo vacío para quitar el atajo.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{T['muted']};")
        lay.addWidget(hint)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = CyberButton("Cancelar")
        cancel.clicked.connect(self.reject)
        ok = CyberButton("Aceptar", accent=True)
        ok.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)

    def combo(self):
        return qt_to_kb(self.edit.keySequence().toString())


class ShortcutsDialog(QDialog):

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        owner.hotkeys.paused = True
        self.setWindowTitle("Atajos de teclado")
        self.setMinimumWidth(600)
        lay = QVBoxLayout(self)

        title = QLabel("ATAJOS DE TECLADO" if T["caps"] else "Atajos de teclado")
        tf = QFont(self.font())
        tf.setPointSize(15)
        tf.setBold(True)
        title.setFont(tf)
        title.setStyleSheet(f"color:{T['accent']};")
        lay.addWidget(title)
        if not owner.hotkeys.available:
            warn = QLabel("Para usar atajos globales instalá:  pip install keyboard")
            warn.setStyleSheet(f"color:{T['highlight']};")
            lay.addWidget(warn)

        lay.addWidget(self._section("Acciones de la app"))
        grid = QGridLayout()
        self.edits = {}
        for row, (key, label) in enumerate(ACTIONS.items()):
            edit = QKeySequenceEdit()
            single_chord(edit)
            self.edits[key] = edit
            self._show_combo(edit, owner.settings.get("atajos", {}).get(key, ""))
            edit.editingFinished.connect(lambda k=key, e=edit: self._action_changed(k, e))
            clear = CyberButton("Quitar")
            clear.clicked.connect(lambda _=False, k=key, e=edit: self._action_clear(k, e))
            grid.addWidget(QLabel(label), row, 0)
            grid.addWidget(edit, row, 1)
            grid.addWidget(clear, row, 2)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)

        lay.addWidget(self._section("Sonido específico"))
        row = QHBoxLayout()
        self.combo_sound = QComboBox()
        for snd in owner.library:
            self.combo_sound.addItem(snd["name"], snd["id"])
        self.sound_edit = QKeySequenceEdit()
        single_chord(self.sound_edit)
        btn_assign = CyberButton("Asignar", accent=True)
        btn_assign.clicked.connect(self._assign)
        btn_remove = CyberButton("Quitar")
        btn_remove.clicked.connect(self._remove)
        self.combo_sound.currentIndexChanged.connect(self._load_sound_edit)
        row.addWidget(self.combo_sound, 2)
        row.addWidget(self.sound_edit, 1)
        row.addWidget(btn_assign)
        row.addWidget(btn_remove)
        lay.addLayout(row)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(f"color:{T['muted']};")
        lay.addWidget(self.summary)

        hint = QLabel("Elegí el sonido, hacé click en el recuadro de teclas y presioná la "
                      "combinación. Conviene usar Ctrl / Alt / Shift.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{T['muted']};")
        lay.addWidget(hint)

        done = CyberButton("Listo", accent=True)
        done.clicked.connect(self.accept)
        end = QHBoxLayout()
        end.addStretch(1)
        end.addWidget(done)
        lay.addLayout(end)
        self._load_sound_edit()
        self._refresh_summary()

    def _section(self, text):
        label = QLabel(text.upper() if T["caps"] else text)
        label.setStyleSheet(f"color:{T['accent2']}; font-weight:bold; padding-top:8px;")
        return label

    @staticmethod
    def _show_combo(edit, combo):
        edit.setKeySequence(QKeySequence(kb_to_qt(combo)) if combo else QKeySequence())


    def _action_changed(self, key, edit):
        combo = qt_to_kb(edit.keySequence().toString())
        error = self.owner.set_action_hotkey(key, combo)
        if error:
            QMessageBox.warning(self, "Atajo", error)
            self._show_combo(edit, self.owner.settings.get("atajos", {}).get(key, ""))

    def _action_clear(self, key, edit):
        self.owner.set_action_hotkey(key, "")
        edit.clear()


    def _current_sound(self):
        sid = self.combo_sound.currentData()
        return next((x for x in self.owner.library if x["id"] == sid), None)

    def _load_sound_edit(self):
        snd = self._current_sound()
        self._show_combo(self.sound_edit, snd.get("hotkey", "") if snd else "")

    def _assign(self):
        snd = self._current_sound()
        if not snd:
            return
        combo = qt_to_kb(self.sound_edit.keySequence().toString())
        if not combo:
            QMessageBox.information(self, "Atajo", "Presioná primero la combinación de teclas.")
            return
        error = self.owner.set_sound_hotkey(snd, combo)
        if error:
            QMessageBox.warning(self, "Atajo", error)
            self._load_sound_edit()
        self._refresh_summary()

    def _remove(self):
        snd = self._current_sound()
        if snd:
            self.owner.set_sound_hotkey(snd, "")
            self.sound_edit.clear()
            self._refresh_summary()

    def _refresh_summary(self):
        items = [f'{x["name"]} → {x["hotkey"].upper()}'
                 for x in self.owner.library if x.get("hotkey")]
        self.summary.setText("Sonidos con atajo:  " + "   ·   ".join(items) if items
                             else "Todavía no hay sonidos con atajo.")

    def done(self, result):
        self.owner.hotkeys.paused = False
        super().done(result)
