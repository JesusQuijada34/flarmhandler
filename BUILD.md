# Build Instructions

## Compilar a Ejecutable (.exe)

### Requisitos
- Python 3.8+
- PyInstaller

### Instalación de PyInstaller
```bash
pip install pyinstaller
```

### Compilar
```bash
pyinstaller --onefile --windowed --name FlarmHandler --icon app/flarmpack.ico --add-data "assets;assets" --add-data "app;app" flarmhandler.py
```

### Resultado
El ejecutable se generará en la carpeta `dist/FlarmHandler.exe`

### Opciones de Compilación
- `--onefile`: Genera un solo archivo ejecutable
- `--windowed`: No muestra consola (aplicación GUI)
- `--name FlarmHandler`: Nombre del ejecutable
- `--icon app/flarmpack.ico`: Icono del ejecutable
- `--add-data "assets;assets"`: Incluye carpeta assets
- `--add-data "app;app"`: Incluye carpeta app

### Distribución
El archivo `FlarmHandler.exe` en la carpeta `dist` es completamente portable y puede distribuirse sin necesidad de instalar Python.
