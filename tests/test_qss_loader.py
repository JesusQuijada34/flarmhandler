"""Contrato del cargador QSS por control (``source/qss/{qtcontrolid}.qss``).

Mismo esquema que ``packagemaker``: un fichero por control, marcadores
``__NOMBRE__`` resueltos por ``lib/qss_loader`` y variantes por rol.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib import qss_loader


def test_qss_dir_has_a_file_per_control():
    controls = qss_loader.available_controls()
    for expected in ("qwidget", "qpushbutton", "qlineedit", "qlabel", "qmessagebox"):
        assert expected in controls, f"falta source/qss/{expected}.qss"


def test_files_use_double_underscore_markers():
    for control in qss_loader.available_controls():
        text = qss_loader.read_qss_file(control)
        assert "{accent" not in text, f"{control} aún usa marcadores de llave"
    assert "__ACCENT__" in qss_loader.read_qss_file("qpushbutton")


def test_build_global_qss_resolves_the_accent():
    import flarmhandler

    qss = flarmhandler.build_global_qss("#E81123")
    assert "__ACCENT" not in qss
    assert "#E81123" in qss


def test_render_does_not_touch_css_braces():
    out = qss_loader.render("QWidget { color: __ACCENT__; }", {"ACCENT": "#0078D4"})
    assert out == "QWidget { color: #0078D4; }"


def test_unknown_control_raises():
    try:
        qss_loader.read_qss_file("qnosuchcontrol")
    except FileNotFoundError:
        pass
    else:  # pragma: no cover
        raise AssertionError("un control inexistente debía lanzar FileNotFoundError")
