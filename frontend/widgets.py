import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QMenu, QPushButton, QVBoxLayout, QWidget

from backend.config import MAX_SECONDS, SAMPLE_RATE
from frontend.constants import BLOCK, BTN_H, BTN_W
from frontend.theme import T, chamfer_path


def fmt_time(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"


def single_chord(edit):
    try:
        edit.setMaximumSequenceLength(1)
    except AttributeError:
        pass


class CyberButton(QPushButton):

    def __init__(self, text, accent=False):
        super().__init__(text)
        self.accent = accent
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(34)

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)

    def _colors(self):
        hover, down = self.underMouse(), self.isDown()
        if not self.isEnabled():
            return T["surface"], T["border"], T["muted"]
        if down:
            return T["accent2"], T["accent2"], T["on_accent"]
        if hover or self.accent:
            return T["accent"], T["accent"], T["on_accent"]
        return T["surface"], T["accent"], T["text"]

    def paintEvent(self, _event):
        fill, border, fg = self._colors()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = chamfer_path(rect, T["cut"] * 0.7)
        p.fillPath(path, QColor(fill))
        p.setPen(QPen(QColor(border), 1.4))
        p.drawPath(path)
        p.setPen(QColor(fg))
        f = QFont(self.font())
        f.setBold(True)
        if T["caps"]:
            f.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
        p.setFont(f)
        text = self.text().upper() if T["caps"] else self.text()
        p.drawText(rect, Qt.AlignCenter, text)


class SoundButton(CyberButton):
    def __init__(self, sound, on_play, on_rename, on_delete, on_hotkey, on_clear_hotkey):
        super().__init__(sound["name"])
        self.sound = sound
        self.setFixedSize(BTN_W, BTN_H)
        self.setToolTip(f'{sound["name"]}  ({sound["duration"]:.1f} s)')
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.clicked.connect(lambda: on_play(self))
        self.customContextMenuRequested.connect(
            lambda pos: self._menu(pos, on_rename, on_delete, on_hotkey, on_clear_hotkey)
        )

    def _menu(self, pos, on_rename, on_delete, on_hotkey, on_clear_hotkey):
        menu = QMenu(self)
        menu.addAction("Renombrar", lambda: on_rename(self))
        menu.addAction("Asignar atajo...", lambda: on_hotkey(self))
        if self.sound.get("hotkey"):
            menu.addAction("Quitar atajo", lambda: on_clear_hotkey(self))
        menu.addAction("Eliminar", lambda: on_delete(self))
        menu.exec(self.mapToGlobal(pos))

    def refresh(self):
        self.setText(self.sound["name"])
        hk = self.sound.get("hotkey")
        extra = f"  [{hk.upper()}]" if hk else ""
        self.setToolTip(f'{self.sound["name"]}  ({self.sound["duration"]:.1f} s){extra}')
        self.update()

    def paintEvent(self, _event):
        fill, border, fg = self._colors()
        hover = self.underMouse() or self.isDown()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = chamfer_path(rect, T["cut"])
        p.fillPath(path, QColor(T["accent"] if hover else T["surface"]))
        p.setPen(QPen(QColor(T["accent"] if hover else T["border"]), 1.4))
        p.drawPath(path)
        if not hover:
            p.fillRect(QRectF(rect.left(), rect.top() + 8, 3, rect.height() - 22),
                       QColor(T["accent"]))
        fg = QColor(T["on_accent"] if hover else T["text"])
        sub = QColor(T["on_accent"] if hover else T["accent2"])

        f = QFont(self.font())
        f.setBold(True)
        if T["caps"]:
            f.setLetterSpacing(QFont.AbsoluteSpacing, 1.0)
        p.setFont(f)
        p.setPen(fg)
        name = self.sound["name"].upper() if T["caps"] else self.sound["name"]
        p.drawText(rect.adjusted(12, 6, -14, -22), Qt.AlignLeft | Qt.AlignVCenter
                   | Qt.TextWordWrap, name)

        small = QFont(self.font())
        small.setPointSize(max(7, small.pointSize() - 2))
        p.setFont(small)
        p.setPen(sub)
        p.drawText(rect.adjusted(12, 0, -14, -6), Qt.AlignRight | Qt.AlignBottom,
                   f'{self.sound["duration"]:.1f} s')
        hk = self.sound.get("hotkey")
        if hk:
            room = int(rect.width() - 26 - 46)
            txt = p.fontMetrics().elidedText(hk.upper(), Qt.ElideRight, room)
            p.drawText(rect.adjusted(12, 0, -14, -6), Qt.AlignLeft | Qt.AlignBottom, txt)


