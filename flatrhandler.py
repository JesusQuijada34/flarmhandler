import sys
import os
import shutil
import zipfile
import tempfile
import argparse
import platform
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QCheckBox, QMessageBox, QFileDialog, QWizard,
    QWizardPage, QProgressBar, QListWidget, QComboBox, QLineEdit, QFormLayout
)
from PyQt5.QtGui import QPixmap, QIcon, QFont, QColor, QPalette
from PyQt5.QtCore import Qt, QTimer, QSize
import xml.etree.ElementTree as ET

# ==============================================
# FUNCIONES AUXILIARES
# ==============================================

def get_documents_path():
    """Obtiene la ruta de documentos según el SO"""
    if platform.system() == "Windows":
        return os.path.join(os.environ.get('USERPROFILE', ''), 'Documents')
    else:
        return os.path.join(os.path.expanduser('~'), 'Documents')

def associate_extensions_windows():
    """
    Asocia la extensión .iflapp con este instalador en Windows.
    Automáticamente si no está asociada.
    """
    try:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, '.iflapp') as check:
                val, _ = winreg.QueryValueEx(check, '')
                if val:
                    return True
        except Exception:
            pass

        if getattr(sys, 'frozen', False):
            exe_path = sys.executable
            command = f'"{exe_path}" "%1"'
        else:
            exe_path = os.path.abspath(sys.argv[0])
            python_exe = sys.executable
            command = f'"{python_exe}" "{exe_path}" "%1"'

        icon_path = os.path.join(os.getcwd(), 'app', 'app-icon.ico')
        if not os.path.isfile(icon_path):
            icon_to_use = exe_path
        else:
            icon_to_use = icon_path

        ext = '.iflapp'
        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, ext) as key:
            winreg.SetValue(key, '', winreg.REG_SZ, 'JerodinApp.Installer')

        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, 'JerodinApp.Installer') as key:
            winreg.SetValue(key, '', winreg.REG_SZ, 'Jerodin Application Installer')
            with winreg.CreateKey(key, 'DefaultIcon') as icon_key:
                winreg.SetValue(icon_key, '', winreg.REG_SZ, icon_to_use)

        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r'JerodinApp.Installer\shell\open\command') as key:
            winreg.SetValue(key, '', winreg.REG_SZ, command)

        return True
    except Exception as e:
        print(f"Error asociando extensión .iflapp: {str(e)}")
        return False

def is_extension_associated_windows():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, '.iflapp') as key:
            val, _ = winreg.QueryValueEx(key, '')
            return bool(val)
    except Exception:
        return False

