# -*- coding: utf-8 -*-
"""Integración de shell para paquetes ``.iflapp`` v2 y ``.asksome``.

Registra los tipos MIME y las asociaciones de archivo del ecosistema Fluthin
para que el explorador del sistema trate un ``.iflapp`` como cualquier otro
ejecutable: con su **icono** propio y su **descripción** en el panel de
propiedades y en el menú "Abrir con".

La identidad del paquete (publisher, app, nombre, versión, plataforma e icono)
se lee de la cabecera en claro del contenedor, sin descifrar ni descomprimir
el payload. Todo el módulo es puro salvo la escritura de los ficheros de
integración, de modo que se puede verificar sin GUI ni red.

Se apoya en :mod:`lib.native_shell` para la información de cabecera y el
generador de miniaturas, y reutiliza las constantes de tipo MIME para no
duplicar cadenas.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from xml.sax.saxutils import escape

from lib.native_shell import (
    ASKSOME_MIME,
    IFLAPP_MIME,
    export_icon_preview,
    package_info,
    write_thumbnailer,
)

# Nombre del tipo de archivo tal como lo verá el usuario en el escritorio.
IFLAPP_LABEL = "Paquete Fluthin"
ASKSOME_LABEL = "Aplicación Fluthin compilada"

#: Extensión -> (tipo MIME, etiqueta legible, descripción larga).
EXTENSIONS = {
    ".iflapp": (
        IFLAPP_MIME,
        IFLAPP_LABEL,
        "Paquete de instalación Fluthin (.iflapp)",
    ),
    ".asksome": (
        ASKSOME_MIME,
        ASKSOME_LABEL,
        "Aplicación Fluthin compilada desde .mexf (.asksome)",
    ),
}


@dataclass
class ShellRegistration:
    """Resultado de una operación de integración de shell."""

    written: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, List[str]]:
        return {
            "written": list(self.written),
            "removed": list(self.removed),
            "skipped": list(self.skipped),
        }


def _freedesktop_exec(command: str) -> str:
    """Normaliza un comando con marcadores de Windows al estilo freedesktop."""
    for marker in ("%1", "%V", "%v"):
        command = command.replace(marker, "%f")
    return command


def render_mime_xml(icon_name: str = "flarmhandler") -> str:
    """XML de ``shared-mime-info`` que declara ``.iflapp`` y ``.asksome``.

    Cada tipo lleva ``<comment>`` (descripción) y ``<icon>`` (nombre del icono
    instalado en el tema), que es lo que el explorador muestra en las
    propiedades y junto al nombre del archivo.
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">',
    ]
    for extension, (mime, _label, description) in EXTENSIONS.items():
        lines.append(f'  <mime-type type="{escape(mime)}">')
        lines.append(f"    <comment>{escape(description)}</comment>")
        lines.append(f"    <comment xml:lang=\"es\">{escape(description)}</comment>")
        lines.append(f'    <glob pattern="*{escape(extension)}"/>')
        lines.append(f'    <icon name="{escape(icon_name)}"/>')
        lines.append("  </mime-type>")
    lines.append("</mime-info>")
    return "\n".join(lines) + "\n"


def _desktop_entry(*, name: str, exec_cmd: str, mime_types: List[str], icon: str) -> str:
    mime = "".join(f"{value};" for value in mime_types)
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={name}\n"
        f"Exec={exec_cmd}\n"
        f"Icon={icon or 'application-x-executable'}\n"
        f"MimeType={mime}\n"
        "NoDisplay=true\n"
        "Terminal=false\n"
    )


def render_desktop_entry(
    *,
    exec_cmd: str,
    icon: str = "flarmhandler",
    name: str = "FlArm Handler",
    only_show_in: str = "",
) -> str:
    """``.desktop`` que abre un paquete con el handler y lo asocia a su MIME."""
    body = _desktop_entry(
        name=name,
        exec_cmd=_freedesktop_exec(exec_cmd),
        mime_types=[mime for mime, _label, _desc in EXTENSIONS.values()],
        icon=icon,
    )
    if only_show_in:
        body += f"OnlyShowIn={only_show_in};\n"
    return body


def _reg_section(lines: List[str], path: str, values: Dict[str, str]) -> None:
    lines.append(f"[{path}]")
    for key, value in values.items():
        if key:
            lines.append(f'"{key}"="{value}"')
        else:
            lines.append(f'@="{value}"')
    lines.append("")


def _reg_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def render_registry(
    *,
    handler_command: str,
    icon_path: str,
) -> str:
    """Fichero ``.reg`` que asocia ``.iflapp``/``.asksome`` con icono y tipo.

    ``handler_command`` es la línea de comandos que abre un paquete (con el
    marcador ``%1``); se escribe dos veces: una para el protocolo y otra para
    la apertura de archivo. ``icon_path`` se toma del icono real del handler.
    """
    lines = ["Windows Registry Editor Version 5.00", ""]
    open_cmd = _reg_escape(handler_command)
    icon = _reg_escape(icon_path)
    for extension, (mime, label, description) in EXTENSIONS.items():
        prog_id = "Fluthin.Package" if extension == ".iflapp" else "Fluthin.Asksome"
        _reg_section(lines, rf"HKEY_CLASSES_ROOT\{extension}", {"": prog_id})
        values = {"": label, "FriendlyTypeName": description}
        _reg_section(lines, rf"HKEY_CLASSES_ROOT\{prog_id}", values)
        _reg_section(
            lines,
            rf"HKEY_CLASSES_ROOT\{prog_id}\DefaultIcon",
            {"": f"{icon},0"},
        )
        _reg_section(
            lines,
            rf"HKEY_CLASSES_ROOT\{prog_id}\shell\open\command",
            {"": open_cmd},
        )
        _reg_section(lines, rf"HKEY_CLASSES_ROOT\{prog_id}\Content Type", {"": mime})
    return "\n".join(lines).rstrip() + "\n"


