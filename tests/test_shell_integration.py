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