def associate_extensions_unix():
    """
    Asocia la extensión .iflapp en Linux/Mac: crea un .desktop y entrada mime.
    Automático (idempotente).
    """
    try:
        home = os.path.expanduser('~')
        local_apps = os.path.join(home, '.local', 'share', 'applications')
        os.makedirs(local_apps, exist_ok=True)

        desktop_name = 'jerodin-iflapp-installer.desktop'
        desktop_path = os.path.join(local_apps, desktop_name)
        cmd = _get_executable_command().replace('%1', '"%f"')

        icon_path = os.path.join(os.getcwd(), 'app', 'app-icon.png')
        if not os.path.isfile(icon_path):
            icon_path = ''

        if not os.path.exists(desktop_path):
            content = [
                '[Desktop Entry]',
                'Type=Application',
                'Name=Jerodin Installer',
                f'Exec={cmd}',
                f'Icon={icon_path}',
                'MimeType=application/x-iflapp',
                'NoDisplay=false',
                'Categories=Utility;Application;'
            ]
            with open(desktop_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content))

        mime_file = os.path.join(local_apps, 'mimeapps.list')
        found = False
        default_section = '[Default Applications]'
        lines = []
        if os.path.exists(mime_file):
            with open(mime_file, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()
        for line in lines:
            if 'application/x-iflapp=' in line:
                found = True
                break
        if not found:
            if default_section not in lines:
                lines.append('\n' + default_section)
            lines.append(f'application/x-iflapp={desktop_name}')
            with open(mime_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

        return True
    except Exception as e:
        print(f"Error asociando extensión .iflapp en Unix: {e}")
        return False

def generateWorkState(dest_dir):
    """Genera un archivo __initrd__.fs de punto de entrada si no existe"""
    app_py_path = os.path.join(dest_dir, '__initrd__.fs')
    if not os.path.exists(app_py_path):
        with open(app_py_path, 'w', encoding='utf-8') as f:
            f.write("""f::LoadImage{
    f.LoadImage.StartDefnition(hybrid_pass.asDef)
    f.LoadImage.loadDir(assets_dir)
    f.LoadImage.loadFile(assets_dir)
    f.LoadImage.loadStoreDetail(xml_path.as)
    f.LoadImage.EndDefinition(Def)
    }::f.End
    f::LoadRAM{std.Out}::f.End
        WORKSTATE 1 :: [
        forceEnv(python_env)::
        __initrd__ :: Name.Invoker.As(StoreDetail.Find(__app__)) ::
        __bootrd__ :: parse.BootElf.As.SyntaxError(__id__)
        ] :: WORKSTATE 0
    ifNotFallout.BalloonError(x=decimal.decimal)[
        resolve.Host(github.io)
        LoadImage(f=Def)
    ]
    ShutDown.Reply.Host.As(Balloon.Ext)""")

def load_qss_from_package(temp_dir):
    """Carga QSS personalizado desde el paquete si existe, devuelve string QSS"""
    candidates = [
        os.path.join(temp_dir, 'app', 'style.qss'),
        os.path.join(temp_dir, 'assets', 'style.qss'),
        os.path.join(temp_dir, 'style.qss'),
        os.path.join('assets', 'style.qss'),
        os.path.join('app', 'style.qss'),
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception:
                continue
    # QSS más modernizado
    return """
    QWizard { background: qlineargradient(x1:0 y1:0 x2:1 y2:1, stop:0 #e3f2fd, stop:1 #e8f5e9);}
    QWizardPage { background: white; }
    QPushButton { background-color: #0062ff; color: white; border-radius: 5px; font-weight: bold; padding: 8px 18px; }
    QPushButton:disabled { background-color: #bdbdbd; color: #666; }
    QProgressBar { border: 1px solid #b3e5fc; border-radius: 7px; height: 21px; background: #f0f6fb;}
    QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #64b5f6, stop:1 #81c784); }
    QLabel#Title { font-size: 21px; font-weight: bold; color: #222; }
    QLabel#SubTitle { color: #505050; }
    QListWidget { border: 1px solid #e0e0e0; background: #fcfcfc; }
    QLineEdit, QTextEdit { border: 1px solid #b3e5fc; }
    """

def _get_executable_command():
    if getattr(sys, 'frozen', False):
        exe_path = sys.executable
        return f'"{exe_path}" "%1"'
    else:
        exe_path = os.path.abspath(sys.argv[0])
        python_exe = sys.executable
        return f'"{python_exe}" "{exe_path}" "%1"'

def parse_compatibility_v2(root):
    """
    Analiza compatibilidad según los tags: <Knosthalij>Windows</Knosthalij>, <Danenone>Linux</Danenone>, 
    <AlphaCube>Multiplataforma</AlphaCube>, y/o un bloque <platform> o <compatibility>.
    Devuelve diccionario con plataforma y status normalizado.
    """
    special_map = {
        "Knosthalij": "Windows",
        "Danenone": "Linux",
        "AlphaCube": "All",  # se asume multiplataforma
    }
    compat = {}
    # Prefer new tags
    for child in list(root):
        tag = child.tag
        text = (child.text or '').strip()
        if tag in special_map and text:
            value = text.lower()
            if 'windows' in value:
                compat[special_map[tag]] = 'Windows'
            elif 'linux' in value:
                compat[special_map[tag]] = 'Linux'
            elif 'multi' in value or 'all' in value or 'plataforma' in value:
                compat[special_map[tag]] = 'All'
            else:
                compat[special_map[tag]] = text
        elif tag.lower() == 'platform' and text:
            plv = text.lower()
            if 'windows' in plv:
                compat['Windows'] = 'Windows'
            elif 'linux' in plv:
                compat['Linux'] = 'Linux'
            elif 'multi' in plv or 'all' in plv or 'plataforma' in plv:
                compat['All'] = 'All'
            else:
                compat[text] = text

    # Try also <compatibility>
    block = root.find('compatibility')
    if block is not None:
        for child in block:
            tag = child.tag
            txt = (child.text or '').strip()
            if not txt:
                continue
            lv = txt.lower()
            if 'win' in lv:
                compat[tag] = 'Windows'
            elif 'linux' in lv:
                compat[tag] = 'Linux'
            elif 'multi' in lv or 'all' in lv or 'plataforma' in lv:
                compat[tag] = 'All'
            else:
                compat[tag] = txt
    return compat

def system_to_name():
    osys = platform.system()
    if osys == 'Windows':
        return 'Windows'
    if osys == 'Linux':
        return 'Linux'
    if osys == 'Darwin':
        return 'Mac'
    return osys

# ==============================================
# CLASE DEL INSTALADOR PEQUEÑO E INTELIGENTE
# ==============================================

class JerodinInstallerWizard(QWizard):
    def __init__(self, temp_dir, meta, package_path, parent=None):
        super().__init__(parent)
        self.temp_dir = temp_dir
        self.meta = meta
        self.package_path = package_path

        # Default install dir
        self.install_dir = os.path.join(
            get_documents_path(), 'Jerodin Apps',
            f"{self.meta['publisher']}.{self.meta['app']}.{self.meta['version']}"
        )
        self.theme_name = "default"
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle(f"{self.meta['title']} {self.meta['version']} - Instalar")
        self.setFixedSize(1024, 630)
        icon_path = os.path.join(self.temp_dir, 'app', 'app-icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setPage(0, WelcomePage(self))
        self.setPage(1, LicensePage(self))
        self.setPage(2, SettingsPage(self))
        self.setPage(3, InstallPage(self))

        self.setButtonText(QWizard.NextButton, "SIGUIENTE")
        self.setButtonText(QWizard.BackButton, "ATRÁS")
        self.setButtonText(QWizard.FinishButton, "FINALIZAR")
        self.setButtonText(QWizard.CancelButton, "CANCELAR")

        # Splash (opcional)
        self.show_splash_screen()

    def show_splash_screen(self):
        splash_path = os.path.join(self.temp_dir, 'assets', 'splash.png')
        if not os.path.exists(splash_path):
            splash_path = os.path.join('assets', 'splash.png')
        if os.path.exists(splash_path):
            self.splash = QWidget()
            self.splash.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.splash.setFixedSize(880, 490)
            layout = QVBoxLayout(self.splash)
            layout.setContentsMargins(0, 0, 0, 0)
            pixmap = QPixmap(splash_path)
            if not pixmap.isNull():
                label = QLabel()
                label.setPixmap(pixmap.scaled(880, 490, Qt.KeepAspectRatioByExpanding))
                layout.addWidget(label)
                self.splash.show()
                QTimer.singleShot(3000, self.splash.close)

class WelcomePage(QWizardPage):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setup_ui()

    def setup_ui(self):
        m = self.parent.meta
        self.setTitle(f"Instalando {m['title']}")
        self.setSubTitle(f"Versión {m['version']}")
        layout = QHBoxLayout(self)
        left_panel = QWidget()
        left_panel.setFixedWidth(320)
        left_layout = QVBoxLayout(left_panel)
        splash_path = os.path.join(self.parent.temp_dir, 'assets', 'splash_setup.png')
        if not os.path.exists(splash_path):
            splash_path = os.path.join('assets', 'splash_setup.png')
        if os.path.exists(splash_path):
            pixmap = QPixmap(splash_path)
            image_label = QLabel()
            image_label.setPixmap(pixmap.scaled(320, 520, Qt.KeepAspectRatio))
            left_layout.addWidget(image_label)
        left_layout.addStretch()
        layout.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        logo_path = os.path.join(self.parent.temp_dir, 'assets', 'product_logo.png')
        if not os.path.exists(logo_path):
            logo_path = os.path.join('assets', 'product_logo.png')
        if os.path.exists(logo_path):
            logo_label = QLabel()
            logo_label.setPixmap(QPixmap(logo_path).scaled(180, 180, Qt.KeepAspectRatio))
            logo_label.setAlignment(Qt.AlignCenter)
            right_layout.addWidget(logo_label)
        title_label = QLabel(f"{m['title']}")
        title_label.setObjectName("Title")
        title_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(title_label)
        version_label = QLabel(f"Versión: {m['version']}")
        version_label.setObjectName("SubTitle")
        version_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(version_label)

        # Información de publisher, rate, correlationid, author
        info_text = f"Proveedor: {m.get('publisher','')}<br>" \
                    f"ID: {m.get('correlationid','')[:12]}...<br>" if m.get('correlationid') else ""
        info_text += f"Licencia/RATE: {m.get('rate','')}<br>" if m.get('rate','') else ""
        info_text += f"Autor: {m.get('author','')}<br>" if m.get('author','') else ""
        if info_text:
            info_lbl = QLabel(info_text)
            info_lbl.setWordWrap(True)
            info_lbl.setAlignment(Qt.AlignCenter)
            right_layout.addWidget(info_lbl)

        # Compatibilidad detallada:
        compat = self.parent.meta.get('compatibility_obj', {})
        if compat:
            lines = [f"{k}: {v}" for k, v in compat.items()]
            compat_text = "Compatibilidad Plataforma:<br>" + "<br>".join(lines)
            compat_label = QLabel(compat_text)
            compat_label.setWordWrap(True)
            compat_label.setAlignment(Qt.AlignCenter)
            right_layout.addWidget(compat_label)
            compatible = self.parent.meta.get('compatible', True)
            color = "#21ad1c" if compatible else "#e30c0c"
            status = "Compatible" if compatible else "No compatible"
            status_label = QLabel(f"<b style='color:{color}'>{status} con el sistema actual</b>")
            status_label.setAlignment(Qt.AlignCenter)
            right_layout.addWidget(status_label)
        right_layout.addSpacing(7)
        desc_label = QLabel("Este asistente le guiará en la instalación. Puede elegir la carpeta y el tema.")
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(desc_label)
        right_layout.addStretch()
        layout.addWidget(right_panel)

class LicensePage(QWizardPage):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setup_ui()

    def setup_ui(self):
        self.setTitle("Acuerdo de Licencia")
        self.setSubTitle("Por favor revise los términos de la licencia antes de continuar.")

        layout = QVBoxLayout(self)
        license_path = os.path.join(self.parent.temp_dir, 'LICENSE')
        license_text = ""
        if os.path.exists(license_path):
            with open(license_path, 'r', encoding='utf-8') as f:
                license_text = f.read()
        else:
            license_text = "No se encontró archivo de licencia."
        self.license_edit = QTextEdit()
        self.license_edit.setPlainText(license_text)
        self.license_edit.setReadOnly(True)
        layout.addWidget(self.license_edit)
        self.accept_checkbox = QCheckBox("Acepto los términos del acuerdo de licencia")
        self.accept_checkbox.stateChanged.connect(self.on_license_accepted)
        layout.addWidget(self.accept_checkbox)
        self.registerField("license_accepted", self.accept_checkbox)

    def on_license_accepted(self, state):
        self.completeChanged.emit()

    def isComplete(self):
        return self.accept_checkbox.isChecked()

class SettingsPage(QWizardPage):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setup_ui()

    def setup_ui(self):
        self.setTitle("Configuración")
        self.setSubTitle("Elija carpeta y tema.")
        layout = QFormLayout(self)
        # Carpeta
        self.install_line = QLineEdit(self.parent.install_dir)
        browse_btn = QPushButton("Examinar...")
        browse_btn.clicked.connect(self.browse_install_dir)
        hbox = QHBoxLayout()
        hbox.addWidget(self.install_line)
        hbox.addWidget(browse_btn)
        wrapper = QWidget()
        wrapper.setLayout(hbox)
        layout.addRow("Carpeta de instalación:", wrapper)
        # Tema
        self.theme_combo = QComboBox()
        qss_locations = []
        for candidate in [
            os.path.join(self.parent.temp_dir, 'app', 'style.qss'),
            os.path.join(self.parent.temp_dir, 'assets', 'style.qss'),
            os.path.join(self.parent.temp_dir, 'style.qss'),
        ]:
            if os.path.isfile(candidate):
                qss_locations.append(candidate)
        if qss_locations:
            self.theme_combo.addItem("Paquete: personalizado", userData=qss_locations[0])
        else:
            self.theme_combo.addItem("Predeterminado", userData=None)
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)
        layout.addRow("Tema:", self.theme_combo)

        # Opción: asociar extensión (.iflapp)
        self.assoc_checkbox = QCheckBox("Asociar archivos .iflapp con este instalador (recomendado)")
        if platform.system() not in ("Windows", "Linux"):
            self.assoc_checkbox.setEnabled(False)
        layout.addRow(self.assoc_checkbox)

    def browse_install_dir(self):
        start = self.install_line.text() or get_documents_path()
        chosen = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de instalación", start)
        if chosen:
            self.install_line.setText(chosen)

    def on_theme_changed(self, idx):
        data = self.theme_combo.itemData(idx)
        if data:
            try:
                with open(data, 'r', encoding='utf-8') as f:
                    qss = f.read()
                    QApplication.instance().setStyleSheet(qss)
            except Exception:
                pass
        else:
            qss = load_qss_from_package(self.parent.temp_dir)
            QApplication.instance().setStyleSheet(qss)

    def validatePage(self):
        self.parent.install_dir = self.install_line.text() or self.parent.install_dir
        self.parent.theme_name = self.theme_combo.currentText()
        if self.assoc_checkbox.isChecked():
            if platform.system() == "Windows":
                associate_extensions_windows()
            elif platform.system() == "Linux":
                associate_extensions_unix()
        return True

class InstallPage(QWizardPage):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.installed = False
        self.setup_ui()

    def setup_ui(self):
        self.setTitle("Instalación")
        self.setSubTitle("La aplicación está siendo instalada en su sistema.")
        layout = QVBoxLayout(self)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.file_list = QListWidget()
        self.file_list.setAlternatingRowColors(True)
        layout.addWidget(self.file_list)

    def initializePage(self):
        super().initializePage()
        QTimer.singleShot(180, self.start_installation)

    def start_installation(self):
        self.setFinalPage(True)
        self.wizard().button(QWizard.BackButton).setEnabled(False)
        self.wizard().button(QWizard.CancelButton).setEnabled(False)
        base_dir = self.parent.install_dir
        try:
            os.makedirs(base_dir, exist_ok=True)
        except Exception as e:
            self.file_list.addItem(f"No se pudo crear el directorio: {str(e)}")
            self.progress_bar.setValue(100)
            self.installed = False
            return
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(lambda: self.update_progress(base_dir))
        self.progress_timer.start(100)

    def update_progress(self, base_dir):
        try:
            v = self.progress_bar.value()
            if v < 100:
                newv = min(v + 9, 100)
                self.progress_bar.setValue(newv)
                if newv % 27 == 0:
                    self.file_list.addItem(f"Progreso... {newv}%")
                if newv == 100:
                    try:
                        for item in os.listdir(self.parent.temp_dir):
                            src = os.path.join(self.parent.temp_dir, item)
                            dst = os.path.join(base_dir, item)
                            if os.path.isdir(src):
                                shutil.copytree(src, dst, dirs_exist_ok=True)
                            else:
                                shutil.copy2(src, dst)
                        generateWorkState(base_dir)
                        self.file_list.addItem("Instalación completada con éxito!")
                        self.installed = True
                        self.completeChanged.emit()
                        self.wizard().button(QWizard.FinishButton).setEnabled(True)
                    except Exception as e:
                        self.file_list.addItem(f"Error al copiar archivos: {str(e)}")
                        self.installed = False
                    finally:
                        self.progress_timer.stop()
        except Exception as e:
            self.file_list.addItem(f"Error inesperado: {str(e)}")
            try:
                self.progress_timer.stop()
            except Exception:
                pass

    def isComplete(self):
        return self.installed

# ==============================================
# FUNCIÓN PRINCIPAL
# ==============================================

def main():
    parser = argparse.ArgumentParser(description='Instalador Jerodin/AlphaCube - .iflapp')
    parser.add_argument('package', nargs='?', help='Ruta al paquete .iflapp')
    args = parser.parse_args()
    if not args.package:
        print("Uso: python Jerodinhandler.py <paquete>.iflapp")
        return
    package_path = args.package
    if not package_path.lower().endswith('.iflapp'):
        print("Error: este instalador acepta sólo paquetes con extensión .iflapp")
        sys.exit(2)
    if not os.path.isfile(package_path):
        print(f"Error: paquete no encontrado: {package_path}")
        sys.exit(2)

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Descomprimir
            with zipfile.ZipFile(package_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            # Buscar details.xml / app.xml
            details_path = os.path.join(temp_dir, 'details.xml')
            if not os.path.exists(details_path):
                for alt in ('app.xml', 'details/app.xml', 'details.xml'):
                    alt_path = os.path.join(temp_dir, alt)
                    if os.path.exists(alt_path):
                        details_path = alt_path
                        break
            if not os.path.exists(details_path):
                raise FileNotFoundError("Archivo details.xml (o app.xml) no encontrado en el paquete")

            tree = ET.parse(details_path)
            root = tree.getroot()
            # Nuevo parsing
            meta = {
                'publisher': root.findtext('publisher') or root.findtext('Author') or 'Unknown',
                'app': root.findtext('app') or root.findtext('id') or 'unknownapp',
                'title': root.findtext('name') or root.findtext('title') or 'Unknown Title',
                'version': root.findtext('version') or '0.0.0',
                'correlationid': root.findtext('correlationid') or '',
                'rate': root.findtext('rate') or '',
                'author': root.findtext('author') or root.findtext('Author') or '',
            }
            for key, value in list(meta.items())[:4]:
                if not value:
                    raise ValueError(f"Campo requerido faltante en details.xml: {key}")

            # Usar tags tipo Knosthalij, Danenone, AlphaCube, platform, o compatibility
            compat = parse_compatibility_v2(root)
            meta['compatibility_obj'] = compat
            # ¿Compatible?
            current_os = system_to_name()

            # Criterio: compatible si hay plataforma igual al sistema, o 'All'
            compatible = False
            if compat:
                # Si hay "All" o key igual al sistema.
                for plat, val in compat.items():
                    # plat o val debe coincidir con actual o ser "All"
                    if str(plat).lower() == current_os.lower() or str(val).lower() == current_os.lower() or val == "All":
                        compatible = True
                        break
            else:
                # Si no hay información de compatibilidad, suponer compatible
                compatible = True

            meta['compatible'] = compatible

            # Asociación automática de extensión
            if platform.system() == "Windows":
                if not is_extension_associated_windows():
                    associate_extensions_windows()
            elif platform.system() == "Linux":
                associate_extensions_unix()

            # Lanzar UI
            app = QApplication(sys.argv)
            app.setStyle('Fusion')
            qss = load_qss_from_package(temp_dir)
            app.setStyleSheet(qss)

            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(246, 253, 251))
            palette.setColor(QPalette.WindowText, QColor(10, 10, 10))
            palette.setColor(QPalette.Base, QColor(255, 255, 255))
            palette.setColor(QPalette.AlternateBase, QColor(239, 250, 246))
            palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 220))
            palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
            palette.setColor(QPalette.Text, QColor(10, 10, 10))
            palette.setColor(QPalette.Button, QColor(240, 240, 240))
            palette.setColor(QPalette.ButtonText, QColor(13, 13, 13))
            palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
            palette.setColor(QPalette.Highlight, QColor(76, 175, 80))
            palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
            app.setPalette(palette)

            if not compatible:
                QMessageBox.warning(None, "Compatibilidad", "Este paquete no parece estar hecho para su sistema operativo actual.\nPuede ocurrir un error o una ejecución incorrecta.")

            wizard = JerodinInstallerWizard(temp_dir, meta, package_path)
            wizard.show()
            sys.exit(app.exec_())

        except Exception as e:
            print(f"Error: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    main()
