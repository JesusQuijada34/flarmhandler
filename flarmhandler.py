#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flarm Store handler (PyQt5 + Markdown + Custom Titlebar + Orange Theme)
"""

from __future__ import annotations
import sys, os, platform, tempfile, shutil, zipfile, tarfile, re, json, webbrowser, subprocess, requests, time, ctypes
from pathlib import Path
from urllib.parse import urlparse
from PyQt5 import QtWidgets, QtGui, QtCore, QtSvg

# --- Try to import PyQt5-Markdown widgets ---
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    import markdown
    HAS_MARKDOWN = True
except Exception:
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
    import pythoncom
    import win32com.client  # type: ignore
    HAS_PYWIN32 = True
except Exception:
    HAS_PYWIN32 = False

DEFAULT_SPLASH = "assets/splash.png"
DEFAULT_ICON = "assets/product_logo.png"
SPLASH_SETUP = "assets/splash_setup.png"

GITHUB_RAW_TEMPLATE = "https://raw.githubusercontent.com/{owner}/{repo}/main/assets/splash.png"
GITHUB_RELEASES_API = "https://api.github.com/repos/{owner}/{repo}/releases"
SCHEME = "flarmstore"
MIMETYPE = "application/x-flarmstore"

# --- Global QSS (Orange Theme) ---
GLOBAL_QSS = """
/* Global Reset */
* {
    outline: none;
}
QWidget {
    background: #ffffff;
    font-family: "Roboto", "Segoe UI", "Helvetica Neue", Helvetica, Arial, sans-serif;
    color: #202124;
    font-size: 14px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #f1f3f4;
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #dadce0;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #bdc1c6;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Buttons */
QPushButton {
    background-color: #ffffff;
    color: #ff6d00;
    border: 1px solid #dadce0;
    border-radius: 4px;
    padding: 8px 24px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QPushButton:hover {
    background-color: #fff3e0;
    border-color: #ffb74d;
}
QPushButton:pressed {
    background-color: #ffe0b2;
}
QPushButton:disabled {
    color: #bdc1c6;
    border-color: #f1f3f4;
}

/* Primary Button (Install) */
QPushButton#PrimaryBtn {
    background-color: #ff6d00;
    color: #ffffff;
    border: none;
}
QPushButton#PrimaryBtn:hover {
    background-color: #f57c00;
}
QPushButton#PrimaryBtn:pressed {
    background-color: #ef6c00;
}
QPushButton#PrimaryBtn:disabled {
    background-color: #e8eaed;
    color: #9aa0a6;
}

/* Inputs */
QLineEdit, QTextEdit {
    background: #ffffff;
    border: 1px solid #dadce0;
    border-radius: 4px;
    padding: 8px;
    selection-background-color: #ffe0b2;
    selection-color: #202124;
}
QLineEdit:focus, QTextEdit:focus {
    border: 2px solid #ff6d00;
    padding: 7px;
}

/* Custom Title Bar */
#TitleBar {
    background-color: #ffffff;
    min-height: 32px;
}
#TitleLabel {
    color: #5f6368;
    font-size: 12px;
    padding-left: 10px;
}
#TitleBtn {
    background: transparent;
    border: none;
    border-radius: 0px;
    padding: 0px;
    min-width: 46px;
    max-width: 46px;
    min-height: 32px;
    max-height: 32px;
}
#TitleBtn:hover {
    background-color: #e8eaed;
}
#TitleBtn#close:hover {
    background-color: #e81123;
    color: white;
}

/* Header Area */
#HeaderArea {
    background-color: #ffffff;
    border-bottom: 1px solid #dadce0;
}
#AppTitle {
    font-size: 24px;
    font-weight: 500;
    color: #202124;
}
#AppMeta {
    color: #ff6d00;
    font-weight: 500;
    font-size: 14px;
}
#AppVersion {
    color: #5f6368;
    font-size: 12px;
}

