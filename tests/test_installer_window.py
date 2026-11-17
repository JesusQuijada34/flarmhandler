"""Regresiones del instalador: enums con ámbito de PyQt6 y ventana frameless.

Cubre dos defectos reproducidos sobre el código real:

* ``QMessageBox.Yes``/``QSizePolicy.Expanding`` no existen en PyQt6 (los enums
  llevan ámbito), así que desinstalar o abrir releases lanzaba ``AttributeError``.
* El flag ``FramelessWindowHint`` estaba comentado: se veían la barra de título
  nativa **y** la propia, y la ventana sin marco no se podía redimensionar.

Ejecutar con ``QT_QPA_PLATFORM=offscreen python -m pytest tests/ -q``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

pytest.importorskip("PyQt6")

from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: E402

_spec = importlib.util.spec_from_file_location("flarmhandler", ROOT / "flarmhandler.py")
flarmhandler = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(flarmhandler)

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture()
def window():
    win = flarmhandler.InstallWindow("demo", "Influent")
    yield win
    win.close()


def test_window_is_frameless_with_own_titlebar(window):
    flags = window.windowFlags()
    assert flags & QtCore.Qt.WindowType.FramelessWindowHint
    assert window.title_bar is not None


def test_resize_filter_installed(window):
    filt = getattr(window, "_resize_filter", None)
    assert isinstance(filt, flarmhandler._ResizeEdgeFilter)


def test_resize_filter_sets_horizontal_cursor_on_left_edge(window):
    filt = window._resize_filter
    event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseMove,
        QtCore.QPointF(2, window.height() // 2),
        QtCore.QPointF(2, window.height() // 2),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    filt.eventFilter(window, event)
    assert window.cursor().shape() == QtCore.Qt.CursorShape.SizeHorCursor


def test_resize_filter_resizes_window_manually(window):
    """Sin backend de WM (offscreen) el redimensionado se hace a mano."""
    filt = window._resize_filter
    start = window.geometry()
    press = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonPress,
        QtCore.QPointF(2, window.height() // 2),
        QtCore.QPointF(2, window.height() // 2),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    assert filt.eventFilter(window, press) is True
    move = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseMove,
        QtCore.QPointF(-40, window.height() // 2),
        QtCore.QPointF(-40, window.height() // 2),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    filt.eventFilter(window, move)
    assert window.geometry().width() > start.width()


def test_uninstall_uses_scoped_messagebox_enum(window, monkeypatch):
    """Desinstalar ya no revienta por ``QMessageBox.Yes`` sin ámbito."""
    calls = {}

    def fake_question(parent, title, text, buttons, default):
        calls["buttons"] = buttons
        return QtWidgets.QMessageBox.StandardButton.No

    monkeypatch.setattr(QtWidgets.QMessageBox, "question", fake_question)
    window.on_uninstall()
    assert calls["buttons"] & QtWidgets.QMessageBox.StandardButton.Yes


def test_offer_open_releases_uses_scoped_enum(window, monkeypatch):
    opened = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "question",
                        lambda *a, **k: QtWidgets.QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(flarmhandler.webbrowser, "open", lambda url: opened.append(url))
    window.offer_open_releases("https://example.com/releases")
    assert opened == ["https://example.com/releases"]