class ChamferPanel(QFrame):

    def __init__(self, title):
        super().__init__()
        self.title = title
        self.right_text = ""
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(14, 44, 14, 14)

    def set_right_text(self, text):
        self.right_text = text
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = chamfer_path(rect, T["cut"] * 1.6)
        p.fillPath(path, QColor(T["panel"]))
        p.setPen(QPen(QColor(T["accent"]), 1.5))
        p.drawPath(path)

        f = QFont(self.font())
        f.setBold(True)
        if T["caps"]:
            f.setLetterSpacing(QFont.AbsoluteSpacing, 2.0)
        p.setFont(f)
        title = self.title.upper() if T["caps"] else self.title
        tw = p.fontMetrics().horizontalAdvance(title) + 24
        tag = QRectF(14, 10, tw, 24)
        p.fillRect(tag, QColor(T["accent"]))
        p.setPen(QColor(T["on_accent"]))
        p.drawText(tag, Qt.AlignCenter, title)
        p.fillRect(QRectF(tag.right() + 6, 20, 26, 4), QColor(T["highlight"]))
        p.setPen(QColor(T["accent2"]))
        p.drawText(QRectF(0, 10, self.width() - 26, 24), Qt.AlignRight | Qt.AlignVCenter,
                   self.right_text)


class LevelMeter(QWidget):
    SEGMENTS = 28

    def __init__(self):
        super().__init__()
        self.level = 0.0
        self.setFixedHeight(16)
        self.setMinimumWidth(200)

    def set_level(self, value):
        self.level = value
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        n, gap = self.SEGMENTS, 2
        w = (self.width() - gap * (n - 1)) / n
        lit = int(round(min(1.0, self.level) * n))
        for i in range(n):
            if i >= lit:
                color = T["border"]
            elif i < n * 0.6:
                color = T["accent2"]
            elif i < n * 0.85:
                color = T["highlight"]
            else:
                color = T["accent"]
            p.fillRect(QRectF(i * (w + gap), 0, w, self.height()), QColor(color))


