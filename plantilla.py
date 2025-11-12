# influent_installer.py
import sys, os, zipfile, tempfile, shutil, xml.etree.ElementTree as ET
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import Qt

def get_documents_path():
    if os.name == "nt" or sys.platform.startswith("win"):
        from ctypes import windll, create_unicode_buffer
        buf = create_unicode_buffer(260)
        windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)  # CSIDL_PERSONAL = 5
        return os.path.join(buf.value, "Flatr Apps")
    else:
        return os.path.join(os.path.expanduser("~/Documentos"), "Flatr Apps")

def extract_package(package_path):
    temp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(package_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)
    return temp_dir

def parse_details(details_path):
    tree = ET.parse(details_path)
    root = tree.getroot()
    return {
        "publisher": root.findtext("publisher", "Unknown"),
        "app": root.findtext("app", "Unnamed"),
        "title": root.findtext("name", "Untitled"),
        "version": root.findtext("version", "?")
    }

def install_package(temp_dir, metadata):
    target_dir = os.path.join(get_documents_path(), f"{metadata['publisher']}.{metadata['app']}.{metadata['version']}")
    os.makedirs(target_dir, exist_ok=True)
    for item in os.listdir(temp_dir):
        s = os.path.join(temp_dir, item)
        d = os.path.join(target_dir, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)

    # Windows shortcut logic
    if os.name == "nt" or sys.platform.startswith("win"):
        script_path = os.path.join(target_dir, f"{metadata['app']}.py")
        if not os.path.exists(script_path):
            with open(script_path, "w", encoding="utf-8") as f:
                f.write("# Entry point for the app\n")

    return target_dir

class InstallerWindow(QWidget):
    def __init__(self, package_path=None):
        super().__init__()
        self.setWindowTitle("Influent Installer")
        self.setFixedSize(1024, 600)
        self.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                border-radius: 5px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #005A9E;
            }
        """)
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)

        self.left_panel = QLabel()
        splash_path = "assets/splash_setup.png" if os.path.exists("assets/splash_setup.png") else "assets/splash.png"
        if os.path.exists(splash_path):
            pixmap = QPixmap(splash_path).scaled(256, 600, Qt.KeepAspectRatioByExpanding)
            self.left_panel.setPixmap(pixmap)
        self.layout.addWidget(self.left_panel)

        self.right_panel = QVBoxLayout()
        self.layout.addLayout(self.right_panel)

        self.title_label = QLabel("Influent Package Installer")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.right_panel.addWidget(self.title_label)

        self.info_label = QLabel("Ready to install your package.")
        self.right_panel.addWidget(self.info_label)

        self.license_view = QTextEdit()
        self.license_view.setReadOnly(True)
        self.right_panel.addWidget(self.license_view)

        self.accept_button = QPushButton("Accept License and Install")
        self.accept_button.clicked.connect(self.install)
        self.right_panel.addWidget(self.accept_button)

        if package_path:
            self.load_package(package_path)

    def load_package(self, path):
        temp_dir = extract_package(path)
        details_path = os.path.join(temp_dir, "details.xml")
        if not os.path.exists(details_path):
            self.info_label.setText("Invalid package: details.xml missing.")
            return
        self.metadata = parse_details(details_path)
        license_path = os.path.join(temp_dir, "LICENSE")
        if os.path.exists(license_path):
            with open(license_path, "r", encoding="utf-8") as f:
                self.license_view.setText(f.read())
        icon_path = os.path.join(temp_dir, "app", "app-icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.temp_dir = temp_dir
        self.info_label.setText(f"Installing {self.metadata['publisher']} {self.metadata['title']} {self.metadata['version']}")

    def install(self):
        install_package(self.temp_dir, self.metadata)
        self.info_label.setText("Installation complete.")
        self.accept_button.setEnabled(False)

def associate_extensions_windows():
    import winreg
    exe_path = os.path.abspath(__file__)
    extensions = [".iflapp", ".iflappb"]
    for ext in extensions:
        try:
            with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, ext) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "InfluentInstaller")
            with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, "InfluentInstaller\\shell\\open\\command") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, f'"{exe_path}" "%1"')
        except Exception as e:
            print(f"Failed to associate {ext}:", e)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    if len(sys.argv) > 1:
        window = InstallerWindow(sys.argv[1])
        window.show()
        sys.exit(app.exec_())
    else:
        if os.name == "nt":
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ".iflapp") as key:
                    val, _ = winreg.QueryValueEx(key, "")
                    if val != "InfluentInstaller":
                        associate_extensions_windows()
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ".iflappb") as key:
                    val, _ = winreg.QueryValueEx(key, "")
                    if val != "InfluentInstaller":
                        associate_extensions_windows()
            except FileNotFoundError:
                associate_extensions_windows()
        sys.exit(0)
