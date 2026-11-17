#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fluthin Armadillo Store handler (PyQt5 + Markdown + Custom Titlebar + Orange Theme)
"""

from __future__ import annotations
import sys, os, platform, tempfile, shutil, zipfile, tarfile, re, json, webbrowser, subprocess, time, ctypes
from pathlib import Path
from PyQt6 import QtWidgets, QtGui, QtCore, QtSvg

# ``QtSvg`` se importa por su efecto lateral: registra el plugin de imagen SVG
# en QtGui, aunque el módulo no lo use de forma directa.
_SVG_PLUGIN = QtSvg

# ``requests`` sólo se usa en el modo online (GitHub). Las acciones de shell y
# la lectura de cabecera deben funcionar sin él, así que su ausencia no impide
# registrar las asociaciones en un sistema mínimo.
try:
    import requests
    HAS_REQUESTS = True
except Exception:
    requests = None
    HAS_REQUESTS = False

# --- Contenedores .iflapp v2 / .asksome e integración de shell ---
# El paquete se instala como una app del ecosistema Fluthin, así que la lectura
# de cabecera y la asociación de tipos MIME viven en ``lib`` y se reutilizan
# aquí en vez de reimplementar el formato binario.
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib import qss_loader

try:
    from lib import iflapp_format as _iflapp_format
    from lib import asksome_format as _asksome_format
    from lib import native_shell as _native_shell
    from lib import package_shell as _package_shell
    HAS_PACKAGE_LIBS = True
except Exception as _pkg_exc:  # pragma: no cover - entorno incompleto
    HAS_PACKAGE_LIBS = False
    _PACKAGE_LIBS_ERROR = str(_pkg_exc)

# --- Splash integrado (Fase 2 del plan maestro) ---
# La lógica del splash vive en ``lib/splash_screen`` para poder reutilizarla
# como librería global (Fase 3, inyección bootloader).
try:
    from lib import splash_screen as _splash
    HAS_SPLASH_LIB = True
except Exception:  # pragma: no cover - entorno incompleto
    _splash = None
    HAS_SPLASH_LIB = False

# --- Efecto Mica (leviathan-ui, opcional) ---
try:
    from leviathan_ui import WipeWindow as _WipeWindow
    HAS_WIPE_WINDOW = True
except Exception:  # pragma: no cover - leviathan-ui ausente
    _WipeWindow = None
    HAS_WIPE_WINDOW = False

# --- Vista Markdown opcional (QtWebEngine de PyQt6 + módulo markdown) ---
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    import markdown
    HAS_MARKDOWN = True
except Exception:
    QWebEngineView = None
    HAS_MARKDOWN = False

# --- Custom titlebar button icons (Windows 11 Style SVGs) ---
WIN11_ICONS = {
    "close": "M 10.5 10.5 L 21.5 21.5 M 21.5 10.5 L 10.5 21.5", # Thin X
    "minimize": "M 11 21 H 21", # Bottom line
    "maximize": "M 10.5 10.5 H 21.5 V 21.5 H 10.5 Z", # Square
    "restore": "M 12.5 14.5 V 10.5 H 22.5 V 20.5 H 18.5 M 10.5 12.5 H 18.5 V 22.5 H 10.5 Z" # Overlapping squares
}

# Optional Windows helpers
HAS_PYWIN32 = False
try:
    import winreg
except Exception:
    winreg = None
try:
    import pythoncom  # noqa: F401  (sonda de disponibilidad de pywin32)
    import win32com.client  # type: ignore
    HAS_PYWIN32 = True
    _PYWIN32_PROBE = pythoncom
except Exception:
    HAS_PYWIN32 = False
    _PYWIN32_PROBE = None

DEFAULT_SPLASH = "assets/splash.png"
DEFAULT_ICON = "assets/product_logo.png"
SPLASH_SETUP = "assets/splash_setup.png"
GITHUB_RELEASES_API = "https://api.github.com/repos/{owner}/{repo}/releases"
SCHEME = "Fluthinstore"
MIMETYPE = "application/x-Fluthinstore"
# Margen (px) de los bordes por los que la ventana frameless se redimensiona.
RESIZE_MARGIN = 6

# --- Color de acento del sistema operativo ---
# El instalador debe teñirse con el acento del SO (estilo Windows App Installer).
# Si no se puede determinar se usa el azul de Windows 11, de modo que la
# interfaz nunca quede sin acento.
DEFAULT_ACCENT = "#0078D4"
_GNOME_ACCENTS = {
    "blue": "#3584E4", "teal": "#2190A4", "green": "#3A944A",
    "yellow": "#C88800", "orange": "#ED5B00", "red": "#E62D42",
    "pink": "#D56199", "purple": "#9141AC", "slate": "#6F8396",
}


def system_accent_color() -> str:
    """Devuelve el color de acento del SO como ``#RRGGBB``.

    Windows: lee ``AccentColor`` de DWM (DWORD en orden ABGR). Linux: consulta
    ``gsettings`` de GNOME. Cualquier fallo cae al azul por defecto.
    """
    if platform.system().lower().startswith("win") and winreg is not None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM") as key:
                value, _ = winreg.QueryValueEx(key, "AccentColor")
            blue, green, red = value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF
            return f"#{red:02X}{green:02X}{blue:02X}"
        except OSError:
            pass
    else:
        try:
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "accent-color"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                name = result.stdout.strip().strip("'").lower()
                if name in _GNOME_ACCENTS:
                    return _GNOME_ACCENTS[name]
        except (OSError, subprocess.SubprocessError):
            pass
    return DEFAULT_ACCENT


def shade_color(color: str, factor: float) -> str:
    """Aclara (``factor > 1``) u oscurece (``factor < 1``) un ``#RRGGBB``."""
    try:
        red = int(color[1:3], 16)
        green = int(color[3:5], 16)
        blue = int(color[5:7], 16)
    except (ValueError, IndexError):
        return color
    clamp = lambda v: max(0, min(255, int(v * factor)))
    return f"#{clamp(red):02X}{clamp(green):02X}{clamp(blue):02X}"


def tint_color(color: str, amount: float) -> str:
    """Mezcla ``color`` hacia blanco en la proporción ``amount`` (0..1).

    Se usa para los fondos tenues del acento (p. ej. hover del botón
    secundario); multiplicar los canales saturaba a cian/blanco puro.
    """
    try:
        red = int(color[1:3], 16)
        green = int(color[3:5], 16)
        blue = int(color[5:7], 16)
    except (ValueError, IndexError):
        return color
    amount = max(0.0, min(1.0, amount))
    blend = lambda channel: int(channel + (255 - channel) * amount)
    return f"#{blend(red):02X}{blend(green):02X}{blend(blue):02X}"