class WaveformView(QWidget):

    changed = Signal()
    MIN_LEN = 0.05

    def __init__(self, data):
        super().__init__()
        self.setMinimumHeight(170)
        self.setMouseTracking(True)
        mono = np.abs(data).max(axis=1)
        pad = (-len(mono)) % BLOCK
        if pad:
            mono = np.pad(mono, (0, pad))
        self.peaks = mono.reshape(-1, BLOCK).max(axis=1)
        self.peak_max = max(float(self.peaks.max()), 1e-6)
        self.duration = len(data) / SAMPLE_RATE
        self.sel_start = 0.0
        self.sel_end = min(self.duration, float(MAX_SECONDS))
        self.view_start, self.view_end = 0.0, self.duration
        self.playhead = None
        self._drag = None
        self._offset = 0.0


    def t2x(self, t):
        return (t - self.view_start) / (self.view_end - self.view_start) * self.width()

    def x2t(self, x):
        return self.view_start + x / max(1, self.width()) * (self.view_end - self.view_start)


    def _set_start(self, t):
        t = min(max(0.0, t), self.sel_end - self.MIN_LEN)
        self.sel_start = max(t, self.sel_end - MAX_SECONDS)

    def _set_end(self, t):
        t = max(min(self.duration, t), self.sel_start + self.MIN_LEN)
        self.sel_end = min(t, self.sel_start + MAX_SECONDS)


    def mousePressEvent(self, e):
        x = e.position().x()
        xs, xe = self.t2x(self.sel_start), self.t2x(self.sel_end)
        if abs(x - xs) < 10:
            self._drag = "start"
        elif abs(x - xe) < 10:
            self._drag = "end"
        elif xs < x < xe:
            self._drag = "move"
            self._offset = self.x2t(x) - self.sel_start
        else:
            self._drag = "start" if abs(x - xs) < abs(x - xe) else "end"
            self.mouseMoveEvent(e)

    def mouseMoveEvent(self, e):
        x = e.position().x()
        t = self.x2t(x)
        if self._drag == "start":
            self._set_start(t)
        elif self._drag == "end":
            self._set_end(t)
        elif self._drag == "move":
            length = self.sel_end - self.sel_start
            start = min(max(0.0, t - self._offset), self.duration - length)
            self.sel_start, self.sel_end = start, start + length
        else:
            near = min(abs(x - self.t2x(self.sel_start)), abs(x - self.t2x(self.sel_end))) < 10
            self.setCursor(Qt.SizeHorCursor if near else Qt.ArrowCursor)
            return
        self.update()
        self.changed.emit()

    def mouseReleaseEvent(self, _e):
        self._drag = None

    def wheelEvent(self, e):
        span = self.view_end - self.view_start
        if e.modifiers() & Qt.ShiftModifier:
            shift = span * 0.1 * (-1 if e.angleDelta().y() > 0 else 1)
            self.view_start += shift
            self.view_end += shift
        else:
            anchor = self.x2t(e.position().x())
            k = 0.8 if e.angleDelta().y() > 0 else 1.25
            new_span = min(self.duration, max(0.5, span * k))
            ratio = (anchor - self.view_start) / span
            self.view_start = anchor - ratio * new_span
            self.view_end = self.view_start + new_span
        span = self.view_end - self.view_start
        if self.view_start < 0:
            self.view_start, self.view_end = 0.0, span
        if self.view_end > self.duration:
            self.view_end, self.view_start = self.duration, self.duration - span
        self.update()


    def _columns(self, w):
        bt = BLOCK / SAMPLE_RATE
        i0 = int(self.view_start / bt)
        i1 = min(len(self.peaks), int(np.ceil(self.view_end / bt)) + 1)
        seg = self.peaks[i0:i1]
        if len(seg) == 0:
            return np.zeros(w)
        idx = np.minimum(np.linspace(0, len(seg), w, endpoint=False).astype(int),
                         len(seg) - 1)
        return np.maximum.reduceat(seg, idx) / self.peak_max

    def paintEvent(self, _e):
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(T["bg"]))
        mid = h / 2
        xs, xe = self.t2x(self.sel_start), self.t2x(self.sel_end)
        cols = self._columns(w)
        for x, v in enumerate(cols):
            inside = xs <= x <= xe
            p.setPen(QColor(T["accent2"] if inside else T["muted"]))
            amp = max(1.0, v * (mid - 8))
            p.drawLine(QPointF(x, mid - amp), QPointF(x, mid + amp))

        shade = QColor(0, 0, 0, 140)
        p.fillRect(QRectF(0, 0, max(0, xs), h), shade)
        p.fillRect(QRectF(min(w, xe), 0, max(0, w - xe), h), shade)

        p.setPen(QPen(QColor(T["highlight"]), 3))
        p.drawLine(QPointF(xs, 0), QPointF(xs, h))
        p.drawLine(QPointF(xe, 0), QPointF(xe, h))
        p.setPen(QColor(T["highlight"]))
        p.drawText(QPointF(xs + 5, 14), fmt_time(self.sel_start))
        label = fmt_time(self.sel_end)
        p.drawText(QPointF(xe - p.fontMetrics().horizontalAdvance(label) - 5, h - 6), label)
        if self.playhead is not None:
            x = self.t2x(self.playhead)
            p.setPen(QPen(QColor(T["accent"]), 2))
            p.drawLine(QPointF(x, 0), QPointF(x, h))
        p.setPen(QPen(QColor(T["border"]), 1))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
