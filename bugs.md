# 🤖 PLAN MAESTRO DE EJECUCIÓN: `packagemaker` & `flarmhandler`

Este documento actúa como la especificación técnica y hoja de ruta obligatoria para los agentes autónomos encargados de la refactorización, corrección de errores y despliegue de nuevas funcionalidades en los repositorios `JesusQuijada34/packagemaker` y `JesusQuijada34/flarmhandler`.

---

## 1. Protocolo Operativo del Agente (Git & Control de Estado)

1. **Sincronización Inicial:**
   - Si los repositorios `JesusQuijada34/packagemaker.git` y `JesusQuijada34/flarmhandler.git` no existen en el entorno local, clónalos.
   - Si ya existen, ejecuta `git pull` antes de iniciar cualquier lectura o modificación.
   - Analiza el historial de commits (especialmente commits previos relacionados con el renderizado de *splashes* integrados y detección de carga de UI) para comprender la arquitectura base.
2. **Flujo de Trabajo y Commits:**
   - **Prohibición estricta:** Trabaja y haz *push* directamente a la rama `main`. **NO** crees ramas secundarias ni Pull Requests sin consentimiento explícito del usuario.
   - **Comparación Post-Push:** Tras cada `git push`, compara el estado remoto con el anterior para documentar con precisión los cambios y generar entradas estructuradas para `CHANGELOG.md` o *Release Notes*.
   - **Actualización de Memoria (`AGENTS.md`):** Al completar cada tarea, márcala como completada (`[x]`), limpia tareas obsoletas y transfiere el conocimiento técnico adquirido, patrones de diseño y pasos de ejecución al archivo `AGENTS.md` de **cada** repositorio.
3. **Gestión de la Carpeta `.refs/` (Visión de Imágenes):**
   - **Regla para Manus AI / OpenHands / ChatGPT:** Si el agente posee capacidad de visión y ha procesado las imágenes en `.refs/`, **debe eliminar la carpeta `.refs/`** únicamente después de que el usuario haya verificado y aprobado la corrección del error y las mejoras de interfaz solicitadas.

---

## 2. Diagnóstico Visual: Análisis de Referencias (`{bug}` vs `{ref}`)

### `{bug}`: Estado Actual Defectuoso (`.refs/bug.png`)
* **Problemas de Renderizado y Ventana:** La barra de título presenta corrupción gráfica severa (artefactos/ruido de píxeles) sobre los botones de minimizar, maximizar y cerrar.
* **Jerarquía y Layout Roto:** La interfaz luce desorganizada y anticuada. El icono de la aplicación (*Suprr*) es un recuadro gris vacío (fallo en la carga de assets) y se muestra incorrectamente bajo la plataforma `AlphaCube` independientemente de la arquitectura real del paquete.
* **Distribución de Controles:** Los botones de acción (`INSTALAR` y `COMPARTIR`) están posicionados en la zona media-superior derecha con estilos planos antiguos (naranja sólido y borde gris), dejando un vacío blanco desproporcionado a la izquierda bajo la sección *"Acerca de esta app"*, mientras que a la derecha se ubica un bloque negro sólido para *"Estado de instalación"*.

### `{ref}`: Objetivo Visual y Funcional (`.refs/ref (1).png` - `ref (4).png`)
El nuevo instalador debe replicar fielmente la arquitectura visual y funcional del **Instalador de Aplicaciones UWP (Windows App Installer)**:
* **Cabecera e Iconografía (`ref (1).png`):**
  * Título principal en tipografía grande y limpia (ej. *"¿Instalar [App]?"* o *"[App] ya está instalado"*).
  * Metadatos organizados inmediatamente debajo en texto secundario: *Editor*, *Versión* y ruta de *Origen*.
  * En la esquina superior derecha, un contenedor cuadrado (`~96x96 px`) que muestra el icono de la aplicación. Si el icono posee fondo transparente, **debe rellenarse dinámicamente con el color de acento del sistema operativo** (ej. azul sistema en `ref (1)` y `ref (2)`).
* **Cuerpo y Capacidades:**
  * Sección *"Funcionalidades:"* con lista de permisos/capacidades en viñetas limpias y enlace *"Más"*.
* **Panel de Estado / Alertas (`ref (1).png`, `ref (2).png`, `ref (4).png`):**
  * Un contenedor rectangular ancho en la zona inferior con un borde resaltado en el **color de acento del sistema operativo** (`2px solid AccentColor`).
  * Muestra mensajes dinámicos de estado o validación: advertencias de versión instalada, requerimiento de privilegios de administrador (`ref (2).png`) o errores de validación de certificado/firma (`ref (4).png`).
* **Geometría de Botones UWP y Pie de Página:**
  * Botones rectangulares con esquinas ligeramente suavizadas (`border-radius: 2px` a `4px`), alineados en la esquina inferior derecha.
  * Botón primario con fondo sólido en el color de acento del sistema y texto blanco (*"Instalar"*, *"Iniciar"*); botón secundario con fondo gris neutro o estado deshabilitado cuando faltan permisos/certificados (*"Reiniciar como administrador"* con icono de escudo en `ref (2).png`, *"Cancelar"*).
  * Icono informativo circular (`i`) en la esquina inferior izquierda (`ref (1)` a `ref (4)`).
