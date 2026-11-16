# -*- coding: utf-8 -*-
"""Splash integrado estilo UWP para instaladores y apps empaquetadas.

Sigue el patrón de ``IntegratedSplash`` de ``packagemaker`` (commit ``f15bfde``):
el splash **no genera ningún asset**. Es una ventana del mismo tamaño que la
ventana principal, con el color de fondo leído del registro de Windows (el
acento del SO) y el icono del paquete (``app/app-icon.ico``) centrado. Al
mostrarse la ventana principal, el splash se desvanece (*fade-out*).

La lógica vive aquí (y no dentro de ``flarmhandler.py``) porque es la misma que
necesita la Fase 3 del plan maestro: ``packagemaker`` copiará este módulo a la
carpeta ``lib/`` de los proyectos ``iflapp`` y lo inyectará como *bootloader*.

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
DEFAULT_ICON = "app/app-icon.ico"
ICON_SIZE = 180
FADE_DURATION_MS = 600
DEFAULT_DURATION_MS = 5000


def resolve_icon_source(window) -> Optional[object]:
    """Icono del paquete a mostrar en el splash (bytes o ruta), o ``None``.

    Prioriza el icono de la cabecera del contenedor (``package_icon``) y, si no,
    busca ``app/app-icon.ico`` / ``app/app-icon.png`` dentro del paquete extraído.
    """
    icon = getattr(window, "package_icon", b"") or None
    if icon:
        return icon
    extract_dir = getattr(window, "temp_extract_dir", None)
    if extract_dir:
        for name in ("app-icon.ico", "app-icon.png"):
            candidate = Path(extract_dir) / "app" / name
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


def render_centered_icon(icon_source, size: int = ICON_SIZE):
    """Pixmap del icono escalado a *size* px, o ``None`` si no es válido."""
    if not HAS_QT:
        return None
    source = _load_icon_pixmap(icon_source)
    if source is None:
        return None
    return source.scaled(
        size, size,
        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
        QtCore.Qt.TransformationMode.SmoothTransformation,
    )


if HAS_QT:

    class IntegratedSplash(QtWidgets.QWidget):
        """Splash a pantalla completa sobre la ventana principal (sin assets).

        Es una ventana sin marco, del mismo tamaño que *parent*, con el fondo
        del color de acento del SO y el icono del paquete centrado. Se desvanece
        al terminar (por el temporizador o al dibujarse la ventana principal) y
        emite ``finished``.
        """

        finished = QtCore.pyqtSignal()

        def __init__(self, parent=None, icon_source=None,
                     accent: str = DEFAULT_ACCENT, title: str = ""):
            super().__init__(parent)
            self._parent = parent
            self._finished = False
            self.setWindowFlags(
                QtCore.Qt.WindowType.FramelessWindowHint
                | QtCore.Qt.WindowType.WindowStaysOnTopHint
            )
            if parent is not None:
                self._sync_to_parent()

            self.setStyleSheet(
                f"#SplashContainer {{ background-color: {accent}; }}"
            )

            container = QtWidgets.QWidget(self)
            container.setObjectName("SplashContainer")
            container.setGeometry(0, 0, self.width(), self.height())

            layout = QtWidgets.QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            layout.addStretch()

            self.icon_label = QtWidgets.QLabel()
            self.icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.icon_label.setStyleSheet("background: transparent;")
            pixmap = render_centered_icon(icon_source)
            if pixmap is not None:
                self.icon_label.setPixmap(pixmap)
            layout.addWidget(self.icon_label)
            layout.addStretch()

            self._timer = QtCore.QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self.finish)

            self._fade = QtCore.QPropertyAnimation(self, b"windowOpacity")
            self._fade.setDuration(FADE_DURATION_MS)
            self._fade.setStartValue(1.0)
            self._fade.setEndValue(0.0)
            self._fade.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
            self._fade.finished.connect(self._on_faded)

        def _sync_to_parent(self):
            """Coloca el splash sobre el área visible de la ventana principal."""
            if self._parent is None:
                return
            top_left = self._parent.mapToGlobal(QtCore.QPoint(0, 0))
            self.setGeometry(
                top_left.x(), top_left.y(),
                self._parent.width(), self._parent.height(),
            )

        def resizeEvent(self, event):
            super().resizeEvent(event)
            self._sync_to_parent()
            container = self.findChild(QtWidgets.QWidget, "SplashContainer")
            if container is not None:
                container.setGeometry(0, 0, self.width(), self.height())

        def start(self, duration_ms: int = DEFAULT_DURATION_MS):
            """Muestra el splash y programa el desvanecido."""
            self.setWindowOpacity(1.0)
            self._sync_to_parent()
            self.show()
            self.raise_()
            self._timer.start(duration_ms)

        def finish_when_ready(self, target, timeout_ms: int = DEFAULT_DURATION_MS):
            """Desvanece el splash en cuanto *target* se dibuja por primera vez.

            La ventana principal se muestra ya (el splash queda encima) para que
            llegue a pintarse; al primer ``paintEvent`` se retira el splash. El
            temporizador actúa de red de seguridad si nunca se pinta.
            """
            if self._finished:
                return
            try:
                target.show()
            except Exception:
                pass
            target.installEventFilter(self)
            self._timer.start(timeout_ms)

        def eventFilter(self, obj, event):
            if event.type() == QtCore.QEvent.Type.Paint and not self._finished:
                try:
                    obj.removeEventFilter(self)
                except Exception:
                    pass
                self.finish()
            return super().eventFilter(obj, event)

        def finish(self):
            """Inicia el desvanecido (idempotente)."""
            if self._finished:
                return
            self._finished = True
            self._timer.stop()
            self._fade.start()

        def _on_faded(self):
            self.hide()
            self.finished.emit()
            self.close()

else:  # pragma: no cover - entorno sin PyQt6

    class IntegratedSplash:  # type: ignore[no-redef]
        """Respaldo sin Qt: no hace nada (el instalador degrada sin GUI)."""

        def __init__(self, *args, **kwargs):
            raise RuntimeError("PyQt6 no disponible para IntegratedSplash")
