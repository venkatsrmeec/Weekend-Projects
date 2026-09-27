# alfred_ui.py — JARVIS-style overlay with Batman sigil
import math
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (
    QPainter, QColor, QPainterPath, QBrush, QPen,
    QRadialGradient, QFont, QConicalGradient
)
def bat_path(scale=1.0):
    """A stylized Batman sigil as a QPainterPath."""
    pts = [
        (0, -15), (8, -35), (16, -24), (36, -34), (92, -26),
        (118, 4), (96, 16), (76, 8), (82, 28), (56, 14),
        (62, 35), (36, 18), (40, 38), (16, 22), (9, 32), (0, 26),
    ]
    s = [(x * scale, y * scale) for x, y in pts]
    path = QPainterPath()
    path.moveTo(*s[0])
    for p in s[1:]:
        path.lineTo(*p)
    for p in reversed(s[:-1]):
        path.lineTo(-p[0], p[1])
    path.closeSubpath()
    return path
STATE_COLORS = {
    "hidden":    (60, 60, 80),
    "wake":      (0, 220, 255),
    "listening": (30, 144, 255),
    "thinking":  (255, 170, 0),
    "speaking":  (0, 220, 150),
    "error":     (255, 60, 60),
}
STATE_CAPTIONS = {
    "wake":      "SYSTEMS ONLINE",
    "listening": "LISTENING",
    "thinking":  "PROCESSING",
    "speaking":  "RESPONDING",
    "error":     "ERROR",
}
class AlfredUI(QWidget):
    def __init__(self, size=720):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(size, size)
        screen = QApplication.primaryScreen().geometry()
        self.move(
            screen.center().x() - size // 2,
            screen.center().y() - size // 2,
        )
        self.state = "hidden"

        self.caption = ""
        self.detail = ""
        self.level = 0.0
        self.smooth_level = 0.0
        self.phase = 0.0
        self.opacity = 0.0
        self.target_opacity = 0.0
        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)
        self.hide()
    def set_state(self, state: str):
        self.state = state
        self.caption = STATE_CAPTIONS.get(state, "")
        if state == "hidden":
            self.target_opacity = 0.0
        else:
            self.show()
            self.target_opacity = 1.0
        self.update()
    def set_detail(self, text: str):
        self.detail = (text or "").strip()
        self.update()
    def set_level(self, level: float):
        self.level = max(0.0, min(1.0, float(level)))
    def _tick(self):
        self.phase = (self.phase + 0.05) % (2 * math.pi)
        self.smooth_level += (self.level - self.smooth_level) * 0.25
        self.level *= 0.85
        self.opacity += (self.target_opacity - self.opacity) * 0.15
        if self.opacity < 0.02 and self.target_opacity == 0.0:
            self.hide()
        self.update()
    def paintEvent(self, event):
        if self.opacity < 0.02:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self.opacity)
        cx, cy = self.width() / 2, self.height() / 2
        r_disc = 180
        r, g, b = STATE_COLORS.get(self.state, STATE_COLORS["hidden"])
        halo_radius = r_disc * (1.6 + 0.15 * self.smooth_level)
        grad = QRadialGradient(cx, cy, halo_radius)
        grad.setColorAt(0.0, QColor(r, g, b, 90))
        grad.setColorAt(0.4, QColor(r, g, b, 40))
        grad.setColorAt(1.0, QColor(r, g, b, 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), halo_radius, halo_radius)
        conic = QConicalGradient(cx, cy, math.degrees(self.phase) * 2)
        conic.setColorAt(0.0, QColor(r, g, b, 0))
        conic.setColorAt(0.15, QColor(r, g, b, 70))
        conic.setColorAt(0.5, QColor(r, g, b, 0))
        conic.setColorAt(1.0, QColor(r, g, b, 0))
        p.setBrush(QBrush(conic))
        p.drawEllipse(QPointF(cx, cy), r_disc * 1.25, r_disc * 1.25)
        for i in range(3):
            ph = self.phase + i * (2 * math.pi / 3)
            base = r_disc + 22 + i * 24
            radius = base + 18 * math.sin(ph) + 30 * self.smooth_level
            alpha = int(140 * (0.5 + 0.5 * math.sin(ph)))
            pen = QPen(QColor(r, g, b, alpha))
            pen.setWidth(2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), radius, radius)
        p.setBrush(QBrush(QColor(8, 10, 16, 235)))
        p.setPen(QPen(QColor(r, g, b, 220), 3))
        p.drawEllipse(QPointF(cx, cy), r_disc, r_disc)
        pen = QPen(QColor(r, g, b, 80))
        pen.setWidth(1)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        p.drawEllipse(QPointF(cx, cy), r_disc - 14, r_disc - 14)
        p.save()
        p.translate(cx, cy)
        breathe = 1.0 + 0.02 * math.sin(self.phase * 1.5)
        p.scale(breathe, breathe)
        bat = bat_path(scale=1.05)
        p.setBrush(QBrush(QColor(255, 200, 30, 245)))
        p.setPen(QPen(QColor(255, 240, 120, 200), 2))
        p.drawPath(bat)
        p.restore()
        if self.caption:
            font = QFont("DejaVu Sans", 15, QFont.Weight.Bold)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 8)
            p.setFont(font)
            p.setPen(QPen(QColor(r, g, b, 240)))
            y = cy + r_disc + 55
            rect = QRectF(0, y, self.width(), 40)
            p.drawText(rect, int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                       self.caption)
        if self.detail:
            font = QFont("DejaVu Sans", 12)
            p.setFont(font)
            p.setPen(QPen(QColor(220, 225, 235, 235)))
            y = cy + r_disc + 105
            rect = QRectF(self.width() * 0.10, y, self.width() * 0.80, 140)
            p.drawText(rect,
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
                           | Qt.TextFlag.TextWordWrap),
                       self.detail)