def render_app_icon(data: bytes, size: int = 96, accent: str = DEFAULT_ACCENT) -> "QtGui.QPixmap | None":
    """Pixmap cuadrado del icono, rellenando el fondo con el acento si es transparente.

    El icono del paquete suele venir con fondo transparente; el instalador UWP
    lo coloca sobre un cuadrado del color de acento del SO. Devuelve ``None`` si
    los bytes no son una imagen válida.
    """
    source = QtGui.QPixmap()
    if not data or not source.loadFromData(data):
        return None
    canvas = QtGui.QPixmap(size, size)
    canvas.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(canvas)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    # Fondo de acento con esquinas suavemente redondeadas (geometría UWP).
    painter.setPen(QtCore.Qt.PenStyle.NoPen)
    painter.setBrush(QtGui.QColor(accent))
    painter.drawRoundedRect(0, 0, size, size, 6, 6)
    scaled = source.scaled(
        size, size,
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

# --- Hojas de estilo (un fichero por control Qt en ``source/qss/``) ---
# ``source/qss/{qtcontrolid}.qss`` es la única fuente de estilos: cada archivo
# agrupa las reglas de un control (QPushButton, QLabel, ...) y usa marcadores
# ``__ACCENT__``/``__ACCENT_HOVER__``/``__ACCENT_PRESSED__``/``__ACCENT_SOFT__``
# que ``build_global_qss`` resuelve con el acento del SO. La lectura la hace
# ``lib/qss_loader.py`` (mismo contrato que packagemaker), así los estilos se
# editan sin tocar el código.
QSS_DIR = qss_loader.QSS_DIR


def build_global_qss(accent: str | None = None) -> str:
    """Devuelve la hoja global con el acento del SO inyectado en los marcadores."""
    accent = accent or system_accent_color()
    replacements = {
        "ACCENT": accent,
        "ACCENT_HOVER": shade_color(accent, 0.90),
        "ACCENT_PRESSED": shade_color(accent, 0.78),
        "ACCENT_SOFT": tint_color(accent, 0.88),
    }
    return qss_loader.render(qss_loader.load_parts(), replacements)


# --- Banner de cabecera según la orientación de la pantalla ---
# El banner es el encabezado dentro de la propia ventana (no confundir con el
# splash de arranque, que ya no usa assets). En horizontal se usa el splash
# ancho; en vertical, el banner de setup (más cuadrado).
LANDSCAPE, PORTRAIT, SQUARE = "landscape", "portrait", "square"


def screen_orientation() -> str:
    """Clasifica la pantalla principal en ``landscape``/``portrait``/``square``."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        return LANDSCAPE
    screen = app.primaryScreen()
    if screen is None:
        return LANDSCAPE
    geo = screen.availableGeometry()
    return _orientation_for(geo.width(), geo.height())


def _orientation_for(width: int, height: int) -> str:
    if width > height:
        return LANDSCAPE
    if height > width:
        return PORTRAIT
    return SQUARE


def banner_candidates(app_name: str, orientation: str) -> list[str]:
    """Nombres de asset del banner, del más específico al genérico."""
    app = (app_name or "").strip().lower()
    names: list[str] = []
    if app:
        if orientation == PORTRAIT:
            names.append(f"{app}-portraitSplash.png")
        names.append(f"{app}-landscapeSplash.png")
    if orientation == PORTRAIT:
        names += ["splash_setup.png", "splash_Setup.png", "splash.png"]
    else:
        names += ["splash.png", "splash_setup.png", "splash_Setup.png"]
    seen: set[str] = set()
    return [n for n in names if not (n in seen or seen.add(n))]


def find_banner_asset(assets_dir: Path | None, app_name: str,
                      orientation: str, has_assets: bool = True) -> Path | None:
    """Primer asset de banner existente en *assets_dir*, o ``None``."""
    if not has_assets or assets_dir is None or not Path(assets_dir).is_dir():
        return None
    for name in banner_candidates(app_name, orientation):
        candidate = Path(assets_dir) / name
        if candidate.is_file():
            return candidate
    return None


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin(argv=None):
    if argv is None:
        argv = sys.argv
    if hasattr(sys, '_MEIPASS'):
        # Frozen: executable is the app itself, args are the rest
        arguments = map(str, argv[1:])
        executable = sys.executable
    else:
        # Script: executable is python, first arg is script (make absolute), rest are args
        args = list(argv)
        args[0] = os.path.abspath(args[0])
        arguments = map(str, args)
        executable = sys.executable
    
    argument_line = u' '.join(f'"{a}"' if ' ' in a else a for a in arguments)
    
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, argument_line, None, 1)
    return int(ret) > 32

CANONICAL_NAME_RE = re.compile(
    r"^(?P<publisher>[^-.]+)\.(?P<app>[^-.]+)\.(?P<version>v[^-]+)-(?P<stamp>\d{2}\.\d{2}-\d{2}\.\d{2})-(?P<platform>[^-]+)$"
)

PLATFORM_ALIASES = {
    "linux": "Danenone",
    "danenone": "Danenone",
    "windows": "Knosthalij",
    "win": "Knosthalij",
    "knosthalij": "Knosthalij",
    "multiplatform": "AlphaCube",
    "multi": "AlphaCube",
    "alphacube": "AlphaCube",
}


def normalize_platform(value: str) -> str:
    """Normaliza el sufijo de plataforma a una de las tres canónicas."""
    return PLATFORM_ALIASES.get((value or "").strip().lower(), (value or "").strip())


def parse_package_filename(filename: str) -> dict:
    """Descompone un nombre de paquete en sus partes.

    Acepta el nombre canónico
    ``publisher.app.vX.x-YY.MM-HH.MM-Platform`` y, como respaldo, el formato
    histórico ``nombre-version-plataforma``. Devuelve ``publisher``, ``app``,
    ``version`` y ``platform`` (``""`` si no se pudo reconocer).
    """
    stem = Path(filename).stem
    match = CANONICAL_NAME_RE.match(stem)
    if match:
        parts = match.groupdict()
        return {
            "publisher": parts["publisher"],
            "app": parts["app"],
            "version": parts["version"],
            "platform": normalize_platform(parts["platform"]),
        }
    legacy = re.match(r"^(.+?)-([0-9A-Za-z.\-_]+)-([0-9A-Za-z._\-]+)$", stem, re.IGNORECASE)
    if legacy:
        return {
            "publisher": "",
            "app": legacy.group(1),
            "version": legacy.group(2),
            "platform": normalize_platform(legacy.group(3)),
        }
    return {"publisher": "", "app": stem, "version": "", "platform": ""}


def platform_tag() -> str:
    sysplat = platform.system().lower()
    if 'windows' in sysplat or 'win' in sysplat:
        return 'Knosthalij'
    return 'Danenone'

def check_platform_compatibility(target_platform: str) -> tuple[bool, str]:
    """
    Checks if the target platform (from details.xml) is compatible with the current OS.
    Returns (is_compatible, error_message).
    """
    current_os_tag = platform_tag()
    target = target_platform.lower() if target_platform else ""
    
    # If target is empty, we assume it's universal or unknown, so we allow it (or maybe warn?)
    # For now, let's be permissive if unknown, but strict if known.
    if not target:
        return True, ""

    if current_os_tag == 'Knosthalij': # Windows
        if 'danenone' in target:
            return False, "Este paquete está diseñado para Linux (Danenone) y no es compatible con Windows."
    
    elif current_os_tag == 'Danenone': # Linux/Mac (simplified)
        if 'knosthalij' in target:
            return False, "Este paquete está diseñado para Windows (Knosthalij) y no es compatible con este sistema."
            
    return True, ""

def parse_Fluthin_url(url: str) -> tuple[str, str]:
    if not isinstance(url, str) or not url.strip():
        raise ValueError("No URL provided")
    clean_url = url.strip()
    accepted_schemes = ("fluthinstore://", "flarmstore://", "fluthinstore:", "flarmstore:")
    lower_url = clean_url.lower()
    for scheme in accepted_schemes:
        if lower_url.startswith(scheme):
            clean_url = clean_url[len(scheme):]
            break
    if clean_url.endswith('/'):
        clean_url = clean_url[:-1]
    parts = clean_url.split('.')
    if len(parts) >= 2:
        owner = parts[0]
        repo = '.'.join(parts[1:])
        return repo, owner
    else:
        raise ValueError(f"URL inválida: {url}. Debe ser Fluthinstore://username.repo")

def best_asset_for_platform(assets: list, shortname: str) -> tuple[dict | None, str | None, str | None]:
    """Elige el asset ``.iflapp`` compatible con la plataforma actual.

    Usa :func:`parse_package_filename`, así que entiende tanto el nombre
    canónico ``publisher.app.vX.x-YY.MM-HH.MM-Platform`` como el histórico.
    Devuelve ``(asset, version, plataforma)`` o ``(None, None, None)``.
    """
    current = platform_tag()
    aliases = {
        "Danenone": ("danenone", "linux", "mac", "macos", "darwin"),
        "Knosthalij": ("knosthalij", "windows", "win"),
        "AlphaCube": ("alphacube", "multi", "multiplatform"),
    }
    wanted = aliases.get(current, ())

    def platform_matches(platform_value: str) -> bool:
        value = (platform_value or "").lower()
        return any(alias in value for alias in wanted)

    # 1) Asset con plataforma compatible.
    for a in assets:
        name = a.get('name', '')
        if not name.lower().endswith('.iflapp'):
            continue
        parsed = parse_package_filename(name)
        if platform_matches(parsed["platform"]):
            return a, parsed["version"], parsed["platform"]

    # 2) Asset cuyo app coincide con el shortname, aunque no declare plataforma.
    for a in assets:
        name = a.get('name', '')
        if not name.lower().endswith('.iflapp'):
            continue
        parsed = parse_package_filename(name)
        if shortname and parsed["app"].lower() == shortname.lower():
            return a, parsed["version"], parsed["platform"]

    return None, None, None

def download_file(url: str, dest_path: str, progress_callback=None) -> str:
    if not HAS_REQUESTS:
        raise RuntimeError("Se requiere el módulo 'requests' para descargar paquetes (modo online).")
    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        total_length = r.headers.get('content-length')
        dl = 0
        total_length = int(total_length) if total_length else None
        
        with open(dest_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    dl += len(chunk)
                    f.write(chunk)
                    if progress_callback and total_length:
                        progress_callback(int(dl * 100 / total_length))
    return dest_path

def _safe_extract_member(base: Path, member_name: str) -> Path:
    """Return a safe extraction target or raise for path traversal."""
    target = (base / member_name).resolve()
    if target != base and base not in target.parents:
        raise ValueError(f"Ruta insegura en paquete: {member_name}")
    return target


def _package_kind(file_path: str) -> str:
    """Clasifica el contenedor: ``iflapp2``, ``asksome``, ``zip`` o ``unknown``."""
    if not HAS_PACKAGE_LIBS:
        return "unknown"
    try:
        data = Path(file_path).read_bytes()[:16]
    except OSError:
        return "unknown"
    if data.startswith(_asksome_format.MAGIC):
        return "asksome"
    return _iflapp_format.sniff_format(file_path)


def read_package_identity(file_path: str) -> dict:
    """Identidad de un paquete leída de su cabecera, sin descifrar el payload.

    Devuelve las mismas claves que ``parse_details_xml`` (``name``,
    ``publisher``, ``app``, ``version``, ``platform``, ``author``) para que el
    resto del flujo no distinga entre un ``.iflapp`` v2, un ``.asksome`` o el
    ZIP histórico.
    """
    if not HAS_PACKAGE_LIBS:
        return {}
    kind = _package_kind(file_path)
    if kind == "asksome":
        header = _asksome_format.read_asksome_header(file_path)
        metadata = dict(header.get("metadata", {}))
        return {
            "name": metadata.get("name", ""),
            "publisher": metadata.get("publisher", ""),
            "app": metadata.get("app", ""),
            "version": metadata.get("version", ""),
            "platform": metadata.get("platform", ""),
            "author": metadata.get("author") or metadata.get("signer", ""),
        }
    if kind == "iflapp2":
        header = _iflapp_format.read_iflapp_header(file_path)
        return dict(header.identity())
    if kind == "zip":
        try:
            with zipfile.ZipFile(file_path, "r") as archive:
                if "details.xml" in archive.namelist():
                    return parse_details_xml(
                        archive.read("details.xml").decode("utf-8", errors="replace")
                    )
        except (zipfile.BadZipFile, KeyError, OSError):
            return {}
    return {}


def read_package_icon(file_path: str) -> bytes:
    """Bytes del icono de cabecera del paquete (vacío si no hay o no aplica)."""
    if not HAS_PACKAGE_LIBS:
        return b""
    try:
        kind = _package_kind(file_path)
        if kind in ("iflapp2", "asksome"):
            data = _native_shell.icon_bytes(file_path)
            return data or b""
    except Exception:
        return b""
    return b""


def extract_archive(file_path: str, extract_to: str) -> bool:
    """Extrae un paquete ``.iflapp`` v2, ``.asksome``, ZIP o TAR en *extract_to*.

    El contenedor ``.iflapp`` v2 y el ``.asksome`` no son ZIP: se delegan en
    ``lib.iflapp_format`` / ``lib.asksome_format``, que ya aplican la
    verificación de firma y la protección contra traversal. El ZIP y el TAR
    históricos conservan las salvaguardas locales.
    """
    file_path = str(file_path)
    base = Path(extract_to).resolve()
    base.mkdir(parents=True, exist_ok=True)

    kind = _package_kind(file_path)
    if kind == "iflapp2" and HAS_PACKAGE_LIBS:
        _iflapp_format.extract_iflapp(file_path, base)
        return True
    if kind == "asksome" and HAS_PACKAGE_LIBS:
        _asksome_format.extract_asksome(file_path, base)
        return True

    if zipfile.is_zipfile(file_path):
        with zipfile.ZipFile(file_path, 'r') as z:
            for member in z.infolist():
                _safe_extract_member(base, member.filename)
            z.extractall(base)
        return True
    try:
        if tarfile.is_tarfile(file_path):
            with tarfile.open(file_path, 'r:*') as archive:
                for member in archive.getmembers():
                    _safe_extract_member(base, member.name)
                    if member.issym() or member.islnk():
                        raise ValueError(f"Enlace inseguro en paquete: {member.name}")
                archive.extractall(base)
            return True
    except (tarfile.TarError, ValueError):
        return False
    dest = base / Path(file_path).name
    shutil.copy(file_path, str(dest))
    return False

def find_executable(root_dir: Path, shortname: str) -> Path | None:
    root = Path(root_dir)
    for p in root.rglob('*'):
        if p.is_file():
            name = p.name.lower()
            if name == f"{shortname.lower()}.exe":
                return p
            if name == shortname.lower():
                try:
                    if os.name != 'nt':
                        if os.access(p, os.X_OK):
                            return p
                    else:
                        return p
                except Exception:
                    return p
            if name == f"{shortname.lower()}.elf":
                return p
    return None

def create_documents_app_folder(publisher: str, app: str, version: str, platformstr: str) -> Path:
    home = Path.home()
    if os.name == 'nt':
        documents = Path(os.path.join(os.environ.get('USERPROFILE',''), 'Documents'))
    else:
        documents = home / 'Documents'
    # Nombre canónico: {publisher}.{app}.{version}-{platform} (igual que
    # ``find_installed_package``, que busca exactamente esta carpeta).
    base = documents / 'Fluthin Apps' / f"{publisher}.{app}.{version}-{platformstr}"
    base.mkdir(parents=True, exist_ok=True)
    return base

def move_install_tree(temp_extract_dir: Path, target_dir: Path) -> Path:
    targ = Path(target_dir)
    for item in Path(temp_extract_dir).iterdir():
        dest = targ / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(item), str(dest))
        else:
            if dest.exists():
                dest.unlink()
            shutil.move(str(item), str(dest))
    return targ

def ensure_executable_bits(root_dir: Path) -> list[str]:
    """Da permiso de ejecución a los binarios instalados.

    El tar del contenedor puede no conservar el bit ``+x``, y sin él el
    lanzador no encuentra el ejecutable. Se marcan los ficheros sin extensión
    y los ``.elf``/``.sh`` bajo ``app`` y ``bin``.
    """
    marked: list[str] = []
    if os.name == 'nt':
        return marked
    root = Path(root_dir)
    for folder in ("app", "bin"):
        candidate = root / folder
        if not candidate.is_dir():
            continue
        for path in candidate.rglob('*'):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix in ("", ".elf", ".sh", ".run", ".bin"):
                try:
                    path.chmod(path.stat().st_mode | 0o111)
                    marked.append(str(path))
                except OSError:
                    pass
    return marked


def normalize_install_permissions(root_dir: Path) -> int:
    """Normaliza los permisos del árbol instalado a valores funcionales.

    Un ZIP o TAR puede traer entradas con modo restrictivo (``000``) o sin
    permiso de escritura para el propietario, y entonces la app instalada no
    puede leer sus propios recursos. Se dejan los directorios en ``0o755`` y
    los ficheros en ``0o644``, conservando el bit de ejecución ya presente.
    En Windows se limpia el atributo de sólo lectura. Devuelve cuántas entradas
    se corrigieron.
    """
    root = Path(root_dir)
    if not root.is_dir():
        return 0

    if os.name == 'nt':
        fixed = 0
        for path in root.rglob('*'):
            try:
                if path.is_file() and not os.access(path, os.W_OK):
                    os.chmod(path, 0o666)
                    fixed += 1
            except OSError:
                pass
        return fixed

    fixed = 0
    for path in root.rglob('*'):
        try:
            mode = path.stat().st_mode
            executable = mode & 0o111
            wanted = 0o755 if path.is_dir() else (0o644 | executable)
            if (mode & 0o777) != wanted:
                path.chmod(wanted)
                fixed += 1
        except OSError:
            pass
    return fixed

def create_shortcut(desktop_path: Path, target: Path, name: str, args: str = "") -> str:
    desktop_path.mkdir(parents=True, exist_ok=True)
    system = platform.system().lower()
    if 'windows' in system:
        if HAS_PYWIN32:
            shortcut_path = str(desktop_path / (name + '.lnk'))
            try:
                shell = win32com.client.Dispatch("WScript.Shell")
                lnk = shell.CreateShortCut(shortcut_path)
                lnk.Targetpath = str(target)
                lnk.Arguments = args
                lnk.WorkingDirectory = str(target.parent)
                lnk.IconLocation = str(target)
                lnk.save()
                return shortcut_path
            except Exception:
                pass
        url_path = desktop_path / (name + '.url')
        content = "[InternetShortcut]\nURL=file:///" + str(target).replace('\\', '/') + "\n"
        url_path.write_text(content, encoding='utf-8')
        return str(url_path)
    elif 'linux' in system:
        file_path = desktop_path / (name + '.desktop')
        content = "[Desktop Entry]\nType=Application\nName=" + name + "\nExec=" + str(target) + " " + args + "\nTerminal=false\nIcon=\nCategories=Utility;\n"
        file_path.write_text(content, encoding='utf-8')
        file_path.chmod(0o755)
        return str(file_path)
    elif 'darwin' in system:
        file_path = desktop_path / (name + '.command')
        content = "#!/bin/bash\n\"" + str(target) + "\" " + args + "\n"
        file_path.write_text(content, encoding='utf-8')
        file_path.chmod(0o755)
        return str(file_path)
    else:
        file_path = desktop_path / (name + '.desktop')
        file_path.write_text(f"[Desktop Entry]\nName={name}\nExec={str(target)} {args}\nTerminal=false\n", encoding='utf-8')
        try:
            file_path.chmod(0o755)
        except Exception:
            pass
        return str(file_path)

# --- Registry & Protocol Registration ---
def check_registry_keys(python_path: str, script_path: str) -> tuple[bool, list[str]]:
    """Check registry keys and return (is_valid, list_of_issues)."""
    if winreg is None: 
        return False, ["winreg module not available"]
    
    # Expected commands with flags based on execution mode
    if getattr(sys, 'frozen', False):
        # Compiled: "C:\Path\To\App.exe" -u "%1"
        exe_path = python_path
        expected_cmd_protocol = f'"{exe_path}" -u "%1"'
        expected_cmd_file = f'"{exe_path}" -l "%1"'
    else:
        # Script: "python.exe" "script.py" -u "%1"
        expected_cmd_protocol = f'"{python_path}" "{script_path}" -u "%1"'
        expected_cmd_file = f'"{python_path}" "{script_path}" -l "%1"'
        
    expected_icon = get_icon_path()
    issues = []
    
    def normalize_path(s):
        """Normalize paths for comparison, handling quotes and case."""
        if not s:
            return ""
        # Remove quotes and normalize
        s = s.strip().strip('"').strip("'")
        return os.path.normcase(os.path.abspath(s))
    
    def normalize_cmd(cmd):
        """Normalize command strings for comparison."""
        if not cmd:
            return ""
        # Remove extra spaces, normalize quotes and case
        # Replace different quote styles
        cmd = cmd.replace("'", '"')
        # Normalize multiple spaces to single space
        cmd = ' '.join(cmd.split())
        return cmd.lower()
    
    def extract_paths_from_cmd(cmd):
        """Extract paths from a command string (1 or 2 paths)."""
        if not cmd:
            return None, None
        
        import re
        # Pattern 1: "python" "script" -flag ...
        pattern_script = r'"([^"]+)"\s+"([^"]+)"'
        match_script = re.search(pattern_script, cmd)
        
        if match_script:
            return normalize_path(match_script.group(1)), normalize_path(match_script.group(2))
            
        # Pattern 2: "exe" -flag ...
        pattern_exe = r'"([^"]+)"'
        match_exe = re.search(pattern_exe, cmd)
        
        if match_exe:
            # Return exe path as first arg, None as second
            return normalize_path(match_exe.group(1)), None
            
        return None, None

    # Helper to check a key with better error reporting
    def check_key(root, key_path, expected_val=None, key_name=""):
        try:
            key = winreg.OpenKey(root, key_path)
            val, _ = winreg.QueryValueEx(key, "")
            winreg.CloseKey(key)
            
            if expected_val:
                # For commands, normalize and compare
                if "command" in key_path.lower():
                    val_norm = normalize_cmd(val)
                    exp_norm = normalize_cmd(expected_val)
                    
                    if val_norm != exp_norm:
                        # Check if it's just a path mismatch
                        reg_py, reg_scr = extract_paths_from_cmd(val)
                        exp_py, exp_scr = extract_paths_from_cmd(expected_val)
                        
                        if reg_py and exp_py:
                            # Compare first path (Python or Exe)
                            if reg_py != exp_py:
                                issues.append(f"{key_name}: ruta principal cambió ({os.path.basename(reg_py)} → {os.path.basename(exp_py)})")
                                return False
                            
                            # Compare second path (Script) if expected
                            if exp_scr:
                                if not reg_scr or reg_scr != exp_scr:
                                    issues.append(f"{key_name}: ruta del script cambió ({os.path.basename(reg_scr) if reg_scr else 'None'} → {os.path.basename(exp_scr)})")
                                    return False
                            elif reg_scr:
                                # We didn't expect a script path but got one (switched from script to exe?)
                                issues.append(f"{key_name}: tipo de ejecución cambió (Script → Exe)")
                                return False
                        
                        issues.append(f"{key_name}: comando desactualizado")
                        return False
                else:
                    if val.lower() != expected_val.lower():
                        issues.append(f"{key_name}: valor no coincide")
                        return False
            return True
        except FileNotFoundError:
            issues.append(f"{key_name}: clave no existe")
            return False
        except Exception as e:
            issues.append(f"{key_name}: error al leer ({str(e)})")
            return False

    # 1. Check Protocol in HKCU or HKCR
    protocol_ok = check_key(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{SCHEME}\shell\open\command", 
                           expected_cmd_protocol, "Protocolo Fluthinstore (HKCU)")
    if not protocol_ok:
        # Try HKCR as fallback
        protocol_ok = check_key(winreg.HKEY_CLASSES_ROOT, rf"{SCHEME}\shell\open\command", 
                               expected_cmd_protocol, "Protocolo Fluthinstore (HKCR)")
            
    # 2. Check .iflapp extension in HKCU or HKCR
    ext_ok = check_key(winreg.HKEY_CURRENT_USER, r"Software\Classes\.iflapp", 
                      "Fluthin.Package", "Extensión .iflapp (HKCU)")
    if not ext_ok:
        # Try HKCR as fallback
        ext_ok = check_key(winreg.HKEY_CLASSES_ROOT, r".iflapp", 
                          "Fluthin.Package", "Extensión .iflapp (HKCR)")
            
    # 3. Check Icon for Fluthin.Package (optional, don't fail if missing)
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Fluthin.Package\DefaultIcon")
        val, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
        
        # Normalize paths for comparison
        current_icon = normalize_path(val.replace(",0", ""))
        target_icon = normalize_path(expected_icon)
        
        if current_icon != target_icon:
            issues.append("Icono: ruta no coincide (se actualizará)")
    except FileNotFoundError:
        issues.append("Icono: no configurado (se agregará)")
    except Exception:
        # Icon is optional, don't fail
        pass
    
    # 4. Check Fluthin.Package command (with -l flag)
    pkg_cmd_ok = check_key(winreg.HKEY_CURRENT_USER, r"Software\Classes\Fluthin.Package\shell\open\command",
                          expected_cmd_file, "Comando Fluthin.Package")
            
    # Registry is valid if protocol and extension are OK
    # Icon and package command issues are warnings but not critical
    is_valid = protocol_ok and ext_ok and pkg_cmd_ok
    
    return is_valid, issues

def get_icon_path() -> str:
    """Get the correct path to Fluthinpack.ico whether running as script or compiled."""
    if hasattr(sys, '_MEIPASS'):
        # Running as compiled executable (PyInstaller)
        base_path = Path(sys._MEIPASS)
    else:
        # Running as script
        base_path = Path(__file__).parent
    
    icon_path = base_path / "app" / "Fluthinpack.ico"
    
    # Fallback to app-icon.ico if Fluthinpack.ico doesn't exist
    if not icon_path.exists():
        icon_path = base_path / "app" / "app-icon.ico"
    
    return str(icon_path)

def _handler_command(python_path: str, script_path: str) -> str:
    """Línea de comandos que abre un paquete con el handler (marcador ``%1``)."""
    if getattr(sys, 'frozen', False):
        return f'"{python_path}" -l "%1"'
    return f'"{python_path}" "{script_path}" -l "%1"'


def register_package_associations(python_path: str, script_path: str) -> tuple[bool, str]:
    """Asocia ``.iflapp``/``.asksome`` con icono y descripción.

    Hace que el explorador del sistema muestre un ``.iflapp`` como cualquier
    otro ejecutable: con el icono del handler y su descripción en las
    propiedades. En freedesktop se escribe el XML de MIME, el ``.desktop`` y el
    icono; en Windows se escribe en el registro vía ``winreg``.
    """
    if not HAS_PACKAGE_LIBS:
        return False, f"Faltan las librerías de paquetes: {_PACKAGE_LIBS_ERROR}"

    system = platform.system().lower()
    if 'windows' in system:
        if winreg is None:
            return False, "winreg no disponible"
        cmd_file = _handler_command(python_path, script_path)
        icon_path = get_icon_path()
        try:
            for extension, (mime, label, description) in _package_shell.EXTENSIONS.items():
                prog_id = "Fluthin.Package" if extension == ".iflapp" else "Fluthin.Asksome"
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{extension}") as key:
                    winreg.SetValueEx(key, None, 0, winreg.REG_SZ, prog_id)
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{prog_id}") as key:
                    winreg.SetValueEx(key, None, 0, winreg.REG_SZ, label)
                    winreg.SetValueEx(key, "FriendlyTypeName", 0, winreg.REG_SZ, description)
                if os.path.exists(icon_path):
                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{prog_id}\DefaultIcon") as key:
                        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, f"{icon_path},0")
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{prog_id}\shell\open\command") as key:
                    winreg.SetValueEx(key, None, 0, winreg.REG_SZ, cmd_file)
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{prog_id}\Content Type") as key:
                    winreg.SetValueEx(key, None, 0, winreg.REG_SZ, mime)
            try:
                ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
            except Exception:
                pass
            return True, "Asociaciones .iflapp/.asksome registradas (HKCU)"
        except Exception as exc:
            return False, f"No se pudieron registrar las asociaciones: {exc}"

    result = _package_shell.install_shell(
        handler_command=_handler_command(python_path, script_path),
        icon_path=get_icon_path(),
    )
    if result.written:
        try:
            subprocess.run(["update-desktop-database", str(Path.home() / ".local" / "share" / "applications")],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        return True, f"{len(result.written)} archivos de asociación escritos"
    return False, "; ".join(result.skipped) or "No se escribió nada"


def unregister_package_associations() -> tuple[bool, str]:
    """Retira las asociaciones de paquete escritas por el registro."""
    if not HAS_PACKAGE_LIBS:
        return False, f"Faltan las librerías de paquetes: {_PACKAGE_LIBS_ERROR}"
    system = platform.system().lower()
    if 'windows' in system:
        if winreg is None:
            return False, "winreg no disponible"
        removed = 0
        for path in (r"Software\Classes\.iflapp", r"Software\Classes\.asksome",
                     r"Software\Classes\Fluthin.Package", r"Software\Classes\Fluthin.Asksome"):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
                removed += 1
            except OSError:
                pass
        return True, f"{removed} claves retiradas"
    result = _package_shell.uninstall_shell()
    return True, f"{len(result.removed)} archivos retirados"


def register_scheme_windows(python_path: str, script_path: str) -> tuple[bool, str]:
    if winreg is None:
        return False, "winreg module not available"
    
    # Determine correct command based on execution mode (Script vs Frozen/Compiled)
    if getattr(sys, 'frozen', False):
        # Compiled (.exe): python_path is the executable, script_path is redundant/same
        # Command: "C:\Path\To\App.exe" -u "%1"
        exe_path = python_path
        cmd_protocol = f'"{exe_path}" -u "%1"'
        cmd_file = f'"{exe_path}" -l "%1"'
    else:
        # Script (.py): python_path is python.exe, script_path is script.py
        # Command: "python.exe" "script.py" -u "%1"
        cmd_protocol = f'"{python_path}" "{script_path}" -u "%1"'
        cmd_file = f'"{python_path}" "{script_path}" -l "%1"'
        
    icon_path = get_icon_path()
    
    try:
        # --- CLEANUP: Remove old keys to prevent conflicts ---
        def delete_key_recursive(root, key_path):
            try:
                open_key = winreg.OpenKey(root, key_path, 0, winreg.KEY_ALL_ACCESS)
                info = winreg.QueryInfoKey(open_key)
                for i in range(0, info[0]):
                    # Delete subkeys first
                    subkey = winreg.EnumKey(open_key, 0)
                    delete_key_recursive(root, key_path + "\\" + subkey)
                winreg.DeleteKey(root, key_path)
                winreg.CloseKey(open_key)
            except Exception:
                pass

        # Delete existing keys in HKCU
        delete_key_recursive(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{SCHEME}")
        delete_key_recursive(winreg.HKEY_CURRENT_USER, r"Software\Classes\.iflapp")
        delete_key_recursive(winreg.HKEY_CURRENT_USER, r"Software\Classes\Fluthin.Package")
        
        # --- REGISTRATION: Create new keys ---
        
        # 1. Register Protocol Fluthinstore://
        key_path = rf"Software\Classes\{SCHEME}"
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "URL:Fluthin Store Protocol")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        
        # Icon for protocol
        if os.path.exists(icon_path):
            icon_key = winreg.CreateKey(key, "DefaultIcon")
            winreg.SetValueEx(icon_key, None, 0, winreg.REG_SZ, f"{icon_path},0")
            winreg.CloseKey(icon_key)
            
        shell = winreg.CreateKey(key, r"shell\open\command")
        winreg.SetValueEx(shell, None, 0, winreg.REG_SZ, cmd_protocol)
        winreg.CloseKey(shell)
        winreg.CloseKey(key)
        
        # 2. Register .iflapp extension
        # .iflapp -> Fluthin.Package
        key_ext = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.iflapp")
        winreg.SetValueEx(key_ext, None, 0, winreg.REG_SZ, "Fluthin.Package")
        winreg.CloseKey(key_ext)
        
        # Fluthin.Package -> Command with -l flag
        key_progid = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Fluthin.Package")
        winreg.SetValueEx(key_progid, None, 0, winreg.REG_SZ, "Fluthin Package")
        
        if os.path.exists(icon_path):
            icon_key = winreg.CreateKey(key_progid, "DefaultIcon")
            winreg.SetValueEx(icon_key, None, 0, winreg.REG_SZ, f"{icon_path},0")
            winreg.CloseKey(icon_key)
            
        shell_progid = winreg.CreateKey(key_progid, r"shell\open\command")
        winreg.SetValueEx(shell_progid, None, 0, winreg.REG_SZ, cmd_file)
        winreg.CloseKey(shell_progid)
        winreg.CloseKey(key_progid)

        # Notify Shell of changes
        try:
            import ctypes
            # SHCNE_ASSOCCHANGED = 0x08000000, SHCNF_IDLIST = 0x0000
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        except Exception:
            pass

        return True, "Registered in HKCU (User-level)"
        
    except Exception as e:
        return False, f"Failed to register: {str(e)}"

def register_scheme_linux(python_path: str, script_path: str) -> tuple[bool, str]:
    try:
        user_apps = Path.home() / ".local" / "share" / "applications"
        user_apps.mkdir(parents=True, exist_ok=True)
        desktop_file = user_apps / "Fluthinstore-handler.desktop"
        exec_cmd = f"{python_path} {script_path} %u"
        
        icon_path = get_icon_path()
        
        content = "[Desktop Entry]\nName=Fluthinstore Handler\nExec=" + exec_cmd + "\nType=Application\nTerminal=false\nMimeType=x-scheme-handler/" + SCHEME + ";\n"
        if os.path.exists(icon_path):
            content += f"Icon={icon_path}\n"
            
        desktop_file.write_text(content, encoding='utf-8')
        subprocess.run(["update-desktop-database", str(user_apps)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["xdg-mime", "default", desktop_file.name, f"x-scheme-handler/{SCHEME}"])
        return True, str(desktop_file)
    except Exception as e:
        return False, str(e)

def register_scheme_macos(python_path: str, script_path: str) -> tuple[bool, str]:
    try:
        apps_dir = Path.home() / "Applications"
        apps_dir.mkdir(parents=True, exist_ok=True)
        app_name = "FluthinHandler.app"
        app_dir = apps_dir / app_name
        contents = app_dir / "Contents"
        macos_dir = contents / "MacOS"
        resources = contents / "Resources"
        macos_dir.mkdir(parents=True, exist_ok=True)
        resources.mkdir(parents=True, exist_ok=True)
        
        # Copy icon
        icon_src = get_icon_path()
        if os.path.exists(icon_src):
            shutil.copy(icon_src, resources / "Fluthinpack.ico")
        
        wrapper = macos_dir / "Fluthinhandler"
        wrapper_text = "#!/bin/bash\n\"" + python_path + "\" \"" + script_path + "\" \"$@\"\n"
        wrapper.write_text(wrapper_text, encoding='utf-8')
        wrapper.chmod(0o755)
        info_plist = contents / "Info.plist"
        plist_lines = []
        plist_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        plist_lines.append('<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">')
        plist_lines.append('<plist version="1.0">')
        plist_lines.append('<dict>')
        plist_lines.append('    <key>CFBundleName</key><string>FluthinHandler</string>')
        plist_lines.append('    <key>CFBundleIdentifier</key><string>com.Fluthin.handler</string>')
        plist_lines.append('    <key>CFBundleExecutable</key><string>Fluthinhandler</string>')
        plist_lines.append('    <key>CFBundlePackageType</key><string>APPL</string>')
        plist_lines.append('    <key>CFBundleShortVersionString</key><string>1.0</string>')
        if os.path.exists(icon_src):
             plist_lines.append('    <key>CFBundleIconFile</key><string>app-icon.ico</string>')
        plist_lines.append('    <key>CFBundleURLTypes</key>')
        plist_lines.append('    <array>')
        plist_lines.append('        <dict>')
        plist_lines.append('            <key>CFBundleURLName</key><string>Fluthin Store</string>')
        plist_lines.append('            <key>CFBundleURLSchemes</key>')
        plist_lines.append('            <array>')
        plist_lines.append('                <string>' + SCHEME + '</string>')
        plist_lines.append('            </array>')
        plist_lines.append('        </dict>')
        plist_lines.append('    </array>')
        plist_lines.append('</dict>')
        plist_lines.append('</plist>')
        info_plist.write_text("\n".join(plist_lines), encoding='utf-8')
        subprocess.run(["open", str(app_dir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.2)
        return True, str(app_dir)
    except Exception as e:
        return False, str(e)


def ensure_registered(python_path: str, script_path: str) -> tuple[bool, str, bool]:
    """Returns (success, message, was_modified)"""
    system = platform.system().lower()
    if 'windows' in system:
        if check_registry_keys(python_path, script_path):
            # Aun así, asegura las asociaciones de .iflapp/.asksome (icono y
            # descripción) que el chequeo antiguo no cubría.
            register_package_associations(python_path, script_path)
            return True, "Already registered correctly", False

        # Try to register in HKCU (no admin needed usually)
        success, msg = register_scheme_windows(python_path, script_path)
        # Asocia también .iflapp/.asksome con icono y descripción.
        assoc_ok, assoc_msg = register_package_associations(python_path, script_path)
        if success:
            extra = f" | {assoc_msg}" if assoc_ok else ""
            return True, msg + extra, True  # Registry was modified

        # If failed, maybe we need admin rights (though HKCU shouldn't need it)
        # But if we were trying HKCR before, we might need it.
        # Our new logic prefers HKCU.
        # if not is_admin():
        #    return False, "ELEVATION_REQUIRED", False
        return False, msg, False
    if 'linux' in system:
        success, msg = register_scheme_linux(python_path, script_path)
        assoc_ok, assoc_msg = register_package_associations(python_path, script_path)
        if success and assoc_ok:
            msg = f"{msg} | {assoc_msg}"
        return success, msg, success
    if 'darwin' in system:
        success, msg = register_scheme_macos(python_path, script_path)
        register_package_associations(python_path, script_path)
        return success, msg, success
    return False, "Unsupported OS", False

# --- UI Components ---

class CustomTitleBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(32)
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.title_label = QtWidgets.QLabel("Fluthin Installer")
        self.title_label.setObjectName("TitleLabel")
        layout.addWidget(self.title_label)
        
        layout.addStretch()
        
        self.btn_min = self.create_btn("minimize")
        self.btn_max = self.create_btn("maximize")
        self.btn_close = self.create_btn("close")
        
        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)
        
        self.btn_min.clicked.connect(self.window().showMinimized)
        self.btn_max.clicked.connect(self.toggle_max)
        self.btn_close.clicked.connect(self.window().close)
        
        self.start = QtCore.QPoint(0, 0)
        self.pressing = False

    def create_btn(self, name):
        btn = QtWidgets.QPushButton()
        btn.setObjectName("TitleBtn")
        btn.setProperty("class", name)
        if name == "close":
            btn.setObjectName("TitleBtn")
            btn.setProperty("id", "close")
        
        # Create icon. El QPixmap se rellena con transparencia *antes* de pintar:
        # sin ese ``fill`` los píxeles quedan sin inicializar y el antialiasing
        # del trazo dejaba el ruido gráfico que se veía sobre los botones.
        pixmap = QtGui.QPixmap(46, 32)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        
        pen = QtGui.QPen(QtGui.QColor("#202124"))
        pen.setWidthF(1.2)
        
        if name == "close":
            pen.setColor(QtGui.QColor("#e81123")) # Red X
            pen.setWidthF(1.5)
            painter.setPen(pen)
            # Draw X
            # Center x=23, y=16. Size ~10px
            painter.drawLine(18, 11, 28, 21)
            painter.drawLine(28, 11, 18, 21)
            
        elif name == "minimize":
            painter.setPen(pen)
            # Draw Line
            painter.drawLine(18, 16, 28, 16)
            
        elif name == "maximize":
            painter.setPen(pen)
            # Draw Rounded Rect
            painter.drawRoundedRect(18, 11, 10, 10, 2, 2)
            
        elif name == "restore":
            painter.setPen(pen)
            # Draw Overlapping Rects
            # Back rect
            path = QtGui.QPainterPath()
            path.addRoundedRect(20, 9, 10, 10, 2, 2)
            # Front rect (filled to hide back lines?) No, just outline
            # Actually restore is complex with rounded rects.
            # Simplified:
            painter.drawRoundedRect(20, 9, 9, 9, 1, 1) # Back
            # Fill front to cover lines
            painter.setBrush(QtGui.QColor("#ffffff"))
            painter.drawRoundedRect(17, 12, 9, 9, 1, 1) # Front
            
        painter.end()
        
        btn.setIcon(QtGui.QIcon(pixmap))
        btn.setIconSize(QtCore.QSize(46, 32))
        return btn

    def toggle_max(self):
        """Maximiza o restaura la ventana frameless (respeta el área útil)."""
        window = self.window()
        if window.isMaximized():
            window.showNormal()
            self.btn_max.setIcon(self.create_btn("maximize").icon())
        else:
            window.showMaximized()
            self.btn_max.setIcon(self.create_btn("restore").icon())

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            # El movimiento nativo del WM aporta Aero Snap; si no está
            # disponible se cae al arrastre manual de toda la vida.
            if handle is not None and handle.startSystemMove():
                self.pressing = False
                return
            self.start = event.globalPosition().toPoint()
            self.pressing = True

    def mouseMoveEvent(self, event):
        if self.pressing:
            end = event.globalPosition().toPoint()
            movement = end - self.start
            self.window().setGeometry(self.window().geometry().translated(movement))
            self.start = end

    def mouseReleaseEvent(self, event):
        self.pressing = False

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.toggle_max()


def _detect_resize_edges(pos, rect, margin=RESIZE_MARGIN):
    """Combinación de bordes a redimensionar para *pos* dentro de *rect*."""
    edges = None
    if pos.x() <= rect.left() + margin:
        edges = QtCore.Qt.Edge.LeftEdge
    elif pos.x() >= rect.right() - margin:
        edges = QtCore.Qt.Edge.RightEdge
    if pos.y() <= rect.top() + margin:
        edges = (edges | QtCore.Qt.Edge.TopEdge) if edges is not None else QtCore.Qt.Edge.TopEdge
    elif pos.y() >= rect.bottom() - margin:
        edges = (edges | QtCore.Qt.Edge.BottomEdge) if edges is not None else QtCore.Qt.Edge.BottomEdge
    return edges


def _cursor_for_edges(edges):
    """Cursor adecuado para los bordes detectados (o ``None``)."""
    if edges is None:
        return None
    left = bool(edges & QtCore.Qt.Edge.LeftEdge)
    right = bool(edges & QtCore.Qt.Edge.RightEdge)
    top = bool(edges & QtCore.Qt.Edge.TopEdge)
    bottom = bool(edges & QtCore.Qt.Edge.BottomEdge)
    if (left and top) or (right and bottom):
        return QtCore.Qt.CursorShape.SizeFDiagCursor
    if (right and top) or (left and bottom):
        return QtCore.Qt.CursorShape.SizeBDiagCursor
    if left or right:
        return QtCore.Qt.CursorShape.SizeHorCursor
    return QtCore.Qt.CursorShape.SizeVerCursor


class _ResizeEdgeFilter(QtCore.QObject):
    """Redimensiona y ajusta el cursor en los bordes de la ventana frameless.

    Se instala sobre la ventana **y** sus descendientes con seguimiento del
    ratón: los hijos llenan la ventana y consumen los eventos, así que sin el
    filtro en ellos los bordes nunca recibían ``MouseMove`` ni ``MouseButtonPress``
    y la ventana sin marco no se podía redimensionar.
    """

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._edges = None
        self._manual = None

    def eventFilter(self, obj, event):
        if getattr(self, "_window", None) is None:
            return False
        try:
            return self._filter(obj, event)
        except RuntimeError:
            # El objeto C++ puede haberse destruido durante el apagado de Qt.
            return False

    def _filter(self, obj, event):
        window = self._window
        if obj is getattr(window, "title_bar", None):
            # La titlebar no redimensiona: arrastrarla mueve la ventana.
            self._reset_cursor()
            return False
        if window.isMaximized():
            return False
        etype = event.type()
        if etype == QtCore.QEvent.Type.MouseMove and isinstance(obj, QtWidgets.QWidget):
            pos = obj.mapTo(window, event.position().toPoint())
            if self._manual is not None:
                self._apply_manual_resize(event.globalPosition().toPoint())
                return True
            edges = _detect_resize_edges(pos, window.rect(), RESIZE_MARGIN)
            if edges != self._edges:
                self._edges = edges
                if edges is None:
                    self._reset_cursor()
                else:
                    self._window.setCursor(QtGui.QCursor(_cursor_for_edges(edges)))
        elif etype == QtCore.QEvent.Type.MouseButtonPress and isinstance(obj, QtWidgets.QWidget):
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                pos = obj.mapTo(window, event.position().toPoint())
                edges = _detect_resize_edges(pos, window.rect(), RESIZE_MARGIN)
                if edges is not None:
                    self._begin_resize(edges, event.globalPosition().toPoint())
                    return True
        elif etype == QtCore.QEvent.Type.MouseButtonRelease:
            self._manual = None
            self._reset_cursor()
        return False

    def _begin_resize(self, edges, global_pos):
        handle = self._window.windowHandle()
        # ``startSystemResize`` delega en el WM (mejor gesto y Aero Snap); si el
        # backend no lo soporta (p. ej. offscreen) se cae al redimensionado
        # manual para que la ventana siga siendo utilizable.
        if handle is not None and handle.startSystemResize(edges):
            self._manual = None
            return
        self._manual = {
            "edges": edges,
            "start_pos": global_pos,
            "start_geo": self._window.geometry(),
        }

    def _apply_manual_resize(self, global_pos):
        state = self._manual
        geo = QtCore.QRect(state["start_geo"])
        delta = global_pos - state["start_pos"]
        edges = state["edges"]
        if edges & QtCore.Qt.Edge.LeftEdge:
            geo.setLeft(geo.left() + delta.x())
        if edges & QtCore.Qt.Edge.RightEdge:
            geo.setRight(geo.right() + delta.x())
        if edges & QtCore.Qt.Edge.TopEdge:
            geo.setTop(geo.top() + delta.y())
        if edges & QtCore.Qt.Edge.BottomEdge:
            geo.setBottom(geo.bottom() + delta.y())
        minimum = self._window.minimumSize()
        if geo.width() < minimum.width() or geo.height() < minimum.height():
            return
        self._window.setGeometry(geo)

    def _reset_cursor(self):
        self._edges = None
        try:
            self._window.unsetCursor()
        except (RuntimeError, AttributeError):
            pass


def _install_resize_filter(window):
    """Instala :class:`_ResizeEdgeFilter` en la ventana y todos sus hijos."""
    filt = _ResizeEdgeFilter(window)
    window.setMouseTracking(True)
    window.installEventFilter(filt)
    for child in window.findChildren(QtWidgets.QWidget):
        child.setMouseTracking(True)
        child.installEventFilter(filt)
    window._resize_filter = filt
    return filt


class BlurredBanner(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(220)
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.bg_label = QtWidgets.QLabel(self)
        self.bg_label.setScaledContents(True)
        
        self.fg_label = QtWidgets.QLabel(self)
        self.fg_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop)
        # Oculto hasta que haya un splash real: un banner vacío de 220 px dejaba
        # el hueco blanco desproporcionado que mostraba la interfaz defectuosa.
        self.setVisible(False)

    def setPixmap(self, pixmap):
        if pixmap is None or pixmap.isNull():
            self._original_pixmap = None
            self.setVisible(False)
            return
        self._original_pixmap = pixmap
        self.setVisible(True)
        self.update_images()

    def set_accent(self, accent: str) -> None:
        """Color con el que se rellena el fondo difuminado del banner."""
        self._accent = accent
        if getattr(self, "_original_pixmap", None) is not None:
            self.update_images()

    def resizeEvent(self, event):
        self.update_images()
        super().resizeEvent(event)
        
    def update_images(self):
        if not hasattr(self, '_original_pixmap'): return
        
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0: return

        # Strategy: "Ajustarse al ancho" (Fit Width)
        # We always scale the image to match the widget width.
        # Then we check if the height is enough.
        
        # 1. Scale to Width
        img_w = self._original_pixmap.width()
        img_h = self._original_pixmap.height()
        if img_w == 0: return
        
        scale_factor = w / img_w
        new_h = int(img_h * scale_factor)
        
        scaled_pix = self._original_pixmap.scaled(
            w, new_h,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        
        if new_h >= h:
            # Case A: Image is taller than widget (or equal).
            # We crop the center vertical part.
            y = (new_h - h) // 2
            cropped = scaled_pix.copy(0, y, w, h)
            
            # Set as main image (Sharp)
            self.fg_label.setPixmap(cropped)
            self.fg_label.setGeometry(0, 0, w, h)
            
            # Background hidden or same (doesn't matter)
            self.bg_label.clear()
            
        else:
            # Case B: Image is shorter than widget (Banner is too wide/short).
            # We center it vertically and fill background with blur.
            
            # 1. Background: Zoomed blur to fill
            cover_pix = self._original_pixmap.scaled(
                w, h,
                QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            # Crop center of cover
            cx = (cover_pix.width() - w) // 2
            cy = (cover_pix.height() - h) // 2
            bg_cropped = cover_pix.copy(cx, cy, w, h)

            # Compose over the accent before blurring so a transparent
            # splash does not reveal the white window behind.
            canvas = QtGui.QPixmap(bg_cropped.size())
            canvas.fill(QtGui.QColor(getattr(self, "_accent", DEFAULT_ACCENT)))
            painter = QtGui.QPainter(canvas)
            painter.drawPixmap(0, 0, bg_cropped)
            painter.end()

            # Blur
            small = canvas.scaled(
                20, 20,
                QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            blurred = small.scaled(
                w, h,
                QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            
            self.bg_label.setPixmap(blurred)
            self.bg_label.setGeometry(0, 0, w, h)
            
            # 2. Foreground: Centered vertically
            y = (h - new_h) // 2
            self.fg_label.setPixmap(scaled_pix)
            self.fg_label.setGeometry(0, y, w, new_h)

def get_remote_details(owner: str, repo: str) -> dict:
    """Fetches details.xml and returns a dict with parsed info."""
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/details.xml"
    try:
        r = requests.get(url, timeout=5)
        if r.ok:
            return parse_details_xml(r.text)
    except Exception:
        pass
    return {}

def parse_details_xml(content: str) -> dict:
    """Parses details.xml content and returns a dict."""
    data = {}
    try:
        import xml.etree.ElementTree as ET
        # Parse the XML content
        root = ET.fromstring(content)
        
        # Extract direct children of root
        for child in root:
            tag_name = child.tag.lower()
            if tag_name in ['name', 'publisher', 'app', 'version', 'platform', 'author']:
                data[tag_name] = child.text.strip() if child.text else ""
    except Exception:
        # Fallback to regex if XML parsing fails
        try:
            patterns = {
                'name': r'<name>(.*?)</name>',
                'publisher': r'<publisher>(.*?)</publisher>',
                'app': r'<app>(.*?)</app>',
                'version': r'<version>(.*?)</version>',
                'platform': r'<platform>(.*?)</platform>',
                'author': r'<author>(.*?)</author>'
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                if match:
                    data[key] = match.group(1).strip()
        except Exception:
            pass
    return data

def find_installed_package(publisher: str, app: str, version: str, platform: str) -> Path | None:
    """Checks if a specific package version is installed by exact folder name match."""
    home = Path.home()
    if os.name == 'nt':
        documents = Path(os.path.join(os.environ.get('USERPROFILE',''), 'Documents'))
    else:
        documents = home / 'Documents'
    
    base_dir = documents / 'Fluthin Apps'
    if not base_dir.exists():
        return None
    
    # Check for exact folder name: {publisher}-{app}-{version}-{platform}
    folder_name = f"{publisher}.{app}.{version}-{platform}"
    target_path = base_dir / folder_name
    
    if target_path.exists() and target_path.is_dir():
        return target_path
    return None

def find_installed_path(owner: str, repo: str) -> Path | None:
    """Checks if the app is installed in Documents/Fluthin Apps (legacy, loose match)."""
    home = Path.home()
    if os.name == 'nt':
        documents = Path(os.path.join(os.environ.get('USERPROFILE',''), 'Documents'))
    else:
        documents = home / 'Documents'
    
    base_dir = documents / 'Fluthin Apps'
    if not base_dir.exists():
        return None
        
    # Look for folder containing publisher.app pattern
    for p in base_dir.iterdir():
        if p.is_dir() and f".{repo}." in p.name:
            return p
    return None

class InstallWindow(QtWidgets.QWidget):
    def __init__(self, repo: str, owner: str, local_file_path: str = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.owner = owner
        self.local_file_path = local_file_path
        self.shortname = repo
        self.app_name = repo # Default fallback
        self.accent = system_accent_color()  # Acento del SO para icono y estados
        self.temp_extract_dir = None # To clean up later if needed
        self.package_icon = b"" # Icono leído de la cabecera del paquete
        
        # Metadata placeholders
        self.meta_publisher = owner
        self.meta_app = repo
        self.meta_version = "Unknown"
        self.meta_platform = "Unknown"
        self.meta_author = owner  # For sharing local packages

        # Pre-load local package info if available
        if self.local_file_path:
            self.load_local_package_metadata()
        
        # Check for existing installation using exact metadata
        self.installed_path = None
        if self.meta_publisher != "Unknown" and self.meta_app != "Unknown" and self.meta_version != "Unknown" and self.meta_platform != "Unknown":
            self.installed_path = find_installed_package(self.meta_publisher, self.meta_app, self.meta_version, self.meta_platform)
        
        # Fallback to loose match if exact match not found
        if not self.installed_path and not local_file_path:
            self.installed_path = find_installed_path(owner, repo)

        # Ventana frameless: la barra de título nativa se retira para que sólo
        # exista la propia (CustomTitleBar). Sin esto aparecían las dos, que es
        # el defecto visual descrito en bugs.md.
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window
            | QtCore.Qt.WindowType.FramelessWindowHint
        )
        self.setObjectName("InstallWindow")
        self.setMinimumSize(720, 480)
        self.resize(1000, 650)
        
        # Main Layout
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Title Bar
        self.title_bar = CustomTitleBar(self)
        self.title_bar.title_label.setText(f"Instalar {self.app_name}")
        self.main_layout.addWidget(self.title_bar)
        
        # Banner Image
        self.banner = BlurredBanner()
        self.banner.set_accent(self.accent)
        self.main_layout.addWidget(self.banner)
        
        # Cabecera estilo UWP: texto a la izquierda, icono en la esquina superior
        # derecha dentro de un cuadrado del color de acento del SO.
        header = QtWidgets.QWidget()
        header.setObjectName("HeaderArea")
        h_layout = QtWidgets.QHBoxLayout(header)
        h_layout.setContentsMargins(30, 24, 30, 18)
        h_layout.setSpacing(20)

        # Texto: título grande + metadatos (Editor / Versión / Origen).
        meta_v = QtWidgets.QVBoxLayout()
        meta_v.setSpacing(6)
        self.title_lbl = QtWidgets.QLabel(self._headline())
        self.title_lbl.setObjectName("AppTitle")
        self.title_lbl.setWordWrap(True)
        meta_v.addWidget(self.title_lbl)

        self.meta_lbl = QtWidgets.QLabel(self._meta_line())
        self.meta_lbl.setObjectName("AppMeta")
        meta_v.addWidget(self.meta_lbl)

        self.ver_lbl = QtWidgets.QLabel(self._version_line())
        self.ver_lbl.setObjectName("AppVersion")
        meta_v.addWidget(self.ver_lbl)

        h_layout.addLayout(meta_v, 1)

        # Icono a la derecha, alineado arriba.
        icon_col = QtWidgets.QVBoxLayout()
        icon_col.setContentsMargins(0, 0, 0, 0)
        self.icon_label = QtWidgets.QLabel()
        self.icon_label.setObjectName("AppIcon")
        self.icon_label.setFixedSize(96, 96)
        self.icon_label.setScaledContents(False)
        self.icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._set_icon_pixmap(None)
        icon_col.addWidget(self.icon_label, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        h_layout.addLayout(icon_col)

        self.main_layout.addWidget(header)
        
        # Content Area (Split)
        content = QtWidgets.QWidget()
        content.setObjectName("ContentArea")
        c_layout = QtWidgets.QHBoxLayout(content)
        c_layout.setContentsMargins(30, 20, 30, 20)
        c_layout.setSpacing(30)
        
        # Left: Description (Markdown/Text)
        left_panel = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        desc_lbl = QtWidgets.QLabel("Acerca de esta app")
        desc_lbl.setStyleSheet("font-weight: bold; font-size: 16px; color: #202124; margin-bottom: 10px;")
        left_layout.addWidget(desc_lbl)
        
        if HAS_MARKDOWN:
            self.readme_view = QWebEngineView()
            self.readme_view.setStyleSheet("background: white;")
            self.readme_view.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
        else:
            self.readme_view = QtWidgets.QTextEdit()
            self.readme_view.setReadOnly(True)
            self.readme_view.setStyleSheet("border: none; background: #ffffff;")
            
        left_layout.addWidget(self.readme_view)
        c_layout.addWidget(left_panel, 65)
        
        # Right: Progress & Logs
        right_panel = QtWidgets.QWidget()
        right_panel.setObjectName("StatusPanel")
        r_layout = QtWidgets.QVBoxLayout(right_panel)
        r_layout.setContentsMargins(14, 12, 14, 12)
        r_layout.setSpacing(10)
        
        lbl_log = QtWidgets.QLabel("Estado de instalación")
        lbl_log.setStyleSheet("font-weight: 600; color: #1B1B1B; background: transparent;")
        r_layout.addWidget(lbl_log)
        
        self.progress = QtWidgets.QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setStyleSheet(
            "QProgressBar { border: none; background: #E8E8E8; border-radius: 2px; }"
            f" QProgressBar::chunk {{ background: {self.accent}; border-radius: 2px; }}"
        )
        r_layout.addWidget(self.progress)
        
        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName("LogArea")
        r_layout.addWidget(self.log)
        
        c_layout.addWidget(right_panel, 35)
        
        self.main_layout.addWidget(content)
        
        # Pie estilo UWP: icono informativo a la izquierda y acciones a la
        # derecha, alineadas al borde inferior.
        footer = QtWidgets.QWidget()
        footer.setObjectName("FooterArea")
        f_layout = QtWidgets.QHBoxLayout(footer)
        f_layout.setContentsMargins(30, 12, 30, 18)
        f_layout.setSpacing(10)

        info_badge = QtWidgets.QLabel("i")
        info_badge.setObjectName("InfoBadge")
        info_badge.setFixedSize(22, 22)
        info_badge.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        f_layout.addWidget(info_badge, 0, QtCore.Qt.AlignmentFlag.AlignBottom)
        f_layout.addStretch()

        action_h = QtWidgets.QHBoxLayout()
        action_h.setSpacing(10)

        self.install_btn = QtWidgets.QPushButton("Instalar")
        self.install_btn.setObjectName("PrimaryBtn")
        self.install_btn.setMinimumWidth(120)
        action_h.addWidget(self.install_btn)

        self.share_btn = QtWidgets.QPushButton("Compartir")
        self.share_btn.setObjectName("SecondaryBtn")
        self.share_btn.setMinimumWidth(120)
        action_h.addWidget(self.share_btn)

        if self.installed_path:
            self.uninstall_btn = QtWidgets.QPushButton("Desinstalar")
            self.uninstall_btn.setObjectName("DangerBtn")
            self.uninstall_btn.setMinimumWidth(120)
            action_h.addWidget(self.uninstall_btn)

        f_layout.addLayout(action_h)

        self.main_layout.addWidget(footer)
        
        # Connects
        if self.installed_path:
            self.install_btn.setText("Ejecutar")
            self.install_btn.clicked.connect(self.on_execute)
            self.uninstall_btn.clicked.connect(self.on_uninstall)
            self.title_bar.title_label.setText(f"Ejecutar {self.app_name}")
            self.log_msg(f"Aplicación detectada en: {self.installed_path}")
        else:
            self.install_btn.clicked.connect(self.on_install)
            
        self.share_btn.clicked.connect(self.on_share)
        
        QtCore.QTimer.singleShot(100, self.load_remote_assets)

        # Offline Mode Adjustments (UI Updates)
        if self.local_file_path:
            self._refresh_header()

            # Check Compatibility
            is_compat, msg = check_platform_compatibility(self.meta_platform)
            if not is_compat:
                self._mark_incompatible(msg)
                QtWidgets.QMessageBox.critical(self, "Incompatible", msg)
            
            # Load local assets if available
            self.load_local_assets_to_ui()

        # La ventana ya tiene todos sus hijos: instala el filtro que
        # redimensiona por los bordes y ajusta el cursor (ventana frameless).
        _install_resize_filter(self)

    def load_local_package_metadata(self):
        """Lee la identidad del paquete local sin descomprimir el payload.

        El contenedor ``.iflapp`` v2 y el ``.asksome`` no son ZIP, así que la
        cabecera se lee con :func:`read_package_identity`; sólo el ZIP
        histórico necesita extracción para llegar a ``details.xml``.
        """
        try:
            data = read_package_identity(self.local_file_path)
            if data:
                self.app_name = data.get('name') or self.app_name
                self.meta_publisher = data.get('publisher') or self.meta_publisher
                self.meta_app = data.get('app') or self.meta_app
                self.meta_version = data.get('version') or self.meta_version
                self.meta_platform = data.get('platform') or self.meta_platform
                self.meta_author = data.get('author') or self.meta_author

                # Update owner/repo for remote fallback
                if data.get('publisher'): self.owner = data.get('publisher')
                if data.get('app'): self.repo = data.get('app')

            # Icono de cabecera (v2/asksome) o de assets extraídos (ZIP).
            self.package_icon = read_package_icon(self.local_file_path)

            # Check Platform Compatibility
            is_compat, msg = check_platform_compatibility(self.meta_platform)
            if not is_compat:
                self.install_btn.setEnabled(False)
                self._mark_incompatible(msg)
                QtWidgets.QMessageBox.warning(self, "Incompatible", msg)

        except Exception as e:
            print(f"Error reading local package metadata: {e}")

    def _headline(self) -> str:
        """Título grande estilo UWP: "¿Instalar X?" o "X ya está instalado"."""
        if self.installed_path:
            return f"{self.app_name} ya está instalado"
        return f"¿Instalar {self.app_name}?"

    def _meta_line(self) -> str:
        """Línea de editor/origen bajo el título."""
        publisher = self.meta_publisher or self.owner
        if self.local_file_path:
            return f"Editor: {publisher} · Origen: archivo local"
        return f"Editor: {publisher} · Origen: {self.owner}/{self.repo}"

    def _version_line(self) -> str:
        """Línea de versión y plataforma."""
        version = self.meta_version or "Desconocida"
        platform_value = self.meta_platform or "Desconocida"
        return f"Versión: {version} · Plataforma: {platform_value}"

    def _refresh_header(self):
        """Repinta título y metadatos tras descubrir la identidad del paquete."""
        self.title_lbl.setText(self._headline())
        self.meta_lbl.setText(self._meta_line())
        self.ver_lbl.setText(self._version_line())

    def _mark_incompatible(self, msg: str = ""):
        """Bloquea la instalación y muestra el aviso de incompatibilidad.

        La barra de estado (panel inferior) es el lugar UWP para el mensaje; no
        se altera el estilo del botón primario para no romper la hoja global.
        """
        self.install_btn.setEnabled(False)
        self.install_btn.setText("Incompatible")
        self.ver_lbl.setText(f"{self._version_line()} · INCOMPATIBLE")
        self.ver_lbl.setStyleSheet("color: #C42B1C; font-weight: 600;")
        if msg:
            self.log_msg(f"Incompatible: {msg}")

    def _set_icon_pixmap(self, data: bytes | None):
        """Pinta el icono del paquete sobre un cuadrado del acento del SO.

        Si no hay icono válido se deja el cuadrado de acento con las iniciales
        de la app, en vez del recuadro gris vacío que mostraba el instalador.
        """
        pix = render_app_icon(data, size=96, accent=self.accent) if data else None
        if pix is not None:
            self.icon_label.setPixmap(pix)
            self._apply_window_icon(data)
            return
        initials = "".join(part[:1] for part in re.split(r"[\s._-]+", self.app_name) if part)[:2].upper()
        self.icon_label.setText(initials or "?")
        self.icon_label.setStyleSheet(
            f"#AppIcon {{ background-color: {self.accent}; border-radius: 6px;"
            f" color: #FFFFFF; font-size: 34px; font-weight: 600; }}"
        )

    def _apply_window_icon(self, data: bytes | None):
        """Adopta el icono del paquete como icono de la ventana y de la app."""
        if not data:
            return
        pixmap = QtGui.QPixmap()
        if not pixmap.loadFromData(data):
            return
        icon = QtGui.QIcon(pixmap)
        self.setWindowIcon(icon)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.setWindowIcon(icon)

    def _apply_mica(self):
        """Aplica el material Mica del SO al fondo de la ventana (si hay soporte).

        Se usa cuando el paquete no trae assets de splash: el plan pide entonces
        "efecto Mica completo en toda la ventana". La propiedad ``backdrop``
        activa las reglas QSS translúcidas; ``WipeWindow`` aporta el material.
        """
        self.setProperty("backdrop", "mica")
        self.style().unpolish(self)
        self.style().polish(self)
        if not HAS_WIPE_WINDOW or _WipeWindow is None:
            return
        try:
            self.window_effects = (
                _WipeWindow.create().set_mode("polished").set_radius(8).set_blur(0).apply(self)
            )
        except Exception:
            pass

    def _apply_banner_asset(self, assets_dir: Path | None, has_assets: bool):
        """Elige el splash de cabecera (banner) según la orientación de pantalla.

        Horizontal → ``splash.png``; vertical → ``splash_setup.png``; sin assets
        → Mica completo. Es independiente del splash de arranque (que ya no usa
        assets): el banner es el encabezado dentro de la propia ventana.
        """
        orientation = screen_orientation()
        asset = (
            find_banner_asset(assets_dir, self.app_name, orientation, has_assets)
            if assets_dir else None
        )
        if asset is None:
            if not has_assets or assets_dir is None:
                self._apply_mica()
            return
        pixmap = QtGui.QPixmap(str(asset))
        if not pixmap.isNull():
            self.banner.setPixmap(pixmap)

    def load_local_assets_to_ui(self):
        """Carga el icono y el banner del paquete en la interfaz.

        El contenedor v2 guarda el icono en la cabecera (no hay que extraerlo),
        así que se prefiere ``package_icon``; si no hay, se busca el icono
        extraído (ZIP histórico).
        """
        # Icono de cabecera del contenedor v2/.asksome
        if getattr(self, "package_icon", b""):
            self._set_icon_pixmap(self.package_icon)

        if not self.temp_extract_dir:
            return

        # Icono extraído (ZIP histórico) si no se pintó el de cabecera.
        if not getattr(self, "package_icon", b""):
            icon_path = self.temp_extract_dir / "app" / "app-icon.ico"
            if not icon_path.exists():
                icon_path = self.temp_extract_dir / "app" / "app-icon.png"
            if icon_path.exists():
                self._set_icon_pixmap(icon_path.read_bytes())

        # Banner: splash de cabecera según orientación (o Mica si no hay assets).
        assets_dir = self.temp_extract_dir / "assets"
        has_assets = assets_dir.is_dir() and any(assets_dir.iterdir())
        self._apply_banner_asset(assets_dir, has_assets)

    def closeEvent(self, event):
        # Cleanup temp dir
        if self.temp_extract_dir and self.temp_extract_dir.exists():
            try:
                shutil.rmtree(self.temp_extract_dir)
            except:
                pass
        super().closeEvent(event)

    def log_msg(self, s: str):
        self.log.append(s)
        cursor = self.log.textCursor()
##        cursor.movePosition(QtGui.QTextCursor.End)
        self.log.setTextCursor(cursor)

    def set_progress(self, val: int):
        self.progress.setValue(val)

    def load_remote_assets(self):
        if self.local_file_path:
            return # Skip remote assets for local files

        # 1. Try Local details.xml if installed
        if self.installed_path:
            local_details = self.installed_path / "details.xml"
            if local_details.exists():
                try:
                    content = local_details.read_text(encoding='utf-8')
                    name_match = re.search(r'<name>(.*?)</name>', content, re.IGNORECASE)
                    if name_match:
                        self.app_name = name_match.group(1)
                        self.title_lbl.setText(self.app_name)
                        self.title_bar.title_label.setText(f"Ejecutar {self.app_name}")
                        # We can return early or still try to fetch other assets?
                        # Let's continue to fetch icons/banner if they are not local (we don't save those yet)
                except Exception:
                    pass

        # 2. Fetch remote details.xml if we still don't have a custom name or just to refresh
        # (Only if we didn't find it locally or we want to be sure)
        # Actually, if we found it locally, we trust it.
        if self.app_name == self.repo:
            details = get_remote_details(self.owner, self.repo)
            if details.get('name'):
                self.app_name = details['name']
                self.title_lbl.setText(self.app_name)
                if not self.installed_path:
                    self.title_bar.title_label.setText(f"Instalar {self.app_name}")
                else:
                    self.title_bar.title_label.setText(f"Ejecutar {self.app_name}")
            
            # Also store other metadata if available
            if details.get('app'): self.meta_app = details['app']
            if details.get('publisher'): self.meta_publisher = details['publisher']
            if details.get('version'): self.meta_version = details['version']
            if details.get('platform'): self.meta_platform = details['platform']
            
            # Update UI labels with new metadata
            self._refresh_header()

            # Check Platform Compatibility
            is_compat, msg = check_platform_compatibility(self.meta_platform)
            if not is_compat:
                self._mark_incompatible(msg)
                # We don't show a popup here to avoid spamming if just viewing, but the UI is clear.

        # Icon
        try:
            icon_url = f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/main/app/app-icon.ico"
            r = requests.get(icon_url, timeout=4)
            if r.ok:
                self._set_icon_pixmap(r.content)
            else:
                icon_url_png = f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/main/app/app-icon.png"
                r = requests.get(icon_url_png, timeout=4)
                if r.ok:
                    self._set_icon_pixmap(r.content)
        except Exception:
            pass

        # Banner: se prueban los assets de splash por orientación (igual que en
        # el flujo local). Si ninguno existe, se aplica Mica a toda la ventana.
        try:
            orientation = screen_orientation()
            candidates = banner_candidates(self.app_name, orientation)
            found = False
            for name in candidates:
                banner_url = (
                    f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/main/assets/{name}"
                )
                r = requests.get(banner_url, timeout=5)
                if r.ok:
                    pix = QtGui.QPixmap()
                    if pix.loadFromData(r.content):
                        self.banner.setPixmap(pix)
                        found = True
                        break
            if not found:
                self._apply_mica()
        except Exception:
            pass

        # Readme
        try:
            readme_candidates = [
                f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/main/README.md",
                f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/master/README.md",
            ]
            text = ""
            for url in readme_candidates:
                r = requests.get(url, timeout=6)
                if r.ok:
                    text = r.text
                    break
            
            if not text:
                text = "No description available."

            if HAS_MARKDOWN and isinstance(self.readme_view, QWebEngineView):
                html = markdown.markdown(text)
                style = (
                    "<style>body { font-family: 'Segoe UI', Roboto, sans-serif;"
                    " color: #202124; line-height: 1.6; }"
                    f" a {{ color: {self.accent}; text-decoration: none; }}"
                    " code { background: #f1f3f4; padding: 2px 4px; border-radius: 4px; }"
                    " h1, h2, h3 { color: #202124; }</style>"
                )
                self.readme_view.setHtml(style + html)
            else:
                self.readme_view.setPlainText(text)
                
        except Exception as e:
            if not HAS_MARKDOWN:
                self.readme_view.setPlainText(f"Error loading details: {e}")

    def on_share(self):
        # Determine the GitHub URL
        if self.local_file_path and self.meta_author and self.meta_app:
            # For local packages, construct URL from author and app
            long_url = f"https://github.com/{self.meta_author}/{self.meta_app}"
        else:
            # For remote packages, use owner and repo
            long_url = f"https://github.com/{self.owner}/{self.repo}"
        
        try:
            r = requests.get(f"https://is.gd/create.php?format=simple&url={long_url}", timeout=15)
            if r.ok:
                short_url = r.text.strip()
            else:
                short_url = long_url
        except:
            short_url = long_url
            
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(short_url)
        
        orig_text = self.share_btn.text()
        self.share_btn.setText("¡Copiado!")
        self.share_btn.setDisabled(True)
        QtCore.QTimer.singleShot(2000, lambda: self.reset_share_btn(orig_text))
        
    def reset_share_btn(self, text):
        self.share_btn.setText(text)
        self.share_btn.setDisabled(False)

    def on_uninstall(self):
        buttons = (
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No
        )
        reply = QtWidgets.QMessageBox.question(
            self, 'Confirmar desinstalación',
            f"¿Estás seguro de que quieres desinstalar {self.app_name}?",
            buttons, QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            try:
                # 1. Remove desktop shortcuts
                desktop = Path.home() / 'Desktop'
                shortcut_name = self.app_name if self.app_name else f"{self.owner}.{self.shortname}"
                shortcut_name = re.sub(r'[<>:"/\\|?*]', '', shortcut_name)
                
                # Try to remove various shortcut formats
                for ext in ['.lnk', '.url', '.desktop', '.command']:
                    shortcut_path = desktop / (shortcut_name + ext)
                    if shortcut_path.exists():
                        try:
                            shortcut_path.unlink()
                            self.log_msg(f"Acceso directo eliminado: {shortcut_path.name}")
                        except Exception as e:
                            self.log_msg(f"No se pudo eliminar acceso directo {shortcut_path.name}: {e}")
                
                # 2. Remove application folder
                if self.installed_path and self.installed_path.exists():
                    shutil.rmtree(self.installed_path, ignore_errors=False)
                    self.log_msg(f"Carpeta eliminada: {self.installed_path}")
                
                # 3. Update UI state
                self.installed_path = None
                
                # Change button back to "Instalar"
                self.install_btn.setText("Instalar")
                self.install_btn.clicked.disconnect()
                self.install_btn.clicked.connect(self.on_install)
                
                # Remove uninstall button
                if hasattr(self, 'uninstall_btn'):
                    self.uninstall_btn.setParent(None)
                    self.uninstall_btn.deleteLater()
                    delattr(self, 'uninstall_btn')
                
                # Update title
                self.title_bar.title_label.setText(f"Instalar {self.app_name}")
                
                self.log_msg("Desinstalación completada correctamente.")
                QtWidgets.QMessageBox.information(self, "Desinstalado", "La aplicación ha sido desinstalada correctamente.")
                
            except PermissionError as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo desinstalar: Permiso denegado.\n{str(e)}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo desinstalar: {str(e)}")

    def on_execute(self):
        if not self.installed_path: return
        exe_path = find_executable(self.installed_path, self.shortname)
        if not exe_path:
            # Fallback scan
            for p in self.installed_path.rglob('*.exe'):
                exe_path = p
                break
        
        if exe_path:
            try:
                subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))
                self.close()
            except Exception as e:
                self.log_msg(f"Error al ejecutar: {e}")
        else:
            self.log_msg("No se encontró el ejecutable.")
            QtWidgets.QMessageBox.warning(self, "Error", "No se encontró el ejecutable.")

    def on_install(self):
        self.install_btn.setEnabled(False)
        self.progress.setValue(0)
        self.log_msg("Iniciando instalación...")
        
        worker = InstallWorker(self.repo, self.owner, self.shortname, self.app_name, self.local_file_path, self.meta_app, self.meta_publisher, self.meta_version, self.meta_platform)
        worker.signals.log.connect(self.log_msg)
        worker.signals.progress.connect(self.set_progress)
        worker.signals.done.connect(self.install_finished)
        worker.signals.ask_open_releases.connect(self.offer_open_releases)
        QtCore.QThreadPool.globalInstance().start(worker)

    def offer_open_releases(self, url: str):
        res = QtWidgets.QMessageBox.question(self, "Abrir releases", "No se encontró un instalador compatible. ¿Abrir GitHub Releases?")
        if res == QtWidgets.QMessageBox.StandardButton.Yes:
            webbrowser.open(url)

    def install_finished(self, success: bool, target_dir: str = ""):
        self.install_btn.setEnabled(True)
        self.progress.setValue(100 if success else 0)
        if success:
            QtWidgets.QMessageBox.information(self, "Éxito", f"Instalación completada correctamente.\nUbicación: {target_dir}")
            self.installed_path = Path(target_dir)
            self.install_btn.setText("Ejecutar")
            self.install_btn.clicked.disconnect()
            self.install_btn.clicked.connect(self.on_execute)
        else:
            QtWidgets.QMessageBox.warning(self, "Error", "La instalación falló. Revisa el registro.")

class WorkerSignals(QtCore.QObject):
    log = QtCore.pyqtSignal(str)
    progress = QtCore.pyqtSignal(int)
    done = QtCore.pyqtSignal(bool, str)
    ask_open_releases = QtCore.pyqtSignal(str)

class InstallWorker(QtCore.QRunnable):
    def __init__(self, repo: str, owner: str, shortname: str, app_name: str, local_file_path: str = None, meta_app_id: str = None, meta_publisher: str = None, meta_version: str = None, meta_platform: str = None):
        super().__init__()
        self.repo = repo
        self.owner = owner
        self.shortname = shortname
        self.app_name = app_name
        self.local_file_path = local_file_path
        self.meta_app_id = meta_app_id
        self.meta_publisher = meta_publisher
        self.meta_version = meta_version
        self.meta_platform = meta_platform
        self.signals = WorkerSignals()

    def run(self):
        try:
            if self.local_file_path:
                # Offline Mode
                self.signals.log.emit("Preparando instalación de paquete local...")
                
                # Preferir los metadatos de la cabecera del paquete; el nombre
                # de archivo sólo es el respaldo.
                parsed = parse_package_filename(self.local_file_path)
                version = self.meta_version or parsed["version"] or "local"
                platformstr = normalize_platform(self.meta_platform or parsed["platform"]) or "unknown"
                publisher = self.meta_publisher or parsed["publisher"]
                app_id = self.meta_app_id or parsed["app"] or self.shortname

                # Check compatibility (Double check)
                if platformstr == 'Danenone' and platform_tag() == 'Knosthalij':
                     self.signals.log.emit("Error: Paquete 'Danenone' (Linux) incompatible con Windows.")
                     self.signals.done.emit(False, "")
                     return

                self.signals.log.emit("Extrayendo archivos...")
                tmpdir = Path(tempfile.mkdtemp(prefix="Fluthin_iflapp_"))
                extract_dir = tmpdir / "extract"
                extract_dir.mkdir(parents=True, exist_ok=True)

                if not extract_archive(self.local_file_path, str(extract_dir)):
                    self.signals.log.emit("Error: no se pudo extraer el paquete (formato o firma inválidos).")
                    self.signals.done.emit(False, "")
                    return

                self.signals.log.emit("Instalando...")
                dest_base = create_documents_app_folder(publisher, app_id, version, platformstr)
                move_install_tree(extract_dir, dest_base)
                normalize_install_permissions(dest_base)
                ensure_executable_bits(dest_base)
                
                # Shortcut logic
                exe_path = find_executable(dest_base, self.shortname)
                if exe_path:
                    desktop = Path.home() / 'Desktop'
                    shortcut_name = self.app_name if self.app_name else self.shortname
                    shortcut_name = re.sub(r'[<>:"/\\|?*]', '', shortcut_name)
                    create_shortcut(desktop, exe_path, shortcut_name)
                    self.signals.log.emit(f"Acceso directo creado: {shortcut_name}")
                
                shutil.rmtree(tmpdir, ignore_errors=True)
                self.signals.done.emit(True, str(dest_base))
                return

            # Online Mode
            self.signals.log.emit(f"Consultando GitHub API ({self.owner}/{self.repo})...")
            api = GITHUB_RELEASES_API.format(owner=self.owner, repo=self.repo)
            r = requests.get(api, timeout=15)
            if not r.ok:
                self.signals.log.emit(f"Error API: {r.status_code}")
                self.signals.ask_open_releases.emit(f"https://github.com/{self.owner}/{self.repo}/releases")
                self.signals.done.emit(False, "")
                return
            
            releases = r.json()
            assets = []
            for rel in releases:
                for a in rel.get('assets', []):
                    a['_release_tag'] = rel.get('tag_name')
                    assets.append(a)
            
            if not assets:
                self.signals.log.emit("No se encontraron assets.")
                self.signals.done.emit(False, "")
                return

            asset, version, platformstr = best_asset_for_platform(assets, self.shortname)
            if not asset:
                self.signals.log.emit("No hay instalador compatible (.iflapp) para tu sistema.")
                self.signals.ask_open_releases.emit(f"https://github.com/{self.owner}/{self.repo}/releases")
                self.signals.done.emit(False, "")
                return

            self.signals.log.emit(f"Descargando: {asset['name']} ({version})")
            
            tmpdir = Path(tempfile.mkdtemp(prefix="Fluthin_dl_"))
            downloaded = tmpdir / asset['name']
            
            try:
                download_file(asset['browser_download_url'], str(downloaded), lambda p: self.signals.progress.emit(p))
            except Exception as e:
                self.signals.log.emit(f"Error descarga: {e}")
                self.signals.done.emit(False, "")
                return

            self.signals.log.emit("Extrayendo...")
            extract_dir = tmpdir / "extract"
            extract_dir.mkdir(parents=True, exist_ok=True)
            if not extract_archive(str(downloaded), str(extract_dir)):
                self.signals.log.emit("Error: no se pudo extraer el paquete descargado.")
                self.signals.done.emit(False, "")
                return
            
            self.signals.log.emit("Instalando...")
            # La cabecera del paquete manda sobre el nombre del asset.
            header = read_package_identity(str(downloaded)) or {}
            publisher_to_use = header.get("publisher") or self.meta_publisher or self.owner
            app_id_to_use = header.get("app") or self.meta_app_id or self.shortname
            version_to_use = header.get("version") or version or "v1"
            platform_to_use = normalize_platform(header.get("platform") or platformstr or "unknown")
            dest_base = create_documents_app_folder(publisher_to_use, app_id_to_use, version_to_use, platform_to_use)
            move_install_tree(extract_dir, dest_base)
            normalize_install_permissions(dest_base)
            ensure_executable_bits(dest_base)
            
            # Download details.xml to install folder for future reference
            try:
                details_url = f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/main/details.xml"
                r = requests.get(details_url, timeout=5)
                if r.ok:
                    (dest_base / "details.xml").write_bytes(r.content)
            except Exception:
                pass

            # Shortcut logic
            exe_path = find_executable(dest_base, self.shortname)
            if exe_path:
                desktop = Path.home() / 'Desktop'
                # Use app_name for shortcut
                shortcut_name = self.app_name if self.app_name else f"{self.owner}.{self.shortname}"
                # Sanitize filename
                shortcut_name = re.sub(r'[<>:"/\\|?*]', '', shortcut_name)
                create_shortcut(desktop, exe_path, shortcut_name)
                self.signals.log.emit(f"Acceso directo creado: {shortcut_name}")
            
            shutil.rmtree(tmpdir, ignore_errors=True)
            self.signals.done.emit(True, str(dest_base))
            
        except Exception as ex:
            self.signals.log.emit(f"Error crítico: {ex}")
            self.signals.done.emit(False, "")

def restart_pc_delayed(seconds: int = 60):
    """Schedule a PC restart after specified seconds."""
    try:
        if platform.system().lower() == 'windows':
            subprocess.run(['shutdown', '/r', '/t', str(seconds), '/c', 
                          f'Reiniciando en {seconds} segundos para aplicar cambios de registro de Fluthin Handler...'], 
                          check=False)
            return True
    except Exception:
        pass
    return False

def cancel_restart():
    """Cancel a scheduled restart."""
    try:
        if platform.system().lower() == 'windows':
            subprocess.run(['shutdown', '/a'], check=False)
            return True
    except Exception:
        pass
    return False

def handle_iflapp_file(file_path: str):
    """Abre un paquete ``.iflapp`` v2, ``.asksome`` o un descriptor ``.mexf``.

    ``.iflapp`` y ``.asksome`` abren la ventana de instalación unificada; un
    ``.mexf`` declara su propia integración de shell y se aplica directamente.
    """
    try:
        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            QtWidgets.QMessageBox.critical(None, "Error", f"Archivo no encontrado: {file_path}")
            return None

        lower = file_path.lower()
        if lower.endswith('.mexf'):
            return handle_mexf_file(file_path)

        if not (lower.endswith('.iflapp') or lower.endswith('.asksome')):
            QtWidgets.QMessageBox.critical(
                None, "Error",
                "El archivo debe tener extensión .iflapp, .asksome o .mexf",
            )
            return None

        # Open unified InstallWindow
        w = InstallWindow(repo="", owner="", local_file_path=file_path)
        _reveal_window(w, file_path)
        return w

    except Exception as e:
        QtWidgets.QMessageBox.critical(None, "Error de Instalación", f"Error al abrir el paquete:\n{str(e)}")
        return None


def handle_mexf_file(file_path: str):
    """Aplica la integración de shell declarada en un descriptor ``.mexf``.

    El ``.mexf`` no es un paquete de instalación: describe asociaciones,
    menús y accesos directos. Se aplica el plan con ``lib.mexf_shell`` y se
    informa al usuario de los archivos escritos.
    """
    if not HAS_PACKAGE_LIBS:
        QtWidgets.QMessageBox.critical(None, "Error", f"Faltan las librerías de paquetes: {_PACKAGE_LIBS_ERROR}")
        return None
    try:
        from lib import mexf_shell
    except Exception as exc:
        QtWidgets.QMessageBox.critical(None, "Error", f"No se pudo cargar el shell .mexf: {exc}")
        return None
    try:
        plan = mexf_shell.load_shell_plan(file_path)
        result = mexf_shell.install_plan(plan)
        written = len(result.get("written", []))
        skipped = result.get("skipped", [])
        message = f"Integración de shell aplicada desde:\n{os.path.basename(file_path)}\n\n{written} archivos escritos."
        if skipped:
            message += "\n\nOmitidos:\n" + "\n".join(skipped)
        QtWidgets.QMessageBox.information(None, "Fluthin Handler", message)
        return plan
    except Exception as exc:
        QtWidgets.QMessageBox.critical(None, "Error", f"No se pudo aplicar el .mexf: {exc}")
        return None


HEADLESS_FLAGS = (
    "--register-shell",
    "--unregister-shell",
    "--info",
    "--list-extensions",
    "--version",
    "--help",
    "-h",
)


def _print_help() -> int:
    print(
        "FlArm Handler — gestor de paquetes .iflapp/.asksome y descriptores .mexf\n\n"
        "Uso:\n"
        "  flarmhandler.py                      Abre la interfaz de instalación.\n"
        "  flarmhandler.py -l <archivo>         Instala/abre un .iflapp, .asksome o .mexf.\n"
        "  flarmhandler.py -u <url>             Abre un enlace Fluthinstore://owner.repo.\n"
        "\nAcciones headless (sin ventana):\n"
        "  --register-shell                     Asocia .iflapp/.asksome con icono y descripción.\n"
        "  --unregister-shell                   Retira esas asociaciones.\n"
        "  --info <archivo>                     Muestra la identidad del paquete (cabecera).\n"
        "  --list-extensions                    Lista las extensiones y tipos MIME asociados.\n"
        "  --version                            Muestra la versión del handler.\n"
    )
    return 0


def _print_version() -> int:
    try:
        version = (Path(__file__).parent / "version.res").read_text(encoding="utf-8", errors="replace")
    except OSError:
        version = "desconocida"
    print(f"FlArm Handler (flarmhandler) — {version.splitlines()[0].strip() if version else 'desconocida'}")
    return 0


def _list_extensions() -> int:
    if not HAS_PACKAGE_LIBS:
        print(f"Faltan las librerías de paquetes: {_PACKAGE_LIBS_ERROR}")
        return 1
    for extension, (mime, label, description) in _package_shell.EXTENSIONS.items():
        print(f"{extension}\t{mime}\t{label}\t{description}")
    return 0


def _package_info(path: str) -> int:
    if not HAS_PACKAGE_LIBS:
        print(f"Faltan las librerías de paquetes: {_PACKAGE_LIBS_ERROR}")
        return 1
    try:
        info = _native_shell.package_info(path)
    except Exception as exc:
        print(f"Error: {exc}")
        return 1
    print(json.dumps(info, indent=2, ensure_ascii=False))
    return 0


def _handle_headless(argv) -> "int | None":
    """Atiende las acciones de shell sin crear la ventana.

    Devuelve el código de salida, o ``None`` si no era una acción headless.
    """
    if not argv:
        return None
    flag = argv[0].strip()
    if flag in ("--help", "-h"):
        return _print_help()
    if flag == "--version":
        return _print_version()
    if flag == "--list-extensions":
        return _list_extensions()
    if flag == "--info":
        if len(argv) < 2:
            print("uso: --info <archivo.iflapp|.asksome>")
            return 2
        return _package_info(argv[1].strip().strip('"').strip("'"))
    if flag in ("--register-shell", "--unregister-shell"):
        python_path = sys.executable
        script_path = os.path.abspath(sys.argv[0])
        if flag == "--register-shell":
            ok, msg = register_package_associations(python_path, script_path)
        else:
            ok, msg = unregister_package_associations()
        print(("OK: " if ok else "ERROR: ") + msg)
        return 0 if ok else 1
    return None


def _reveal_window(window, package_path: str | None = None):
    """Muestra *window* con un splash integrado que se desvanece al dibujarse.

    El splash no usa assets: es una ventana del tamaño de *window*, con el fondo
    del acento del SO y el icono del paquete (``app/app-icon.ico``) centrado. Si
    no se puede construir (sin PyQt) la ventana se muestra directamente.
    """
    if not HAS_SPLASH_LIB or _splash is None:
        window.show()
        return
    accent = getattr(window, "accent", DEFAULT_ACCENT)
    icon_source = _splash.resolve_icon_source(window)
    try:
        splash = _splash.IntegratedSplash(
            parent=window, icon_source=icon_source, accent=accent,
        )
        splash.finish_when_ready(window)
        splash.start()
    except Exception:
        window.show()


def main(argv):
    python_path = sys.executable
    script_path = os.path.abspath(argv[0])

    # === ACCIONES HEADLESS (sin ventana) ===
    headless = _handle_headless(argv[1:])
    if headless is not None:
        return headless

    # === REGISTRATION ===
    # Registra el protocolo y, además, las asociaciones .iflapp/.asksome con
    # icono y descripción, para que el explorador los trate como ejecutables.
    # No requiere privilegios de administrador (se usa el ámbito de usuario).
    try:
        system = platform.system().lower()
        if 'windows' in system:
            register_scheme_windows(python_path, script_path)
        register_package_associations(python_path, script_path)
    except Exception:
        pass

    # === APP EXECUTION ===
    app = QtWidgets.QApplication(argv)
    accent = system_accent_color()
    app.setStyleSheet(build_global_qss(accent))

    # Parse arguments with explicit flags
    if len(argv) >= 2:
        arg1 = argv[1].strip().strip('"').strip("'")

        # Check for explicit flags
        if arg1 == "-u" and len(argv) >= 3:
            # URL flag: -u Fluthinstore://owner.repo
            url = argv[2].strip().strip('"').strip("'")
            try:
                repo, owner = parse_Fluthin_url(url)
                w = InstallWindow(repo, owner)
                _reveal_window(w)
            except Exception as e:
                QtWidgets.QMessageBox.critical(None, "Error", f"URL inválida: {e}")
                return 1

        elif arg1 == "-l" and len(argv) >= 3:
            # Local file flag: -l "path/to/file.iflapp"
            file_path = argv[2].strip().strip('"').strip("'")
            file_path = os.path.abspath(file_path)
            w = handle_iflapp_file(file_path)
            if not w:
                return 1

        else:
            # No explicit flag, try to auto-detect (backward compatibility)
            arg = arg1
            arg_path = os.path.abspath(arg) if not arg.startswith(f"{SCHEME}:") else arg
            lower = arg.lower()

            # Priority 1: Check if it's an existing package file
            if os.path.exists(arg_path) and lower.endswith(('.iflapp', '.asksome', '.mexf')):
                w = handle_iflapp_file(arg_path)
                if not w:
                    return 1

            # Priority 2: Check if argument ends with a package extension
            elif lower.endswith(('.iflapp', '.asksome', '.mexf')):
                w = handle_iflapp_file(arg)
                if not w:
                    return 1

            # Priority 3: Handle Fluthinstore:// protocol
            elif arg.startswith(f"{SCHEME}:") or arg.startswith(f"{SCHEME}://"):
                try:
                    repo, owner = parse_Fluthin_url(arg)
                    w = InstallWindow(repo, owner)
                    _reveal_window(w)
                except Exception as e:
                    QtWidgets.QMessageBox.critical(None, "Error", f"URL inválida: {e}")
                    return 1
            else:
                # Unknown argument, show manual input
                text, ok = QtWidgets.QInputDialog.getText(None, "Fluthin Handler",
                    f"Argumento no reconocido: {arg}\n\nIntroduce una URL de Fluthin (Fluthinstore://owner.repo):")
                if ok and text:
                    try:
                        repo, owner = parse_Fluthin_url(text)
                        w = InstallWindow(repo, owner)
                        _reveal_window(w)
                    except Exception as e:
                        QtWidgets.QMessageBox.critical(None, "Error", f"URL inválida: {e}")
                        return 1
                else:
                    return 0
    else:
        # No arguments - Just show a success message for the registration
        QtWidgets.QMessageBox.information(None, "Fluthin Handler",
            "Registro actualizado correctamente.\n\nEl handler quedó asociado a los paquetes .iflapp y .asksome (icono y descripción incluidos).")
        return 0

    return app.exec()

if __name__ == "__main__":
    sys.exit(main(sys.argv))
