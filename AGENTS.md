# AGENTS.md — FlArm Handler (`flarmhandler`)

Identidad: `influent.flarmhandler.v1.0-26.08-21.56` (JesusQuijada34).
Repo: `https://github.com/JesusQuijada34/flarmhandler.git`, rama de trabajo `main`.

## Flujo de trabajo
- **Nunca crear ramas**: se trabaja y se sube directamente a `main`.
- Ejecutar la suite: `QT_QPA_PLATFORM=offscreen python -m pytest tests/ -q`.
- Análisis estático: `python -m pyflakes flarmhandler.py` debe salir limpio.
- Compilar sin arrancar la GUI: `python -m py_compile flarmhandler.py`.
- Comprobación de seguridad de extracción: `python static_smoke_test.py`
  (AST que exige `_safe_extract_member`, `extract_archive`, `issym()` y ausencia
  de `extractall` sin filtrar).

## Arquitectura
- `flarmhandler.py` es un único módulo PyQt6 (~94 KB) con la GUI y la lógica de
  instalación. Contiene:
  - `InstallWindow(QtWidgets.QWidget)` — ventana principal del instalador.
  - `InstallWorker(QtCore.QRunnable)` — build/instalación en hilo aparte.
  - `CustomTitleBar` / `TitleBtn` / `TitleLabel` — barra de título propia (32 px).
  - `BlurredBanner` — cabecera con `assets/splash.png` (recorte central o fondo
    difuminado si la imagen es más corta).
- `lib/` porta el ecosistema Fluthin: `iflapp_format` (contenedor v2),
  `asksome_format`, `mexf_*`, `native_shell`, `package_shell`, `safe_zip`.
  `HAS_PACKAGE_LIBS` es `False` si faltan; el handler degrada sin ellos.
- `lib/splash_screen.py` — splash dinámico estilo UWP (Fase 2). Clasifica la
  pantalla en `landscape`/`portrait`/`square`, busca los assets
  `{app}-landscapeSplash.png`/`{app}-portraitSplash.png` (o los genéricos
  `splash.png`/`splash_setup.png`), rellena su transparencia con el acento del
  SO y, si no hay ninguno, genera un marco transparente con el icono centrado a
  `512x512`. `SplashWindow.finish_when_ready(target)` desvanece el splash en el
  primer `paintEvent` de la ventana (con temporizador de seguridad). Se mantiene
  fuera de `flarmhandler.py` porque la Fase 3 lo copia a la `lib/` de los
  proyectos `iflapp` como *bootloader*.
- `InstallWindow._apply_banner_asset(assets_dir, has_assets)` elige el splash de
  cabecera por orientación; sin assets aplica **Mica** (`_apply_mica`: propiedad
  `backdrop="mica"` + `WipeWindow` de `leviathan_ui`, ambos opcionales). El flujo
  online prueba los mismos candidatos vía GitHub raw y cae a Mica si no hay.
- `read_package_identity()` lee la cabecera sin descifrar y devuelve las mismas
  claves que `parse_details_xml` (`name`, `publisher`, `app`, `version`,
  `platform`, `author`), así el flujo no distingue v2 / asksome / ZIP.

## Sistema de diseño (UWP / Windows App Installer)
- El instalador replica el **Windows App Installer**: título grande
  («¿Instalar X?» / «X ya está instalado»), metadatos Editor/Versión/Origen,
  icono cuadrado de 96×96 en la esquina superior derecha, panel de estado con
  borde de acento y acciones abajo a la derecha con un icono informativo `i`.
- **El acento lo aporta el SO, no hay color fijo**: `system_accent_color()` lee
  `AccentColor` de DWM en Windows y `gsettings ... accent-color` en GNOME; cae a
  `DEFAULT_ACCENT` (`#0078D4`) si no puede. `shade_color()` oscurece y
  `tint_color()` mezcla hacia blanco (multiplicar saturaba a cian puro).
- `GLOBAL_QSS` es una **plantilla** con placeholders `{accent}`, `{accent_hover}`,
  `{accent_pressed}` y `{accent_soft}`. Se resuelve con `build_global_qss()`, que
  usa `str.replace` (no `str.format`) porque la hoja contiene llaves CSS que
  `format` interpretaría como campos. `main()` llama a `build_global_qss(accent)`.
- `render_app_icon(data, size, accent)` pinta el icono del paquete sobre un
  cuadrado del color de acento (estilo UWP). Si el icono es transparente o no
  hay, el acento se ve detrás. Sin icono válido, `_set_icon_pixmap` muestra las
  iniciales de la app sobre el acento en lugar de un recuadro gris vacío.

## Trampas conocidas
- **Corrupción de la titlebar**: en `CustomTitleBar.create_btn` el `QPixmap(46,
  32)` **debe** rellenarse con `pixmap.fill(QtCore.Qt.GlobalColor.transparent)`
  antes de pintar y activar el antialiasing. Sin el `fill` los píxeles quedan sin
  inicializar y aparecen artefactos sobre los botones de minimizar/maximizar/cerrar.
- **Permisos tras extraer**: `ensure_executable_bits()` sólo marca `+x`. Para
  normalizar lectura/escritura hay `normalize_install_permissions()` (directorios
  `0o755`, ficheros `0o644` conservando el bit `+x`; en Windows limpia el
  atributo de sólo lectura). Se llama **antes** de `ensure_executable_bits` en
  los dos flujos de instalación (offline y online). Sin esto, un ZIP/TAR con
  modo `000` deja la app instalada sin poder leer sus recursos.
- **`BlurredBanner`**: las asignaciones `scaled_pix` / `cover_pix` estuvieron
  comentadas pero el código las seguía usando → `NameError` al mostrar el banner.
  Restauradas con los enums de Qt6 (`AspectRatioMode.*`, `TransformationMode.*`).
  El banner se oculta (`setVisible(False)`) hasta que haya un splash real, para no
  dejar el hueco blanco de 220 px.
- En PyQt6 los enums son con ámbito: `QtCore.Qt.AlignmentFlag.AlignCenter`,
  `QtCore.Qt.AspectRatioMode.KeepAspectRatio`, etc. El estilo antiguo
  (`QtCore.Qt.AlignCenter`) falla en tiempo de ejecución.
- `QtSvg` y `pythoncom` se importan por **efecto lateral** (registro del plugin
  SVG en QtGui y sonda de pywin32); se referencian (`_SVG_PLUGIN`,
  `_PYWIN32_PROBE`) para que pyflakes no los marque como muertos sin perder el
  efecto.
- Los tests de UI necesitan `PyQt6` y las libs de sistema (`libegl1`, `libgl1`,
  `libxkbcommon-x11-0`) y `QT_QPA_PLATFORM=offscreen`. Conserva una referencia a
  la `QApplication` (patrón `_ensure_app`) o Qt aborta el proceso.

## Plan maestro
`bugs.md` es la hoja de ruta de 3 fases. Fase 1 (bugs críticos del instalador)
completada: permisos, detección de plataforma/assets y QSS UWP. Fase 2 (banner
borroso por orientación, Mica y splash dinámico con fade-out) completada.
Fase 3 (librería global de splashes e inyección *bootloader* en `packagemaker`)
pendiente.