def _write(path: Path, content: str, written: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    written.append(str(path))


def _write_icon(base: Path, source: Optional[Path], written: List[str]) -> str:
    """Instala el icono del handler en el tema de iconos del usuario.

    Devuelve el nombre del icono (sin extensión) tal como se referencia desde
    los ``.desktop`` y el XML de MIME.
    """
    if not source or not Path(source).is_file():
        return "flarmhandler"
    import shutil

    destination = base / "icons" / "hicolor" / "256x256" / "apps" / "flarmhandler.ico"
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(str(source), str(destination))
        written.append(str(destination))
    except OSError:
        return "flarmhandler"
    return "flarmhandler"


def install_shell(
    *,
    handler_command: str,
    icon_path: Optional[Path | str] = None,
    base_dir: Optional[Path | str] = None,
    platform_name: Optional[str] = None,
    thumbnailer: bool = True,
) -> ShellRegistration:
    """Registra ``.iflapp``/``.asksome`` con icono y descripción.

    En Linux/macOS (freedesktop) escribe el XML de MIME, el ``.desktop`` del
    handler, el icono en el tema y el generador de miniaturas; en Windows
    genera un ``.reg`` para importar. Nunca lanza si el destino no se puede
    escribir: informa en ``skipped``.
    """
    platform_name = platform_name or sys.platform
    result = ShellRegistration()
    icon_source = Path(icon_path) if icon_path else None

    if platform_name.startswith("win"):
        directory = Path(base_dir) if base_dir else Path.cwd()
        try:
            reg = directory / "flarmhandler-shell.reg"
            reg.parent.mkdir(parents=True, exist_ok=True)
            reg.write_text(
                render_registry(
                    handler_command=handler_command,
                    icon_path=str(icon_source or "flarmhandler.ico"),
                ),
                encoding="utf-16",
            )
            result.written.append(str(reg))
        except OSError as exc:
            result.skipped.append(f"{directory}: {exc}")
        return result

    base = Path(base_dir) if base_dir else Path.home() / ".local" / "share"
    try:
        icon_name = _write_icon(base, icon_source, result.written)
        _write(
            base / "mime" / "packages" / "flarmhandler.xml",
            render_mime_xml(icon_name=icon_name),
            result.written,
        )
        _write(
            base / "applications" / "flarmhandler-package.desktop",
            render_desktop_entry(exec_cmd=handler_command, icon=icon_name),
            result.written,
        )
        if thumbnailer:
            entry = write_thumbnailer(base / "thumbnailers", name="flarmhandler")
            # ``write_thumbnailer`` escribe también el runner ejecutable; se
            # registran ambos para que el conteo coincida con lo instalado.
            result.written.append(str(entry))
            result.written.append(str(entry.with_name("flarmhandler-thumbnailer")))
    except OSError as exc:
        result.skipped.append(f"{base}: {exc}")
    return result


def uninstall_shell(
    *,
    base_dir: Optional[Path | str] = None,
    platform_name: Optional[str] = None,
) -> ShellRegistration:
    """Retira los ficheros escritos por :func:`install_shell`."""
    platform_name = platform_name or sys.platform
    result = ShellRegistration()

    if platform_name.startswith("win"):
        directory = Path(base_dir) if base_dir else Path.cwd()
        reg = directory / "flarmhandler-shell.reg"
        if reg.exists():
            reg.unlink()
            result.removed.append(str(reg))
        return result

    base = Path(base_dir) if base_dir else Path.home() / ".local" / "share"
    targets = [
        base / "mime" / "packages" / "flarmhandler.xml",
        base / "applications" / "flarmhandler-package.desktop",
        base / "icons" / "hicolor" / "256x256" / "apps" / "flarmhandler.ico",
        base / "thumbnailers" / "flarmhandler.thumbnailer",
        base / "thumbnailers" / "flarmhandler-thumbnailer",
    ]
    for target in targets:
        try:
            if target.exists():
                target.unlink()
                result.removed.append(str(target))
        except OSError as exc:
            result.skipped.append(f"{target}: {exc}")
    return result


def describe_package(path: Path | str) -> Dict[str, str]:
    """Descripción corta de un paquete para logs y menús contextuales.

    No descifra el payload: usa sólo la cabecera en claro.
    """
    info = package_info(path)
    identity = info.get("identity", {})
    name = identity.get("name") or identity.get("app") or Path(path).stem
    version = identity.get("version", "")
    publisher = identity.get("publisher", "")
    parts = [part for part in (publisher, version) if part]
    suffix = f" ({', '.join(parts)})" if parts else ""
    return {
        "name": name,
        "description": f"{name}{suffix}",
        "mime_type": info.get("mime_type", ""),
        "icon_bytes": str(info.get("icon_bytes", 0)),
    }


def export_preview(path: Path | str, out_dir: Path | str, *, size: int = 256) -> Optional[Path]:
    """Vuelca el icono del paquete a PNG (delegado en ``native_shell``)."""
    return export_icon_preview(path, out_dir, size=size)