/* Logs */
#LogArea {
    background-color: #202124;
    color: #e8eaed;
    font-family: "Consolas", monospace;
    font-size: 12px;
    border: none;
    border-radius: 4px;
}
"""

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

def parse_flarm_url(url: str) -> tuple[str, str]:
    if not url:
        raise ValueError("No URL provided")
    clean_url = url.replace(f"{SCHEME}://", "").replace(f"{SCHEME}:", "")
    if clean_url.endswith('/'):
        clean_url = clean_url[:-1]
    parts = clean_url.split('.')
    if len(parts) >= 2:
        owner = parts[0]
        repo = '.'.join(parts[1:])
        return repo, owner
    else:
        raise ValueError(f"URL inválida: {url}. Debe ser flarmstore://username.repo")

def platform_system_tag_for_asset() -> str:
    return platform_tag()

def best_asset_for_platform(assets: list, shortname: str) -> tuple[dict | None, str | None, str | None]:
    plat = platform_system_tag_for_asset().lower()
    aliases = {
        'knosthalij': ['knosthalij', 'windows', 'win'],
        'danenone': ['danenone', 'linux', 'mac', 'macos', 'darwin']
    }
    
    def match_name(name: str) -> bool:
        if not name.lower().endswith('.iflapp'):
            return False
        m = re.match(r'^(.+?)-([0-9A-Za-z\.\-_]+)-([0-9A-Za-z\._\-]+)\.iflapp$', name, re.IGNORECASE)
        if not m:
            return False
        platpart = m.group(3).lower()
        for key, vals in aliases.items():
            if plat in [key] and any(v in platpart for v in vals):
                return True
        return False

    for a in assets:
        if match_name(a.get('name','')):
            m = re.match(r'^(.+?)-([0-9A-Za-z\.\-_]+)-([0-9A-Za-z\._\-]+)\.iflapp$', a.get('name',''), re.IGNORECASE)
            if m:
                return a, m.group(2), m.group(3)
    
    for a in assets:
        name = a.get('name','')
        if name.lower().endswith('.iflapp') and name.lower().startswith(shortname.lower() + '-'):
             m = re.match(r'^(.+?)-([0-9A-Za-z\.\-_]+)-([0-9A-Za-z\._\-]+)\.iflapp$', name, re.IGNORECASE)
             if m:
                 return a, m.group(2), m.group(3)
                 
    return None, None, None

def download_file(url: str, dest_path: str, progress_callback=None) -> str:
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

def extract_archive(file_path: str, extract_to: str) -> bool:
    file_path = str(file_path)
    if zipfile.is_zipfile(file_path):
        with zipfile.ZipFile(file_path, 'r') as z:
            z.extractall(extract_to)
        return True
    try:
        if tarfile.is_tarfile(file_path):
            with tarfile.open(file_path, 'r:*') as t:
                t.extractall(extract_to)
            return True
    except Exception:
        pass
    dest = Path(extract_to) / Path(file_path).name
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
    # New format: {publisher}.{app}.{version}-{platform}
    base = documents / 'FLARM Apps' / f"{publisher}.{app}.{version}-{platformstr}"
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
            except Exception as e:
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
def check_registry_keys(python_path: str, script_path: str) -> bool:
    if winreg is None: return False
    expected_cmd = f"\"{python_path}\" \"{script_path}\" \"%1\""
    expected_icon = get_icon_path()
    
    def normalize(s):
        return os.path.normcase(os.path.abspath(s) if s else "")

    # Helper to check a key
    def check_key(root, key_path, expected_val=None):
        try:
            key = winreg.OpenKey(root, key_path)
            val, _ = winreg.QueryValueEx(key, "")
            winreg.CloseKey(key)
            if expected_val:
                return val.lower() == expected_val.lower()
            return True
        except Exception:
            return False

    # 1. Check Protocol in HKCU
    if not check_key(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{SCHEME}\shell\open\command", expected_cmd):
        if not check_key(winreg.HKEY_CLASSES_ROOT, rf"{SCHEME}\shell\open\command", expected_cmd):
            return False
            
    # 2. Check .iflapp extension in HKCU
    if not check_key(winreg.HKEY_CURRENT_USER, rf"Software\Classes\.iflapp", "Flarm.Package"):
        if not check_key(winreg.HKEY_CLASSES_ROOT, rf".iflapp", "Flarm.Package"):
            return False
            
    # 3. Check Icon for Flarm.Package
    # We check if the current icon matches what we expect. If not, we return False to trigger an update.
    # We try to match either raw path or path,0
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Flarm.Package\DefaultIcon")
        val, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
        
        # Normalize paths for comparison
        current_icon = val.lower().replace(",0", "")
        target_icon = expected_icon.lower()
        
        if current_icon != target_icon:
            return False
    except Exception:
        # Key doesn't exist or error reading it
        return False
            
    return True

def get_icon_path() -> str:
    """Get the correct path to flarmpack.ico whether running as script or compiled."""
    if hasattr(sys, '_MEIPASS'):
        # Running as compiled executable (PyInstaller)
        base_path = Path(sys._MEIPASS)
    else:
        # Running as script
        base_path = Path(__file__).parent
    
    icon_path = base_path / "app" / "flarmpack.ico"
    
    # Fallback to app-icon.ico if flarmpack.ico doesn't exist
    if not icon_path.exists():
        icon_path = base_path / "app" / "app-icon.ico"
    
    return str(icon_path)

def register_scheme_windows(python_path: str, script_path: str) -> tuple[bool, str]:
    if winreg is None:
        return False, "winreg module not available"
    
    cmd = f"\"{python_path}\" \"{script_path}\" \"%1\""
    icon_path = get_icon_path()
    
    try:
        # 1. Register Protocol flarmstore://
        key_path = rf"Software\Classes\{SCHEME}"
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "URL:Flarm Store Protocol")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        
        # Icon
        if os.path.exists(icon_path):
            icon_key = winreg.CreateKey(key, "DefaultIcon")
            winreg.SetValueEx(icon_key, None, 0, winreg.REG_SZ, f"{icon_path},0")
            winreg.CloseKey(icon_key)
            
        shell = winreg.CreateKey(key, r"shell\open\command")
        winreg.SetValueEx(shell, None, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(shell)
        winreg.CloseKey(key)
        
        # 2. Register .iflapp extension
        # .iflapp -> Flarm.Package
        key_ext = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.iflapp")
        winreg.SetValueEx(key_ext, None, 0, winreg.REG_SZ, "Flarm.Package")
        winreg.CloseKey(key_ext)
        
        # Flarm.Package -> Command
        key_progid = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Flarm.Package")
        winreg.SetValueEx(key_progid, None, 0, winreg.REG_SZ, "Flarm Package")
        
        if os.path.exists(icon_path):
            icon_key = winreg.CreateKey(key_progid, "DefaultIcon")
            winreg.SetValueEx(icon_key, None, 0, winreg.REG_SZ, f"{icon_path},0")
            winreg.CloseKey(icon_key)
            
        shell_progid = winreg.CreateKey(key_progid, r"shell\open\command")
        winreg.SetValueEx(shell_progid, None, 0, winreg.REG_SZ, cmd)
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
        desktop_file = user_apps / f"flarmstore-handler.desktop"
        exec_cmd = f"{python_path} {script_path} %u"
        
        icon_path = get_icon_path()
        
        content = "[Desktop Entry]\nName=Flarmstore Handler\nExec=" + exec_cmd + "\nType=Application\nTerminal=false\nMimeType=x-scheme-handler/" + SCHEME + ";\n"
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
        app_name = "FlarmHandler.app"
        app_dir = apps_dir / app_name
        contents = app_dir / "Contents"
        macos_dir = contents / "MacOS"
        resources = contents / "Resources"
        macos_dir.mkdir(parents=True, exist_ok=True)
        resources.mkdir(parents=True, exist_ok=True)
        
        # Copy icon
        icon_src = get_icon_path()
        if os.path.exists(icon_src):
            shutil.copy(icon_src, resources / "flarmpack.ico")
        
        wrapper = macos_dir / "flarmhandler"
        wrapper_text = "#!/bin/bash\n\"" + python_path + "\" \"" + script_path + "\" \"$@\"\n"
        wrapper.write_text(wrapper_text, encoding='utf-8')
        wrapper.chmod(0o755)
        info_plist = contents / "Info.plist"
        plist_lines = []
        plist_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        plist_lines.append('<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">')
        plist_lines.append('<plist version="1.0">')
        plist_lines.append('<dict>')
        plist_lines.append('    <key>CFBundleName</key><string>FlarmHandler</string>')
        plist_lines.append('    <key>CFBundleIdentifier</key><string>com.flarm.handler</string>')
        plist_lines.append('    <key>CFBundleExecutable</key><string>flarmhandler</string>')
        plist_lines.append('    <key>CFBundlePackageType</key><string>APPL</string>')
        plist_lines.append('    <key>CFBundleShortVersionString</key><string>1.0</string>')
        if os.path.exists(icon_src):
             plist_lines.append('    <key>CFBundleIconFile</key><string>flarmpack.ico</string>')
        plist_lines.append('    <key>CFBundleURLTypes</key>')
        plist_lines.append('    <array>')
        plist_lines.append('        <dict>')
        plist_lines.append('            <key>CFBundleURLName</key><string>Flarm Store</string>')
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
            return True, "Already registered correctly", False
        
        # Try to register in HKCU (no admin needed usually)
        success, msg = register_scheme_windows(python_path, script_path)
        if success:
            return True, msg, True  # Registry was modified
            
        # If failed, maybe we need admin rights (though HKCU shouldn't need it)
        # But if we were trying HKCR before, we might need it.
        # Our new logic prefers HKCU.
        if not is_admin():
            return False, "ELEVATION_REQUIRED", False
        return False, msg, False
    if 'linux' in system:
        success, msg = register_scheme_linux(python_path, script_path)
        return success, msg, success
    if 'darwin' in system:
        success, msg = register_scheme_macos(python_path, script_path)
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
        
        self.title_label = QtWidgets.QLabel("Flarm Installer")
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
        btn.setObjectName(f"TitleBtn")
        btn.setProperty("class", name)
        if name == "close":
            btn.setObjectName("TitleBtn")
            btn.setProperty("id", "close")
        
        # Create icon
        pixmap = QtGui.QPixmap(46, 32)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
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
        if self.window().isMaximized():
            self.window().showNormal()
            self.btn_max.setIcon(self.create_btn("maximize").icon())
        else:
            self.window().showMaximized()
            self.btn_max.setIcon(self.create_btn("restore").icon())

    def mousePressEvent(self, event):
        self.start = self.mapToGlobal(event.pos())
        self.pressing = True

    def mouseMoveEvent(self, event):
        if self.pressing:
            end = self.mapToGlobal(event.pos())
            movement = end - self.start
            self.window().setGeometry(self.window().geometry().translated(movement))
            self.start = end

    def mouseReleaseEvent(self, event):
        self.pressing = False

class BlurredBanner(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(220)
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.bg_label = QtWidgets.QLabel(self)
        self.bg_label.setScaledContents(True)
        
        self.fg_label = QtWidgets.QLabel(self)
        self.fg_label.setAlignment(QtCore.Qt.AlignCenter)
        
    def setPixmap(self, pixmap):
        self._original_pixmap = pixmap
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
        
        scaled_pix = self._original_pixmap.scaled(w, new_h, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        
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
            cover_pix = self._original_pixmap.scaled(w, h, QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation)
            # Crop center of cover
            cx = (cover_pix.width() - w) // 2
            cy = (cover_pix.height() - h) // 2
            bg_cropped = cover_pix.copy(cx, cy, w, h)
            
            # Blur
            small = bg_cropped.scaled(20, 20, QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)
            blurred = small.scaled(w, h, QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)
            
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
    
    base_dir = documents / 'FLARM Apps'
    if not base_dir.exists():
        return None
    
    # Check for exact folder name: {publisher}.{app}.{version}-{platform}
    folder_name = f"{publisher}.{app}.{version}-{platform}"
    target_path = base_dir / folder_name
    
    if target_path.exists() and target_path.is_dir():
        return target_path
    return None

def find_installed_path(owner: str, repo: str) -> Path | None:
    """Checks if the app is installed in Documents/FLARM Apps (legacy, loose match)."""
    home = Path.home()
    if os.name == 'nt':
        documents = Path(os.path.join(os.environ.get('USERPROFILE',''), 'Documents'))
    else:
        documents = home / 'Documents'
    
    base_dir = documents / 'FLARM Apps'
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
        self.temp_extract_dir = None # To clean up later if needed
        
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

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
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
        self.main_layout.addWidget(self.banner)
        
        # Header Info Area
        header = QtWidgets.QWidget()
        header.setObjectName("HeaderArea")
        header.setFixedHeight(100)
        h_layout = QtWidgets.QHBoxLayout(header)
        h_layout.setContentsMargins(30, 15, 30, 15)
        h_layout.setSpacing(20)
        
        # Icon
        self.icon_label = QtWidgets.QLabel()
        self.icon_label.setFixedSize(72, 72)
        self.icon_label.setStyleSheet("background: #f1f3f4; border-radius: 12px; border: 1px solid #dadce0;")
        self.icon_label.setScaledContents(True)
        if os.path.exists(DEFAULT_ICON):
             self.icon_label.setPixmap(QtGui.QPixmap(DEFAULT_ICON))
        h_layout.addWidget(self.icon_label)
        
        # Text Info
        meta_v = QtWidgets.QVBoxLayout()
        meta_v.setSpacing(4)
        self.title_lbl = QtWidgets.QLabel(self.app_name)
        self.title_lbl.setObjectName("AppTitle")
        meta_v.addWidget(self.title_lbl)
        
        self.meta_lbl = QtWidgets.QLabel(self.meta_publisher)
        self.meta_lbl.setObjectName("AppMeta")
        meta_v.addWidget(self.meta_lbl)
        
        self.ver_lbl = QtWidgets.QLabel(f"Plataforma: {self.meta_platform}")
        self.ver_lbl.setObjectName("AppVersion")
        meta_v.addWidget(self.ver_lbl)
        
        h_layout.addLayout(meta_v)
        h_layout.addStretch()
        
        # Actions
        action_h = QtWidgets.QHBoxLayout()
        action_h.setSpacing(10)
        
        self.install_btn = QtWidgets.QPushButton("Instalar")
        self.install_btn.setObjectName("PrimaryBtn")
        self.install_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.install_btn.setMinimumWidth(120)
        action_h.addWidget(self.install_btn)
        
        self.share_btn = QtWidgets.QPushButton("Compartir")
        self.share_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.share_btn.setMinimumWidth(120)
        action_h.addWidget(self.share_btn)

        if self.installed_path:
            self.uninstall_btn = QtWidgets.QPushButton("Desinstalar")
            self.uninstall_btn.setCursor(QtCore.Qt.PointingHandCursor)
            self.uninstall_btn.setMinimumWidth(120)
            self.uninstall_btn.setStyleSheet("color: #d93025; border: 1px solid #f28b82;")
            action_h.addWidget(self.uninstall_btn)
        
        h_layout.addLayout(action_h)
        
        self.main_layout.addWidget(header)
        
        # Content Area (Split)
        content = QtWidgets.QWidget()
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
            self.readme_view.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        else:
            self.readme_view = QtWidgets.QTextEdit()
            self.readme_view.setReadOnly(True)
            self.readme_view.setStyleSheet("border: none; background: #ffffff;")
            
        left_layout.addWidget(self.readme_view)
        c_layout.addWidget(left_panel, 65)
        
        # Right: Progress & Logs
        right_panel = QtWidgets.QWidget()
        r_layout = QtWidgets.QVBoxLayout(right_panel)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(10)
        
        lbl_log = QtWidgets.QLabel("Estado de instalación")
        lbl_log.setStyleSheet("font-weight: bold; color: #202124;")
        r_layout.addWidget(lbl_log)
        
        self.progress = QtWidgets.QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setStyleSheet("QProgressBar { border: none; background: #e8eaed; border-radius: 2px; } QProgressBar::chunk { background: #ff6d00; border-radius: 2px; }")
        r_layout.addWidget(self.progress)
        
        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName("LogArea")
        r_layout.addWidget(self.log)
        
        c_layout.addWidget(right_panel, 35)
        
        self.main_layout.addWidget(content)
        
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
            # Enable share button for local packages if we have author info
            # self.share_btn.setVisible(False)  # Keep it visible now
            self.meta_lbl.setText(f"{self.meta_publisher} (Local)")
            self.ver_lbl.setText(f"Versión: {self.meta_version} | Plataforma: {self.meta_platform}")
            
            # Check Compatibility
            is_compat, msg = check_platform_compatibility(self.meta_platform)
            if not is_compat:
                self.install_btn.setEnabled(False)
                self.install_btn.setText("Incompatible")
                self.install_btn.setStyleSheet("background-color: #d93025; color: white;")
                QtWidgets.QMessageBox.critical(self, "Incompatible", msg)
            
            # Load local assets if available
            self.load_local_assets_to_ui()

    def load_local_package_metadata(self):
        """Extracts details.xml from the local package to populate metadata."""
        try:
            self.temp_extract_dir = Path(tempfile.mkdtemp(prefix="flarm_meta_"))
            with zipfile.ZipFile(self.local_file_path, 'r') as z:
                # Try to extract details.xml
                if "details.xml" in z.namelist():
                    z.extract("details.xml", self.temp_extract_dir)
                    details_path = self.temp_extract_dir / "details.xml"
                    content = details_path.read_text(encoding='utf-8')
                    data = parse_details_xml(content)
                    
                    self.app_name = data.get('name', self.app_name)
                    self.meta_publisher = data.get('publisher', self.meta_publisher)
                    self.meta_app = data.get('app', self.meta_app)
                    self.meta_version = data.get('version', self.meta_version)
                    self.meta_platform = data.get('platform', self.meta_platform)
                    self.meta_author = data.get('author', self.meta_author)
                    
                    # Update owner/repo for remote fallback
                    if data.get('publisher'): self.owner = data.get('publisher')
                    if data.get('app'): self.repo = data.get('app')
                
                # Extract assets if they exist
                assets_to_extract = []
                for f in z.namelist():
                    if f.startswith("assets/") or f.startswith("app/"):
                        assets_to_extract.append(f)
                
                if assets_to_extract:
                    z.extractall(self.temp_extract_dir, members=assets_to_extract)
                    
        except Exception as e:
            print(f"Error reading local package metadata: {e}")

    def load_local_assets_to_ui(self):
        """Loads icons and banner from the extracted temp dir."""
        if not self.temp_extract_dir: return
        
        # Icon
        icon_path = self.temp_extract_dir / "app" / "app-icon.ico"
        if not icon_path.exists():
             icon_path = self.temp_extract_dir / "app" / "app-icon.png"
        
        if icon_path.exists():
            pix = QtGui.QPixmap(str(icon_path))
            self.icon_label.setPixmap(pix.scaled(72, 72, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            
        # Banner
        banner_path = self.temp_extract_dir / "assets" / "splash.png"
        if banner_path.exists():
            pix = QtGui.QPixmap(str(banner_path))
            self.banner.setPixmap(pix)

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
        cursor.movePosition(QtGui.QTextCursor.End)
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
            self.meta_lbl.setText(self.meta_publisher)
            self.ver_lbl.setText(f"Versión: {self.meta_version} | Plataforma: {self.meta_platform}")

        # Icon
        try:
            icon_url = f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/main/app/app-icon.ico"
            r = requests.get(icon_url, timeout=4)
            if r.ok:
                pix = QtGui.QPixmap()
                pix.loadFromData(r.content)
                self.icon_label.setPixmap(pix.scaled(72, 72, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            else:
                icon_url_png = f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/main/app/app-icon.png"
                r = requests.get(icon_url_png, timeout=4)
                if r.ok:
                    pix = QtGui.QPixmap()
                    pix.loadFromData(r.content)
                    self.icon_label.setPixmap(pix.scaled(72, 72, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        except Exception:
            pass

        # Banner
        try:
            banner_url = GITHUB_RAW_TEMPLATE.format(owner=self.owner, repo=self.repo)
            r = requests.get(banner_url, timeout=5)
            if r.ok:
                pix = QtGui.QPixmap()
                pix.loadFromData(r.content)
                self.banner.setPixmap(pix)
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
                style = "<style>body { font-family: Roboto, sans-serif; color: #202124; line-height: 1.6; } a { color: #ff6d00; text-decoration: none; } code { background: #f1f3f4; padding: 2px 4px; border-radius: 4px; } h1, h2, h3 { color: #202124; }</style>"
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
            r = requests.get(f"https://is.gd/create.php?format=simple&url={long_url}", timeout=5)
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
        reply = QtWidgets.QMessageBox.question(self, 'Confirmar desinstalación', 
                                             f"¿Estás seguro de que quieres desinstalar {self.app_name}?",
                                             QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
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
        
        worker = InstallWorker(self.repo, self.owner, self.shortname, self.app_name, self.local_file_path, self.meta_app, self.meta_publisher)
        worker.signals.log.connect(self.log_msg)
        worker.signals.progress.connect(self.set_progress)
        worker.signals.done.connect(self.install_finished)
        worker.signals.ask_open_releases.connect(self.offer_open_releases)
        QtCore.QThreadPool.globalInstance().start(worker)

    def offer_open_releases(self, url: str):
        res = QtWidgets.QMessageBox.question(self, "Abrir releases", "No se encontró un instalador compatible. ¿Abrir GitHub Releases?")
        if res == QtWidgets.QMessageBox.Yes:
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
    def __init__(self, repo: str, owner: str, shortname: str, app_name: str, local_file_path: str = None, meta_app_id: str = None, meta_publisher: str = None):
        super().__init__()
        self.repo = repo
        self.owner = owner
        self.shortname = shortname
        self.app_name = app_name
        self.local_file_path = local_file_path
        self.meta_app_id = meta_app_id
        self.meta_publisher = meta_publisher
        self.signals = WorkerSignals()

    def run(self):
        try:
            if self.local_file_path:
                # Offline Mode
                self.signals.log.emit(f"Preparando instalación de paquete local...")
                
                # Parse filename for version/platform
                filename = os.path.basename(self.local_file_path)
                match = re.match(r'^(.+?)-([0-9A-Za-z\.\-_]+)-([0-9A-Za-z\._\-]+)\.iflapp$', filename, re.IGNORECASE)
                if match:
                    version = match.group(2)
                    platformstr = match.group(3)
                else:
                    version = "local"
                    platformstr = "unknown"

                # Check compatibility (Double check)
                if platformstr.lower() == 'danenone' and platform_tag() == 'win':
                     self.signals.log.emit("Error: Paquete 'Danenone' (Linux) incompatible con Windows.")
                     self.signals.done.emit(False, "")
                     return

                self.signals.log.emit("Extrayendo archivos...")
                tmpdir = Path(tempfile.mkdtemp(prefix="flarm_iflapp_"))
                extract_dir = tmpdir / "extract"
                extract_dir.mkdir(parents=True, exist_ok=True)
                
                extract_archive(self.local_file_path, str(extract_dir))
                
                self.signals.log.emit("Instalando...")
                # Use meta values if available, otherwise fallback to defaults
                publisher_to_use = self.meta_publisher if self.meta_publisher else self.owner
                app_id_to_use = self.meta_app_id if self.meta_app_id else self.shortname
                dest_base = create_documents_app_folder(publisher_to_use, app_id_to_use, version, platformstr)
                move_install_tree(extract_dir, dest_base)
                
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
            
            tmpdir = Path(tempfile.mkdtemp(prefix="flarm_dl_"))
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
            extract_archive(str(downloaded), str(extract_dir))
            
            self.signals.log.emit("Instalando...")
            # Use meta values if available, otherwise fallback to defaults
            publisher_to_use = self.meta_publisher if self.meta_publisher else self.owner
            app_id_to_use = self.meta_app_id if self.meta_app_id else self.shortname
            dest_base = create_documents_app_folder(publisher_to_use, app_id_to_use, version or "v1", platformstr or "unknown")
            move_install_tree(extract_dir, dest_base)
            
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

def restart_pc():
    """Restart the PC to apply registry changes."""
    try:
        if platform.system().lower() == 'windows':
            subprocess.run(['shutdown', '/r', '/t', '5', '/c', 'Reiniciando para aplicar cambios de registro de Flarm Handler...'], check=False)
            return True
    except Exception:
        pass
    return False

def handle_iflapp_file(file_path: str):
    """Handle .iflapp file as offline installer package."""
    try:
        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            QtWidgets.QMessageBox.critical(None, "Error", f"Archivo no encontrado: {file_path}")
            return None
        
        if not file_path.lower().endswith('.iflapp'):
            QtWidgets.QMessageBox.critical(None, "Error", "El archivo debe tener extensión .iflapp")
            return None
            
        # Open unified InstallWindow
        w = InstallWindow(repo="", owner="", local_file_path=file_path)
        w.show()
        return w
        
    except Exception as e:
        QtWidgets.QMessageBox.critical(None, "Error de Instalación", f"Error al abrir el paquete:\n{str(e)}")
        return None

def main(argv):
    python_path = sys.executable
    script_path = os.path.abspath(argv[0])
    
    # === NO ARGUMENTS: Registry Integrity Check Mode ===
    if len(argv) == 1:
        # Verify admin mode first
        if not is_admin():
            # Need to restart as admin
            if run_as_admin(argv):
                return 0  # Successfully elevated, this instance exits
            else:
                # User declined UAC or error occurred
                app = QtWidgets.QApplication(argv)
                QtWidgets.QMessageBox.warning(None, "Permisos Requeridos", 
                    "Se requieren permisos de administrador para verificar la integridad del registro.")
                return 1
        
        # Now we are admin, check registry integrity
        is_reg = check_registry_keys(python_path, script_path)
        registry_modified = False
        
        if not is_reg:
            # Registry needs to be updated
            success, msg, was_modified = ensure_registered(python_path, script_path)
            registry_modified = was_modified
            
            if not success:
                app = QtWidgets.QApplication(argv)
                QtWidgets.QMessageBox.critical(None, "Error de Registro", 
                    f"No se pudo registrar el protocolo y la extensión .iflapp:\n{msg}")
                return 1
        
        # If registry was modified, restart PC
        if registry_modified:
            app = QtWidgets.QApplication(argv)
            QtWidgets.QMessageBox.information(None, "Registro Actualizado", 
                "El registro ha sido actualizado correctamente.\n\nEl sistema se reiniciará en 5 segundos para aplicar los cambios.")
            restart_pc()
            return 0
        else:
            # Registry was already OK
            app = QtWidgets.QApplication(argv)
            QtWidgets.QMessageBox.information(None, "Integridad Verificada", 
                "La integridad del registro está correcta. No se requieren cambios.")
            return 0
    
    # === WITH ARGUMENTS: Normal Operation ===
    app = QtWidgets.QApplication(argv)
    app.setStyleSheet(GLOBAL_QSS)
    
    # Check if argument is a .iflapp file
    if len(argv) >= 2:
        arg = argv[1]
        
        # Handle .iflapp file
        if arg.lower().endswith('.iflapp') or (os.path.exists(arg) and arg.lower().endswith('.iflapp')):
            w = handle_iflapp_file(arg)
            if w:
                # Keep window alive
                pass
            else:
                return 1
        
        # Handle flarmstore:// protocol
        elif arg.startswith(f"{SCHEME}:") or arg.startswith(f"{SCHEME}://"):
            try:
                repo, owner = parse_flarm_url(arg)
                w = InstallWindow(repo, owner)
                w.show()
            except Exception as e:
                QtWidgets.QMessageBox.critical(None, "Error", f"URL inválida: {e}")
                return 1
        else:
            # Unknown argument, show manual input
            text, ok = QtWidgets.QInputDialog.getText(None, "Flarm Handler", 
                f"Argumento no reconocido: {arg}\n\nIntroduce una URL de Flarm (flarmstore://owner.repo):")
            if ok and text:
                try:
                    repo, owner = parse_flarm_url(text)
                    w = InstallWindow(repo, owner)
                    w.show()
                except Exception as e:
                    QtWidgets.QMessageBox.critical(None, "Error", f"URL inválida: {e}")
                    return 1
            else:
                return 0
    
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main(sys.argv))
