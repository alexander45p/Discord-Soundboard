import uuid
from pathlib import Path

import sounddevice as sd
import soundfile as sf
from PySide6.QtCore import QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QGridLayout, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QScrollArea,
    QSlider, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from backend.audio_decoder import TooLong, decode_audio
from backend.audio_engine import AudioEngine
from backend.config import (
    AUDIO_VIDEO_FILTER, LIBRARY_FILE, MAX_SOURCE_SECONDS, SAMPLE_RATE, SETTINGS_FILE,
    SOUNDS_DIR,
)
from backend.devices import input_devices, output_devices
from backend.hotkeys import ACTIONS, HotkeyManager
from backend.storage import load_json, save_json
from frontend.constants import BTN_W, SPACING
from frontend.dialogs import HotkeyDialog, ShortcutsDialog, TrimDialog
from frontend.theme import T, THEMES, build_qss, chamfer_path
from frontend.widgets import ChamferPanel, CyberButton, LevelMeter, SoundButton


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tableta de sonidos")
        self.resize(900, 620)

        SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
        self.engine = AudioEngine()
        self.library = load_json(LIBRARY_FILE, [])
        self.settings = load_json(SETTINGS_FILE, {})
        self.buttons = []
        self.hotkeys = HotkeyManager()
        self.hotkeys.triggered.connect(self._hotkey_pressed)

        self._build_ui()
        for sound in self.library:
            self._create_button(sound)
        self.relayout()
        self._apply_devices(initial=True)
        self._apply_mic(initial=True)
        self._register_saved_hotkeys()
        self._setup_tray()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(10)


        head = QHBoxLayout()
        self.title = QLabel()
        f = QFont(self.font())
        f.setPointSize(18)
        f.setBold(True)
        self.title.setFont(f)
        self.subtitle = QLabel()
        head.addWidget(self.title)
        head.addWidget(self.subtitle)
        head.addStretch(1)
        head.addWidget(QLabel("Tema:"))
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(list(THEMES))
        self.combo_theme.setCurrentText(self.settings.get("tema", "Cyberpunk"))
        self.combo_theme.currentTextChanged.connect(self.set_theme)
        head.addWidget(self.combo_theme)
        layout.addLayout(head)


        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar audio por nombre...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.relayout)
        btn_add = CyberButton("＋ Agregar audio / video", accent=True)
        btn_add.clicked.connect(self.add_sounds)
        btn_stop = CyberButton("■ Detener todo")
        btn_stop.clicked.connect(self.engine.stop_all)
        top.addWidget(self.search, 1)
        top.addWidget(btn_add)
        top.addWidget(btn_stop)
        btn_keys = CyberButton("⌨ Atajos")
        btn_keys.clicked.connect(self.open_shortcuts)
        top.addWidget(btn_keys)
        layout.addLayout(top)


        dev_row = QHBoxLayout()
        self.combo_cable = QComboBox()
        self.combo_monitor = QComboBox()
        devices = output_devices()
        for combo in (self.combo_cable, self.combo_monitor):
            combo.addItem("— ninguna —", None)
            for idx, label in devices:
                combo.addItem(label, idx)
            combo.setMinimumWidth(160)
        self._restore_combo(self.combo_cable, self.settings.get("cable"))
        self._restore_combo(self.combo_monitor, self.settings.get("monitor"))
        for combo in (self.combo_cable, self.combo_monitor):
            combo.currentIndexChanged.connect(self._apply_devices)

        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(int(self.settings.get("volume", 100)))
        self.volume.valueChanged.connect(self._volume_changed)
        self.engine.volume = self.volume.value() / 100

        dev_row.addWidget(QLabel("Salida 1 (cable virtual):"))
        dev_row.addWidget(self.combo_cable, 1)
        dev_row.addWidget(QLabel("Salida 2 (auriculares):"))
        dev_row.addWidget(self.combo_monitor, 1)
        dev_row.addWidget(QLabel("Vol:"))
        dev_row.addWidget(self.volume)
        layout.addLayout(dev_row)


        mic_row = QHBoxLayout()
        self.combo_mic = QComboBox()
        self.combo_mic.addItem("— ninguno —", None)
        for idx, label in input_devices():
            self.combo_mic.addItem(label, idx)
        self.combo_mic.setMinimumWidth(160)
        self._restore_combo(self.combo_mic, self.settings.get("mic"))
        self.combo_mic.currentIndexChanged.connect(self._apply_mic)
        self.btn_mic = CyberButton("")
        self.btn_mic.clicked.connect(self._toggle_mic)
        self.mic_vol = QSlider(Qt.Horizontal)
        self.mic_vol.setRange(0, 200)
        self.mic_vol.setValue(int(self.settings.get("mic_vol", 100)))
        self.mic_vol.valueChanged.connect(self._mic_volume_changed)
        self.engine.mic_gain = self.mic_vol.value() / 100
        self.engine.mic_enabled = bool(self.settings.get("mic_on", True))
        self._refresh_mic_button()
        mic_row.addWidget(QLabel("Micrófono real:"))
        mic_row.addWidget(self.combo_mic, 1)
        mic_row.addWidget(self.btn_mic)
        mic_row.addWidget(QLabel("Vol mic:"))
        mic_row.addWidget(self.mic_vol)
        layout.addLayout(mic_row)


        lvl_row = QHBoxLayout()
        self.meter = LevelMeter()
        self._lvl = 0.0
        lvl_row.addWidget(QLabel("Hacia Discord (Salida 1):"))
        lvl_row.addWidget(self.meter, 1)
        layout.addLayout(lvl_row)
        self.lvl_hint = QLabel(
            "Si la barra se mueve al tocar un botón, el audio está llegando al cable. "
            "En Discord (Ajustes de voz): entrada = CABLE Output, desactivá la supresión "
            "de ruido y usá «Detección de voz» (no «Pulsar para hablar»)."
        )
        self.lvl_hint.setWordWrap(True)
        self.lvl_hint.setStyleSheet(f"color:{T['muted']};")
        layout.addWidget(self.lvl_hint)
        self.meter_timer = QTimer(self)
        self.meter_timer.setInterval(40)
        self.meter_timer.timeout.connect(self._update_meter)
        self.meter_timer.start()


        self.panel = ChamferPanel("Sonidos")
        self.empty_label = QLabel()
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.panel.body.addWidget(self.empty_label)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        container = QWidget()
        container.setObjectName("gridHost")
        self.grid = QGridLayout(container)
        self.grid.setSpacing(SPACING)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.scroll.setWidget(container)
        self.panel.body.addWidget(self.scroll, 1)
        layout.addWidget(self.panel, 1)

        self._refresh_header()

    def _refresh_header(self):
        self.title.setText("TABLETA DE SONIDOS" if T["caps"] else "Tableta de sonidos")
        self.title.setStyleSheet(f"color:{T['accent']};")
        self.subtitle.setText("// SOUNDBOARD" if T["caps"] else "soundboard")
        self.subtitle.setStyleSheet(f"color:{T['accent2']}; padding-top:8px;")
        self.empty_label.setStyleSheet(f"color:{T['muted']};")

    def set_theme(self, name):
        T.clear()
        T.update(THEMES.get(name, THEMES["Cyberpunk"]))
        QApplication.instance().setStyleSheet(build_qss(T))
        self._refresh_header()
        for w in self.findChildren(QWidget):
            w.update()
        self.settings["tema"] = name
        save_json(SETTINGS_FILE, self.settings)

    def _restore_combo(self, combo, saved_name):
        if saved_name:
            i = combo.findText(saved_name)
            if i >= 0:
                combo.setCurrentIndex(i)


    def _apply_devices(self, *_args, initial=False):
        if initial:


            cable_words = ("cable input", "vb-audio", "virtual cable")
            current_cable_name = self.combo_cable.currentText().lower()
            current_is_cable = any(word in current_cable_name for word in cable_words)
            candidates = []
            try:
                hostapis = sd.query_hostapis()
                for idx, label in output_devices():
                    low = label.lower()
                    if any(word in low for word in cable_words):
                        api_name = hostapis[sd.query_devices(idx)["hostapi"]]["name"].lower()
                        candidates.append((0 if "wasapi" in api_name else 1, idx))
            except Exception:
                candidates = []
            if not current_is_cable:
                self.combo_cable.blockSignals(True)
                if candidates:
                    candidates.sort()
                    cable_index = self.combo_cable.findData(candidates[0][1])
                    if cable_index >= 0:
                        self.combo_cable.setCurrentIndex(cable_index)
                else:

                    self.combo_cable.setCurrentIndex(0)
                self.combo_cable.blockSignals(False)

            if self.combo_monitor.currentData() is None or (
                self.combo_monitor.currentData() == self.combo_cable.currentData()
            ):
                try:
                    default_output = sd.default.device[1]
                    monitor_index = self.combo_monitor.findData(default_output)
                    if default_output == self.combo_cable.currentData() or monitor_index < 0:
                        monitor_index = next(
                            (self.combo_monitor.findData(idx) for idx, _ in output_devices()
                             if idx != self.combo_cable.currentData()), -1
                        )
                    if monitor_index >= 0:
                        self.combo_monitor.blockSignals(True)
                        self.combo_monitor.setCurrentIndex(monitor_index)
                        self.combo_monitor.blockSignals(False)
                except Exception:
                    pass
        errors = self.engine.set_devices(
            self.combo_cable.currentData(), self.combo_monitor.currentData()
        )
        self.settings["cable"] = self.combo_cable.currentText()
        self.settings["monitor"] = self.combo_monitor.currentText()
        save_json(SETTINGS_FILE, self.settings)
        if errors:
            QMessageBox.warning(self, "Error de audio", "\n".join(errors))
        elif self.combo_cable.currentData() is None:
            self.lvl_hint.setText(
                "No se detectó un cable virtual. Instalá VB-CABLE y reiniciá la app. "
                "Después elegí CABLE Input en Salida 1 y CABLE Output como entrada en Discord."
            )
        else:
            self.lvl_hint.setText(
                "Salida 1 envía los sonidos y el micrófono a Discord. En Discord elegí "
                "CABLE Output como entrada y usá Detección de voz."
            )

    def _volume_changed(self, value):
        self.engine.volume = value / 100
        self.settings["volume"] = value
        save_json(SETTINGS_FILE, self.settings)


    def _apply_mic(self, *_args, initial=False):
        if initial and "mic" not in self.settings:
            try:
                i = self.combo_mic.findData(sd.default.device[0])
                if i >= 0:
                    self.combo_mic.setCurrentIndex(i)
                    return
            except Exception:
                pass
        errors = self.engine.set_mic(self.combo_mic.currentData())
        self.settings["mic"] = self.combo_mic.currentText()
        save_json(SETTINGS_FILE, self.settings)
        if errors:
            QMessageBox.warning(self, "Error de micrófono", "\n".join(errors))

    def _toggle_mic(self):
        self.engine.mic_enabled = not self.engine.mic_enabled
        self.settings["mic_on"] = self.engine.mic_enabled
        save_json(SETTINGS_FILE, self.settings)
        self._refresh_mic_button()

    def _refresh_mic_button(self):
        on = self.engine.mic_enabled
        self.btn_mic.setText("Mic: ON" if on else "Mic: OFF (silenciado)")
        self.btn_mic.accent = on
        self.btn_mic.update()

    def _mic_volume_changed(self, value):
        self.engine.mic_gain = value / 100
        self.settings["mic_vol"] = value
        save_json(SETTINGS_FILE, self.settings)


    def _create_button(self, sound):
        btn = SoundButton(sound, self.play, self.rename, self.delete,
                          self.assign_hotkey, self.clear_hotkey)
        btn.refresh()
        self.buttons.append(btn)
        return btn

    def relayout(self, *_args):
        if not hasattr(self, "grid"):
            return
        query = self.search.text().strip().lower()
        while self.grid.count():
            self.grid.takeAt(0)
        visible = [b for b in self.buttons if query in b.sound["name"].lower()]
        for b in self.buttons:
            b.setVisible(b in visible)
        cols = max(1, (self.scroll.viewport().width() - 10) // (BTN_W + SPACING))
        for i, b in enumerate(visible):
            self.grid.addWidget(b, i // cols, i % cols)

        if not self.buttons:
            self.empty_label.setText("Todavía no hay audios. Usá «Agregar audio / video».")
        elif not visible:
            self.empty_label.setText("Ningún audio coincide con la búsqueda.")
        else:
            self.empty_label.setText("")
        self.empty_label.setVisible(bool(self.empty_label.text()))
        self.panel.set_right_text(f"{len(self.buttons)} / ∞")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.relayout()


    def confirm(self, title, text, ok_text="Aceptar"):
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        box.setIcon(QMessageBox.Question)
        ok = box.addButton(ok_text, QMessageBox.AcceptRole)
        box.addButton("Cancelar", QMessageBox.RejectRole)
        box.setDefaultButton(ok)
        box.exec()
        return box.clickedButton() is ok

    def play(self, btn):
        try:
            data = self.engine.load(SOUNDS_DIR / btn.sound["file"])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo reproducir el audio:\n{e}")
            return
        if not self.engine.streams:
            QMessageBox.information(
                self, "Sin salida",
                "Elegí al menos una salida de audio (cable virtual o auriculares).",
            )
            return
        self.engine.play(data)

    def add_sounds(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Elegir audio o video", "", AUDIO_VIDEO_FILTER
        )
        for p in paths:
            src = Path(p)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                data = decode_audio(src)
            except TooLong:
                QApplication.restoreOverrideCursor()
                QMessageBox.warning(
                    self, "Archivo demasiado largo",
                    f"«{src.name}» dura más de {MAX_SOURCE_SECONDS // 60} minutos.",
                )
                continue
            except ImportError:
                QApplication.restoreOverrideCursor()
                QMessageBox.warning(
                    self, "Falta una librería",
                    "Para leer videos y otros formatos instalá:  pip install av",
                )
                continue
            except Exception as e:
                QApplication.restoreOverrideCursor()
                QMessageBox.warning(self, "Error", f"No se pudo leer «{src.name}»:\n{e}")
                continue
            QApplication.restoreOverrideCursor()

            dlg = TrimDialog(self, src.name, data, src.stem, self.combo_monitor.currentData())
            if dlg.exec() != QDialog.Accepted:
                continue
            name, seg = dlg.result_sound()
            if not self.confirm(
                "Confirmar",
                f"¿Agregar «{name}» ({len(seg) / SAMPLE_RATE:.1f} s) a la tableta?",
                "Sí, agregar",
            ):
                continue
            file_name = f"{uuid.uuid4().hex}.wav"
            sf.write(str(SOUNDS_DIR / file_name), seg, SAMPLE_RATE, subtype="PCM_16")
            sound = {"id": uuid.uuid4().hex, "name": name, "file": file_name,
                     "duration": len(seg) / SAMPLE_RATE}
            self.library.append(sound)
            self._create_button(sound)
        save_json(LIBRARY_FILE, self.library)
        self.relayout()


    def _setup_tray(self):
        self.tray = None
        pm = QPixmap(64, 64)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        path = chamfer_path(QRectF(4, 4, 56, 56), 14)
        p.fillPath(path, QColor("#0a0608"))
        p.setPen(QPen(QColor("#ff3b4e"), 4))
        p.drawPath(path)
        p.setPen(QColor("#35e0e6"))
        f = QFont("Bahnschrift", 24)
        f.setBold(True)
        p.setFont(f)
        p.drawText(pm.rect(), Qt.AlignCenter, "TS")
        p.end()
        icon = QIcon(pm)
        self.setWindowIcon(icon)
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("Tableta de sonidos")
        self._tray_menu = QMenu()
        self._tray_menu.addAction("Mostrar / ocultar", self._toggle_window)
        self._tray_menu.addAction("Detener todo", self.engine.stop_all)
        self._tray_menu.addAction("Salir", self.quit_app)
        self.tray.setContextMenu(self._tray_menu)
        self.tray.activated.connect(
            lambda reason: self._toggle_window() if reason == QSystemTrayIcon.Trigger else None
        )
        self.tray.show()

    def _show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _toggle_window(self):
        if self.isVisible() and not self.isMinimized():
            if self.tray is not None:
                self.hide()
            else:
                self.showMinimized()
        else:
            self._show_window()

    def quit_app(self):
        self.close()

    def _run_action(self, key):
        if key == "stop":
            self.engine.stop_all()
        elif key == "toggle":
            self._toggle_window()
        elif key == "quit":
            self.quit_app()
        elif key == "add":
            if QApplication.activeModalWidget() is None:
                self._show_window()
                self.add_sounds()

    def _update_meter(self):
        peak, self.engine.cable_peak = self.engine.cable_peak, 0.0
        self._lvl = max(peak ** 0.5, self._lvl * 0.82)
        self.meter.set_level(self._lvl)


    def _register_saved_hotkeys(self):
        failed = []
        for key, combo in self.settings.get("atajos", {}).items():
            if combo and key in ACTIONS and self.hotkeys.register(f"action:{key}", combo):
                failed.append(f"{ACTIONS[key]} ({combo})")
        for sound in self.library:
            combo = sound.get("hotkey")
            if combo and self.hotkeys.register(sound["id"], combo):
                failed.append(f'{sound["name"]} ({combo})')
        if failed and self.hotkeys.available:
            QMessageBox.warning(self, "Atajos", "No se pudieron activar estos atajos:\n"
                                + "\n".join(failed))

    def _hotkey_pressed(self, key):
        if key.startswith("action:"):
            self._run_action(key.split(":", 1)[1])
            return
        sound_id = key
        for b in self.buttons:
            if b.sound["id"] == sound_id:
                self.play(b)
                return

    def _combo_owner(self, combo, ignore_key):
        for k, c in self.settings.get("atajos", {}).items():
            if c == combo and f"action:{k}" != ignore_key:
                return ACTIONS.get(k, k)
        for snd in self.library:
            if snd.get("hotkey") == combo and snd["id"] != ignore_key:
                return snd["name"]
        return None

    def set_action_hotkey(self, key, combo):
        atajos = self.settings.setdefault("atajos", {})
        hk_id = f"action:{key}"
        if not combo:
            self.hotkeys.unregister(hk_id)
            atajos.pop(key, None)
            save_json(SETTINGS_FILE, self.settings)
            return None
        if not self.hotkeys.available:
            return "Para usar atajos globales instalá:  pip install keyboard"
        owner = self._combo_owner(combo, hk_id)
        if owner:
            return f"«{combo.upper()}» ya lo usa «{owner}»."
        error = self.hotkeys.register(hk_id, combo)
        if error:
            return error
        atajos[key] = combo
        save_json(SETTINGS_FILE, self.settings)
        return None

    def set_sound_hotkey(self, sound, combo):
        if combo:
            if not self.hotkeys.available:
                return "Para usar atajos globales instalá:  pip install keyboard"
            owner = self._combo_owner(combo, sound["id"])
            if owner:
                return f"«{combo.upper()}» ya lo usa «{owner}»."
            error = self.hotkeys.register(sound["id"], combo)
            if error:
                return error
            sound["hotkey"] = combo
        else:
            self.hotkeys.unregister(sound["id"])
            sound.pop("hotkey", None)
        for b in self.buttons:
            if b.sound is sound:
                b.refresh()
        save_json(LIBRARY_FILE, self.library)
        return None

    def assign_hotkey(self, btn):
        if not self.hotkeys.available:
            QMessageBox.information(self, "Falta una librería",
                                    "Para usar atajos globales instalá:  pip install keyboard")
            return
        dlg = HotkeyDialog(self, btn.sound["name"])
        self.hotkeys.paused = True
        try:
            accepted = dlg.exec() == QDialog.Accepted
        finally:
            self.hotkeys.paused = False
        if not accepted:
            return
        error = self.set_sound_hotkey(btn.sound, dlg.combo())
        if error:
            QMessageBox.warning(self, "Atajo", error)

    def clear_hotkey(self, btn):
        self.set_sound_hotkey(btn.sound, "")

    def open_shortcuts(self):
        ShortcutsDialog(self).exec()

    def rename(self, btn):
        name, ok = QInputDialog.getText(
            self, "Renombrar", "Nuevo nombre:", text=btn.sound["name"]
        )
        name = name.strip()
        if ok and name:
            btn.sound["name"] = name
            btn.refresh()
            save_json(LIBRARY_FILE, self.library)
            self.relayout()

    def delete(self, btn):
        if not self.confirm("Eliminar", f"¿Eliminar «{btn.sound['name']}»?", "Sí, eliminar"):
            return
        path = SOUNDS_DIR / btn.sound["file"]
        self.engine.forget(path)
        self.hotkeys.unregister(btn.sound["id"])
        try:
            path.unlink()
        except OSError:
            pass
        self.library = [s for s in self.library if s["id"] != btn.sound["id"]]
        self.buttons.remove(btn)
        btn.setParent(None)
        btn.deleteLater()
        save_json(LIBRARY_FILE, self.library)
        self.relayout()

    def closeEvent(self, event):
        sd.stop()
        self.hotkeys.clear()
        self.engine.shutdown()
        if self.tray is not None:
            self.tray.hide()
        super().closeEvent(event)
        QApplication.instance().quit()
