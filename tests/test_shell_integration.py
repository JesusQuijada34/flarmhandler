"""Pruebas funcionales de la integración de flarmhandler con el ecosistema Fluthin.

Ejercen las funciones reales: parseo de nombres canónicos, lectura de cabecera y
extracción de contenedores ``.iflapp`` v2 / ``.asksome``, registro de
asociaciones de shell (freedesktop) y aplicación de descriptores ``.mexf``.

Ejecutar con::

    QT_QPA_PLATFORM=offscreen python -m pytest tests/ -q
"""

from __future__ import annotations

import importlib.util
import os
import struct
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("flarmhandler", ROOT / "flarmhandler.py")
flarmhandler = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(flarmhandler)

from lib import iflapp_format, asksome_format, package_shell  # noqa: E402


def _png_bytes() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    raw = b"\x00\xff\x00\x00\xff"
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def _png_transparent(width: int = 2, height: int = 2) -> bytes:
    """PNG RGBA completamente transparente, para probar el fondo de acento."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    row = b"\x00" + bytes((0, 0, 0, 0)) * width
    raw = row * height
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


@pytest.fixture()
def sample_project(tmp_path: Path) -> Path:
    project = tmp_path / "pkg"
    (project / "app").mkdir(parents=True)
    (project / "assets").mkdir(parents=True)
    (project / "details.xml").write_text(
        '<?xml version="1.0"?><app>'
        "<publisher>influent</publisher><app>demo</app><name>Demo App</name>"
        "<version>v1.0-26.01-10.00</version><platform>Danenone</platform>"
        "<author>JesusQuijada34</author></app>",
        encoding="utf-8",
    )
    (project / "app" / "demo").write_text("#!/usr/bin/env python3\nprint('hola')\n", encoding="utf-8")
    (project / "assets" / "splash.png").write_bytes(_png_bytes())
    (project / "app" / "app-icon.png").write_bytes(_png_bytes())
    return project


@pytest.fixture()
def iflapp_package(sample_project: Path, tmp_path: Path) -> Path:
    target = tmp_path / "influent.demo.v1.0-26.01-10.00-Danenone.iflapp"
    iflapp_format.pack_iflapp(
        sample_project,
        target,
        identity={
            "publisher": "influent",
            "app": "demo",
            "name": "Demo App",
            "version": "v1.0-26.01-10.00",
            "platform": "Danenone",
            "author": "JesusQuijada34",
        },
        icon=_png_bytes(),
    )
    return target


@pytest.fixture()
def asksome_package(sample_project: Path, tmp_path: Path) -> Path:
    target = tmp_path / "influent.demo.v1.0-26.01-10.00-Danenone.asksome"
    asksome_format.pack_asksome(
        sample_project,
        target,
        metadata={
            "publisher": "influent",
            "app": "demo",
            "name": "Demo Asksome",
            "version": "v1.0-26.01-10.00",
            "platform": "Danenone",
        },
        icon=_png_bytes(),
    )
    return target


# --- Parser de nombres canónicos -------------------------------------------------


def test_parse_package_filename_canonical():
    parsed = flarmhandler.parse_package_filename(
        "influent.dashboard.v3.2.7-26.05-20.13-AlphaCube.iflapp"
    )
    assert parsed == {
        "publisher": "influent",
        "app": "dashboard",
        "version": "v3.2.7",
        "platform": "AlphaCube",
    }


def test_parse_package_filename_legacy_and_unknown():
    legacy = flarmhandler.parse_package_filename("demo-1.0.0-Linux.iflapp")
    assert legacy["app"] == "demo"
    assert legacy["platform"] == "Danenone"

    unknown = flarmhandler.parse_package_filename("random.iflapp")
    assert unknown["app"] == "random"
    assert unknown["platform"] == ""


def test_best_asset_for_platform_prefers_compatible():
    assets = [
        {"name": "influent.demo.v1.0-26.01-10.00-Knosthalij.iflapp"},
        {"name": "influent.demo.v1.0-26.01-10.00-Danenone.iflapp"},
    ]
    asset, version, platform = flarmhandler.best_asset_for_platform(assets, "demo")
    assert asset["name"].endswith("Danenone.iflapp")
    assert platform == "Danenone"
    assert version == "v1.0"


# --- Lectura y extracción de contenedores v2 -------------------------------------


def test_read_package_identity_iflapp(iflapp_package: Path):
    identity = flarmhandler.read_package_identity(str(iflapp_package))
    assert identity["publisher"] == "influent"
    assert identity["app"] == "demo"
    assert identity["platform"] == "Danenone"


def test_read_package_identity_asksome(asksome_package: Path):
    identity = flarmhandler.read_package_identity(str(asksome_package))
    assert identity["publisher"] == "influent"
    assert identity["app"] == "demo"


def test_read_package_icon_returns_header_bytes(iflapp_package: Path):
    assert flarmhandler.read_package_icon(str(iflapp_package)).startswith(b"\x89PNG")


def test_extract_archive_iflapp_v2(iflapp_package: Path, tmp_path: Path):
    destination = tmp_path / "out"
    assert flarmhandler.extract_archive(str(iflapp_package), str(destination)) is True
    assert (destination / "details.xml").is_file()
    assert (destination / "app" / "demo").is_file()


def test_extract_archive_asksome(asksome_package: Path, tmp_path: Path):
    destination = tmp_path / "out"
    assert flarmhandler.extract_archive(str(asksome_package), str(destination)) is True
    assert (destination / "details.xml").is_file()


def test_package_kind_detects_containers(iflapp_package: Path, asksome_package: Path):
    assert flarmhandler._package_kind(str(iflapp_package)) == "iflapp2"
    assert flarmhandler._package_kind(str(asksome_package)) == "asksome"


def test_ensure_executable_bits_marks_binaries(tmp_path: Path):
    binary = tmp_path / "app" / "demo"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o644)
    flarmhandler.ensure_executable_bits(tmp_path)
    if os.name != "nt":
        assert os.access(binary, os.X_OK)


def test_normalize_install_permissions_fixes_restrictive_modes(tmp_path: Path):
    if os.name == "nt":
        pytest.skip("los modos POSIX no aplican en Windows")
    (tmp_path / "app").mkdir()
    script = tmp_path / "app" / "demo"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    script.chmod(0o000)
    data = tmp_path / "app" / "data.json"
    data.write_text("{}\n", encoding="utf-8")
    data.chmod(0o000)

    fixed = flarmhandler.normalize_install_permissions(tmp_path)
    assert fixed >= 2
    # Los ficheros quedan legibles y escribibles por el propietario.
    assert os.access(data, os.R_OK) and os.access(data, os.W_OK)
    assert (data.stat().st_mode & 0o777) == 0o644
    # El bit de ejecución se conserva si ya estaba presente.
    script.chmod(0o755)
    flarmhandler.normalize_install_permissions(tmp_path)
    assert (script.stat().st_mode & 0o111) == 0o111


# --- Acento del sistema y geometría UWP ------------------------------------------


def _ensure_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    # Conservar referencia: si la QApplication se recolecta, Qt aborta el proceso.
    globals()["_QT_APP_REF"] = app
    return app


def test_system_accent_color_is_hex():
    accent = flarmhandler.system_accent_color()
    assert accent.startswith("#")
    assert len(accent) == 7
    int(accent[1:], 16)


def test_shade_and_tint_color():
    assert flarmhandler.shade_color("#0078D4", 0.90) == "#006CBE"
    assert flarmhandler.tint_color("#0078D4", 1.0) == "#FFFFFF"
    assert flarmhandler.tint_color("#0078D4", 0.0) == "#0078D4"
    # Entradas inválidas se devuelven sin cambios en vez de lanzar.
    assert flarmhandler.shade_color("no-es-color", 0.5) == "no-es-color"


def test_build_global_qss_injects_accent_without_leftover_placeholders():
    qss = flarmhandler.build_global_qss("#0078D4")
    assert "{accent" not in qss
    assert "#0078D4" in qss
    # La geometría UWP pide esquinas suaves y un panel de estado con acento.
    assert "#StatusPanel" in qss
    assert "border-radius: 4px" in qss
    assert "QPushButton#PrimaryBtn" in qss
    assert "QPushButton#DangerBtn" in qss


def test_render_app_icon_paints_accent_background():
    _ensure_app()
    transparent = _png_transparent(2, 2)
    pix = flarmhandler.render_app_icon(transparent, size=96, accent="#0078D4")
    assert pix is not None and pix.width() == 96 and pix.height() == 96
    # Con un icono transparente el fondo del cuadrado muestra el acento del SO.
    assert pix.toImage().pixelColor(2, 2).name() == "#0078d4"
    assert flarmhandler.render_app_icon(b"", size=96) is None
    assert flarmhandler.render_app_icon(b"no-es-imagen", size=96) is None


def test_install_window_header_uses_uwp_copy():
    _ensure_app()
    window = flarmhandler.InstallWindow(repo="suprr", owner="influent")
    try:
        assert window.title_lbl.text() == "¿Instalar suprr?"
        assert window.meta_lbl.text().startswith("Editor: influent")
        assert "Versión:" in window.ver_lbl.text()
        assert window.icon_label.width() == 96
        # Sin icono válido se muestran las iniciales sobre el color de acento.
        assert window.icon_label.text() == "S"
        assert window.accent in window.progress.styleSheet()
    finally:
        window.deleteLater()



# --- Integración de shell (freedesktop) ------------------------------------------


def test_register_package_associations_linux(tmp_path: Path):
    base = tmp_path / "share"
    result = package_shell.install_shell(
        handler_command='"/usr/bin/python" "handler.py" -l "%f"',
        icon_path=None,
        base_dir=base,
        platform_name="linux",
    )
    written = [Path(p) for p in result.written]
    mime = base / "mime" / "packages" / "flarmhandler.xml"
    assert mime in written
    assert "application/x-iflapp" in mime.read_text(encoding="utf-8")
    assert "application/x-asksome" in mime.read_text(encoding="utf-8")
    assert (base / "applications" / "flarmhandler-package.desktop").is_file()


def test_register_and_unregister_roundtrip(tmp_path: Path):
    base = tmp_path / "share"
    package_shell.install_shell(
        handler_command='"/usr/bin/python" "handler.py" -l "%f"',
        base_dir=base,
        platform_name="linux",
    )
    package_shell.uninstall_shell(base_dir=base, platform_name="linux")
    remaining = [p for p in base.rglob("*") if p.is_file()]
    assert remaining == []


def test_describe_package(iflapp_package: Path):
    info = package_shell.describe_package(iflapp_package)
    assert info["mime_type"] == "application/x-iflapp"
    assert "Demo App" in info["description"]
    assert "influent" in info["description"]


# --- Descriptores .mexf ----------------------------------------------------------


def test_mexf_plan_install_and_uninstall(tmp_path: Path):
    from lib import mexf_shell

    project = tmp_path / "proj" / ".mexf"
    project.mkdir(parents=True)
    (project / "main.mexf").write_text(
        "format: mexf\n"
        "version: 1\n"
        "metadata:\n"
        "  id: influent.demo\n"
        "  name: Demo Fluthin\n"
        "  version: v1.0-26.01-10.00\n"
        "icon: flarmhandler\n"
        "file_associations:\n"
        "  - extension: .iflapp\n"
        "    mime_type: application/x-iflapp\n"
        "    description: Paquete Fluthin\n"
        "    open_command: '\"flarmhandler\" -l \"%1\"'\n",
        encoding="utf-8",
    )
    base = tmp_path / "share"
    plan = mexf_shell.load_shell_plan(project.parent)
    assert plan.identifier == "influent.demo"
    result = mexf_shell.install_plan(plan, base_dir=base, platform_name="linux")
    assert result["written"]
    assert (base / "mime" / "packages" / "influent.demo.xml").is_file()

    removed = mexf_shell.uninstall_plan(plan, base_dir=base, platform_name="linux")
    assert removed["removed"]
