# Fluthin Armadillo Handler (FlArm Handler)

**Identidad del paquete:** `influent.flarmhandler.v1.0-26.08-21.56`
**Autor:** `JesusQuijada34`
**Plataforma:** `AlphaCube`
**Descripción:** Estructura reparada por MoonFix

## Estructura PackageMaker 3.2.7

Este repositorio fue normalizado mediante **MoonFix**, usando la estructura de PackageMaker 3.2.7. El paquete público debe conservar `details.xml`, `version.res`, `autorun`, `autorun.bat`, `.storedetail`, `updater.py`, `config/settings.json`, los marcadores `.container` y los archivos de documentación correspondientes. El publisher oficial es `influent` y la versión pública no contiene sufijo de plataforma.

## Instalación y ejecución

Instala las dependencias declaradas en `lib/requirements.txt` cuando exista y ejecuta el entrypoint real del proyecto. En Linux, los comandos privilegiados son específicos de Danenone y no deben trasladarse a Windows. En proyectos AlphaCube, la validación Windows debe realizarse con el `buildthis` oficial de PackageMaker.

## Validación

La fuente debe pasar compilación sintáctica, pruebas funcionales disponibles, comprobación de identidad XML, protección contra traversal en ZIP y llamadas seguras a subprocess. Los artefactos `.iflapp` deben ser generados por PackageMaker; los paquetes Debian deben usar el nombre canónico `influent.flarmhandler.v1.0-26.08-21.56_ARCH.deb`.

## Release

El tag y el título del release deben ser exactamente `v1.0-26.08-21.56`. Los assets deben usar el nombre canónico del paquete y una extensión objetiva. No se permite publicar un release AlphaCube que contenga únicamente el build Linux.

## Referencia original

# FlarmHandler

**FlarmHandler** es el gestor de paquetes y protocolo oficial para el ecosistema Flarm. Permite instalar aplicaciones desde repositorios GitHub utilizando enlaces `flarmstore://`.

## 🚀 Características

- **Protocolo `flarmstore://`**: Abre e instala paquetes directamente desde el navegador o enlaces compartidos.
- **Paquetes Offline (`.iflapp`)**:
  - Soporte para instalación sin conexión mediante archivos `.iflapp`.
  - Asociación de archivos nativa con icono personalizado.
  - Instalación automática con doble clic.
  - Extracción automática de metadatos y recursos (splash, iconos) desde el paquete.
- **Compatibilidad de Plataforma**:
  - Verificación automática de compatibilidad Windows/Linux.
  - Bloqueo de instalación de paquetes incompatibles (Danenone en Windows, Knosthalij en Linux).
- **Detección de Paquetes Instalados**:
  - Verifica automáticamente si un paquete ya está instalado.
  - Muestra botones "Ejecutar", "Instalar" y "Desinstalar" según corresponda.
  - Funciona tanto para paquetes locales como remotos.
- **Interfaz Moderna**:
  - Estilo visual inspirado en **Play Store** y **GitHub**.
  - **Modo Oscuro/Claro** automático (basado en QSS).
  - Barra de título personalizada estilo **Windows 11**.
- **Verificación Inteligente**:
  - Comprobación automática de claves de registro y asociaciones de archivo.
  - Auto-reparación con elevación de privilegios (Administrador) si es necesario.
  - **Reinicio Automático** (Opcional) para aplicar cambios críticos del sistema si es necesario.
- **Soporte Multimedia**:
  - Visualización de `README.md` con soporte **Markdown** (imágenes, enlaces, código).
  - Carga dinámica de iconos y banners desde el repositorio remoto o paquete local.
- **Gestión de Instalación**:
  - Descarga, extracción e instalación automatizada.
  - Creación de accesos directos en el Escritorio.
  - Barra de progreso real.
  - Formato de carpetas: `{publisher}-{app}-{version}-{platform}`
- **Compartir Mejorado**:
  - Genera enlaces cortos con is.gd para paquetes remotos y locales.
  - Para paquetes locales, extrae información del autor desde el XML.

## 🛠️ Instalación y Uso

### Requisitos
- Python 3.8+
- PyQt5
- Requests
- Markdown (opcional, para mejor visualización)

### Ejecución Manual
```bash
python flarmhandler.py
```
O para abrir un paquete específico:
```bash
python flarmhandler.py flarmstore://usuario.repositorio
```

## 📦 Estructura de Enlaces
El formato de los enlaces es:
`flarmstore://<usuario_github>.<nombre_repositorio>`

Ejemplo:
`flarmstore://JesusQuijada34.flarmhandler`

## 🎨 Personalización
El gestor busca recursos locales en la carpeta `assets/` para su propia interfaz:
- `assets/splash_setup.png`: Imagen vertical para el lanzador.
- `assets/splash.png`: Banner por defecto.
- `assets/product_logo.png`: Icono de la aplicación.

Si no se encuentran, utiliza fallbacks o intenta cargar los del repositorio remoto.

## 📄 Licencia
Este proyecto está bajo la licencia MIT.