* **Pantalla de Carga (`ref (3).png`):**
  * Contenedor limpio que muestra un anillo de progreso giratorio (*spinner* estilo Fluent/UWP) en el color de acento del sistema sobre el texto centrado *"Cargando..."* antes de revelar los datos del paquete.

---

## 3. Lista de Tareas Técnicas (Backlog de Ejecución)

### Fase 1: Corrección de Bugs Críticos del Instalador (`flarmhandler`)
- [x] **Permisos de Descompresión:** Corregir el motor de extracción/instalación para que no aplique permisos restrictivos en disco. Garantizar permisos estándar de lectura y escritura (`chmod` / ACLs de Windows) de forma automática tras descomprimir.
- [x] **Detección de Plataforma y Assets:** Corregir el parser de metadatos para que identifique la arquitectura/plataforma real del paquete (eliminando el hardcoding erróneo a `AlphaCube`), cargue correctamente los iconos y cree los accesos directos en el sistema.
- [x] **Actualización de Hojas de Estilo (QSS):** Actualizar los archivos `.qss` tanto en `packagemaker` como en `flarmhandler` para implementar la geometría UWP, controles dinámicos con el color de acento del SO y estados de botones (activo, hover, deshabilitado).

### Fase 2: Fondos Dinámicos, Mica y Arquitectura de Splashes
- [x] **Banner Borroso y Efecto Mica:**
  - Sustituir el fondo sólido de la ventana por un banner superior difuminado (*blur*) utilizando `assets/splash.png` como contenedor de cabecera, aplicando efecto **Mica** en el resto inferior de la ventana.
  - **Detección de Orientación de Pantalla:**
    - *Horizontal* (`ancho > alto`): Usar `assets/splash.png` difuminado.
    - *Vertical* (`ancho < alto`): Mostrar `assets/splash_setup.png` centrado y difuminado.
    - *Sin assets disponibles:* Aplicar efecto Mica completo en toda la ventana.
- [x] **Sistema de Splash Dinámico al Iniciar el Instalador:**
  - Adoptar el icono del paquete como icono de aplicación y de ventana.
  - **Splash integrado sin assets (patrón `IntegratedSplash` de `packagemaker`,
    commit `f15bfde`):** una ventana del **mismo tamaño que la ventana
    principal**, con el **fondo del color de acento del SO** (leído del registro
    de Windows en Windows; `gsettings` en GNOME) y el **icono del paquete**
    (`app/app-icon.ico`) **centrado**. No se generan ni recortan assets.
  - **Transición Suave:** detectar el momento exacto en que la ventana principal
    se ha dibujado (primer `paintEvent`) para ejecutar el *fade-out* del splash
    y revelar la interfaz; un temporizador actúa de red de seguridad.
- [x] **Centralización de QSS (`source/qss/{qtcontrolid}.qss`):** un fichero por
  control Qt (`qwidget`, `qpushbutton`, `qlabel`, `qlineedit`, `qscrollbar`,
  `qmessagebox`, `qprogressbar`) como única fuente de estilos. `lib/qss_loader.py`
  (mismo contrato que packagemaker) los lee y ensambla; `build_global_qss()`
  inyecta el acento del SO con marcadores `__ACCENT__`/`__ACCENT_HOVER__`/
  `__ACCENT_PRESSED__`/`__ACCENT_SOFT__`. Reutilizable en la Fase 3.

### Fase 3: Librería Global de Splashes e Inyección Bootloader (`packagemaker`)
- [x] **Librería Compartida (`lib/`):** `lib/splash_bootloader.py` es autocontenido
  (sólo stdlib + PyQt6 opcional) y `lib/bootloader_injection.copy_splash_library()`
  lo copia a `lib/` del proyecto junto a un `__init__.py`, al compilar cada guion.
- [x] **Inyección de Código tipo Bootloader (AST / Parser de Scripts):**
  `lib/bootloader_injection.py` analiza el guion con `ast` e inyecta, respetando
  la indentación, la cabecera (post-imports) y el cierre (post-UI init: antes de
  `app.exec()`/`exec_()` o tras el primer `.show()`). La copia inyectada
  (`<guion>_pmboot.py`) se compila y se borra al terminar; el original no se toca.
  Cableado en `BuildThread._compile_binary` y `iflapp_ide.compile_project`.
  Detecta `PyQt6` y `leviathan_ui`; arquitectura extensible vía `FRAMEWORK_MODULES`.

---

## 4. Criterios de Aceptación Final
1. La ventana de instalación se renderiza sin artefactos gráficos en la barra de título y replica la estructura UWP de `.refs/ref (1).png` a `ref (4).png`.
2. Los paquetes se descomprimen con permisos de lectura/escritura funcionales, mostrando su plataforma real, icono (con fondo de acento si es transparente) y generando sus accesos directos.
3. El motor de *bootloader* de splash se inyecta limpiamente en proyectos `iflapp` compilados, logrando una transición fluida estilo UWP.
4. Todos los cambios están sincronizados en `main` de ambos repositorios, con `AGENTS.md` actualizado y `.refs/` eliminada tras la aprobación del usuario.