# -*- coding: utf-8 -*-
"""Splash dinámico estilo UWP para instaladores y apps empaquetadas.

La lógica vive aquí (y no dentro de ``flarmhandler.py``) porque es la misma que
necesita la Fase 3 del plan maestro: ``packagemaker`` copiará este módulo a la
carpeta ``lib/`` de los proyectos ``iflapp`` y lo inyectará como *bootloader*.

Reglas del plan (``bugs.md``, Fase 2):

* Se evalúa la orientación de la pantalla: ``landscape`` (ancho > alto),
  ``portrait`` (ancho < alto) y ``square`` (ancho == alto).
* ``landscape`` prefiere ``{app}-landscapeSplash.png``; ``portrait`` prefiere
  ``{app}-portraitSplash.png``. En pantalla cuadrada vale cualquier asset.
* Si no hay asset específico se usa un splash genérico; si tampoco lo hay, se
  genera un marco transparente con el icono centrado a ``512x512``.
* La transparencia del asset se rellena con el color de acento del SO.
* Al mostrar la ventana principal, el splash se desvanece (*fade-out*).

Sin ``PyQt6`` el módulo importa igual (``HAS_QT`` es ``False``) para que el
resto del instalador no dependa de la GUI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from PyQt6 import QtCore, QtGui, QtWidgets

    HAS_QT = True
except Exception:  # pragma: no cover - entorno sin PyQt6
    QtCore = QtGui = QtWidgets = None
    HAS_QT = False

DEFAULT_ACCENT = "#0078D4"
DEFAULT_ICON = "assets/product_logo.png"

LANDSCAPE = "landscape"
PORTRAIT = "portrait"
SQUARE = "square"

# Dimensiones estándar de renderizado que fija el plan maestro.
STANDARD_SIZES = {
    LANDSCAPE: (1366, 768),
    PORTRAIT: (768, 1366),
    SQUARE: (1280, 1280),
}

FADE_DURATION_MS = 450
# Tamaño del icono del splash de respaldo (marco transparente).
FALLBACK_ICON_SIZE = 512


def screen_orientation(width: int, height: int) -> str:
    """Clasifica una pantalla en ``landscape`` / ``portrait`` / ``square``."""
    if width > height:
        return LANDSCAPE
    if width < height:
        return PORTRAIT
    return SQUARE


def current_orientation() -> str:
    """Orientación de la pantalla principal (``landscape`` por defecto)."""
    if not HAS_QT:
        return LANDSCAPE
    screen = QtWidgets.QApplication.primaryScreen()
    if screen is None:
        return LANDSCAPE
    geometry = screen.geometry()
    return screen_orientation(geometry.width(), geometry.height())


def splash_candidates(app_name: str, orientation: str) -> list[str]:
    """Nombres de asset que se intentan, del más específico al más genérico.

    En pantalla cuadrada se ignora la restricción de orientación (cualquier
    asset vale), así que se listan ambos y luego los genéricos.
    """
    app = (app_name or "").strip()
    specific = []
    if orientation == LANDSCAPE:
        specific = [f"{app}-landscapeSplash.png"]
    elif orientation == PORTRAIT:
        specific = [f"{app}-portraitSplash.png"]
    else:  # square: sin restricción de orientación
        specific = [f"{app}-landscapeSplash.png", f"{app}-portraitSplash.png"]

    generic = ["splash.png", "splash_setup.png"]
    seen = set()
    ordered = []
    for name in specific + generic:
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def find_splash_asset(
    assets_dir: Path | str,
    app_name: str,
    orientation: str,
    has_assets: bool = True,
) -> Optional[Path]:
    """Primer asset de splash existente en *assets_dir* (o ``None``).

    ``has_assets`` permite distinguir "carpeta sin assets" de "assets sin
    splash": en ambos casos no hay splash que mostrar, pero el llamador usa el
    dato para decidir entre Mica completo o un banner normal.
    """
    if not has_assets:
        return None
    assets_dir = Path(assets_dir)
    for name in splash_candidates(app_name, orientation):
        candidate = assets_dir / name
        if candidate.is_file():
            return candidate
    return None


def _load_icon_pixmap(icon_source):
    """Carga el icono desde una ruta, unos bytes o un ``QPixmap`` ya listo."""
    if icon_source is None:
        return None
    if isinstance(icon_source, QtGui.QPixmap):
        return None if icon_source.isNull() else icon_source
    if isinstance(icon_source, (bytes, bytearray)):
        pixmap = QtGui.QPixmap()
        if pixmap.loadFromData(bytes(icon_source)):
            return pixmap
        return None
    path = Path(icon_source)
    if not path.is_file():
        return None
    pixmap = QtGui.QPixmap(str(path))
    return None if pixmap.isNull() else pixmap


def render_fallback_icon(
    icon_source,
    size: int = FALLBACK_ICON_SIZE,
    accent: str = DEFAULT_ACCENT,
):
    """Marco transparente con el icono centrado a *size* px.

    Se usa cuando no hay ningún asset de splash. *icon_source* puede ser una
    ruta, los bytes del icono (p. ej. la cabecera del contenedor) o un
    ``QPixmap``. Devuelve ``None`` si no hay icono válido.
    """
    if not HAS_QT:
        return None
    source = _load_icon_pixmap(icon_source)
    if source is None:
        return None

    canvas = QtGui.QPixmap(size, size)
    canvas.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(canvas)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)

    # Fondo de acento con esquinas suaves (geometría UWP), igual que el icono
    # de la cabecera del instalador.
    painter.setPen(QtCore.Qt.PenStyle.NoPen)
    painter.setBrush(QtGui.QColor(accent))
    painter.drawRoundedRect(0, 0, size, size, 24, 24)

    target = int(size * 0.6)
    scaled = source.scaled(
        target,
        target,
        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
        QtCore.Qt.TransformationMode.SmoothTransformation,
    )
    painter.drawPixmap(
        (size - scaled.width()) // 2,
        (size - scaled.height()) // 2,
        scaled,
    )
    painter.end()
    return canvas


def standard_size_for(orientation: str) -> tuple[int, int]:
    """Tamaño de renderizado estándar de la orientación, recortado a la pantalla.

    El plan fija ``1366x768`` (horizontal), ``768x1366`` (vertical) y
    ``1280x1280`` (cúbico); si la pantalla es más pequeña se usa su tamaño para
    que el splash nunca exceda el área visible.
    """
    size = STANDARD_SIZES.get(orientation, STANDARD_SIZES[LANDSCAPE])
    if HAS_QT:
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is not None:
            geo = screen.geometry()
            return (max(min(size[0], geo.width()), 320), max(min(size[1], geo.height()), 240))
    return size


def _fit_asset_to_frame(pixmap, orientation: str, accent: str):
    """Escala el asset al marco estándar y rellena el resto con el acento."""
    width, height = standard_size_for(orientation)
    scaled = pixmap.scaled(
        width, height,
        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
        QtCore.Qt.TransformationMode.SmoothTransformation,
    )
    canvas = QtGui.QPixmap(width, height)
    canvas.fill(QtGui.QColor(accent))
    painter = QtGui.QPainter(canvas)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    painter.drawPixmap((width - scaled.width()) // 2, (height - scaled.height()) // 2, scaled)
    painter.end()
    return canvas


def build_splash_pixmap(
    asset_path: Path | str | None,
    orientation: str,
    accent: str = DEFAULT_ACCENT,
    icon_source=None,
):
    """Pixmap del splash a mostrar, o ``None`` si no hay nada que renderizar.

    Prioriza el asset: se escala al marco estándar de la orientación y su
    transparencia/letterbox se rellena con el acento del SO. Si no hay asset,
    cae al marco transparente con el icono centrado a ``512x512``.
    """
    if not HAS_QT:
        return None
    if asset_path:
        pixmap = QtGui.QPixmap(str(asset_path))
        if not pixmap.isNull():
            return _fit_asset_to_frame(pixmap, orientation, accent)
    return render_fallback_icon(icon_source, FALLBACK_ICON_SIZE, accent)


def center_on_screen(widget) -> None:
    """Centra *widget* en la pantalla principal (sin depender del padre)."""
    if not HAS_QT:
        return
    screen = QtWidgets.QApplication.primaryScreen()
    if screen is None:
        return
    geo = screen.geometry()
    widget.move(
        geo.center().x() - widget.width() // 2,
        geo.center().y() - widget.height() // 2,
    )


class SplashWindow(QtWidgets.QWidget if HAS_QT else object):
    """Ventana de splash sin marco que se desvanece al revelar la app."""

    def __init__(self, pixmap, accent: str = DEFAULT_ACCENT, parent=None):
        if not HAS_QT:
            raise RuntimeError("PyQt6 no disponible para SplashWindow")
        super().__init__(parent)
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._accent = accent
        self._finished = False

        self._label = QtWidgets.QLabel(self)
        self._label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._label.setPixmap(pixmap)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        self.setFixedSize(pixmap.size())

        self._fade = QtCore.QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(FADE_DURATION_MS)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.setEasingCurve(QtCore.QEasingCurve.Type.InOutQuad)
        self._fade.finished.connect(self._on_faded)

    def start(self):
        """Muestra el splash centrado y opaco."""
        self.setWindowOpacity(1.0)
        self.show()
        center_on_screen(self)
        self.raise_()

    def finish_when_ready(self, target, timeout_ms: int = 4000):
        """Desvanece el splash en cuanto *target* se dibuja por primera vez.

        El plan pide detectar el momento exacto en que la ventana principal ha
        sido dibujada. Se conecta al primer ``paintEvent`` (se desconecta tras
        usarlo) con un temporizador de seguridad: si la ventana nunca llega a
        pintarse, el splash se retira igualmente para no quedar en pantalla.
        """
        if self._finished:
            return
        self._target = target
        # La ventana se muestra ya (el splash queda encima, con
        # ``WindowStaysOnTopHint``) para que llegue a pintarse; en cuanto lo
        # haga, el filtro dispara el desvanecido. El temporizador es la red de
        # seguridad si nunca se pinta.
        try:
            target.show()
        except Exception:
            pass
        target.installEventFilter(self)
        QtCore.QTimer.singleShot(timeout_ms, self.finish)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.Paint and not self._finished:
            try:
                obj.removeEventFilter(self)
            except Exception:
                pass
            self.finish()
        return super().eventFilter(obj, event)

    def finish(self, target=None):
        """Desvanece el splash; opcionalmente revela *target* al terminar.

        Es idempotente: llamarlo dos veces (p. ej. por un temporizador y por el
        evento de ventana dibujada) no reinicia la animación.
        """
        if self._finished:
            return
        self._finished = True
        if target is not None:
            self._target = target
        self._fade.start()

    def _on_faded(self):
        target = getattr(self, "_target", None)
        if target is not None:
            try:
                target.show()
                target.raise_()
                target.activateWindow()
            except Exception:
                pass
        self.close()
