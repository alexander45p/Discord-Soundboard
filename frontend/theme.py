from PySide6.QtGui import QPainterPath


THEMES = {
    "Cyberpunk": dict(
        bg="#0a0608", panel="#13080b", surface="#1d0d11", border="#5c1a22",
        accent="#ff3b4e", accent2="#35e0e6", text="#f4eaec", muted="#a37b80",
        highlight="#f3e600", on_accent="#0a0608", cut=12, caps=True,
    ),
    "Oscuro": dict(
        bg="#14161b", panel="#1b1e25", surface="#252932", border="#3a4050",
        accent="#5b8def", accent2="#7bd1a0", text="#e6e8ee", muted="#8b93a3",
        highlight="#e5c07b", on_accent="#0d1017", cut=6, caps=False,
    ),
    "Claro": dict(
        bg="#eceef2", panel="#ffffff", surface="#e2e5ec", border="#bcc3d2",
        accent="#3a6df0", accent2="#1d9a6c", text="#1b1f2a", muted="#6a7284",
        highlight="#b27c00", on_accent="#ffffff", cut=6, caps=False,
    ),
}


T = dict(THEMES["Cyberpunk"])


def build_qss(t):
    return f"""
    QWidget {{ background:{t['bg']}; color:{t['text']}; }}
    QLabel {{ background:transparent; }}
    QLineEdit, QComboBox {{
        background:{t['surface']}; border:1px solid {t['border']};
        border-bottom:2px solid {t['accent']}; border-radius:0; padding:6px 8px;
        selection-background-color:{t['accent']}; selection-color:{t['on_accent']};
    }}
    QComboBox::drop-down {{ border:none; width:22px; }}
    QComboBox QAbstractItemView {{
        background:{t['panel']}; color:{t['text']}; border:1px solid {t['accent']};
        selection-background-color:{t['accent']}; selection-color:{t['on_accent']};
    }}
    QSlider::groove:horizontal {{ height:4px; background:{t['border']}; }}
    QSlider::sub-page:horizontal {{ background:{t['accent']}; }}
    QSlider::handle:horizontal {{
        background:{t['accent2']}; width:10px; margin:-6px 0; border-radius:0;
    }}
    QAbstractScrollArea, #qt_scrollarea_viewport, #gridHost {{
        background:transparent; border:none;
    }}
    QScrollBar:vertical {{ background:{t['panel']}; width:10px; margin:0; }}
    QScrollBar::handle:vertical {{ background:{t['accent']}; min-height:30px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
    QMenu {{ background:{t['panel']}; border:1px solid {t['accent']}; padding:4px; }}
    QMenu::item {{ padding:6px 22px; background:transparent; }}
    QMenu::item:selected {{ background:{t['accent']}; color:{t['on_accent']}; }}
    QToolTip {{
        background:{t['panel']}; color:{t['accent2']}; border:1px solid {t['accent']};
    }}
    QDialog, QMessageBox, QInputDialog {{ background:{t['bg']}; }}
    QPushButton {{
        background:{t['surface']}; border:1px solid {t['accent']}; padding:6px 16px;
        border-radius:0;
    }}
    QPushButton:hover {{ background:{t['accent']}; color:{t['on_accent']}; }}
    """


def chamfer_path(r, c):
    p = QPainterPath()
    p.moveTo(r.left(), r.top())
    p.lineTo(r.right() - c, r.top())
    p.lineTo(r.right(), r.top() + c)
    p.lineTo(r.right(), r.bottom())
    p.lineTo(r.left() + c, r.bottom())
    p.lineTo(r.left(), r.bottom() - c)
    p.closeSubpath()
    return p
