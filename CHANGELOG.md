# Changelog

Todas las mejoras y cambios notables en este proyecto serán documentados en este archivo.

## [v2.0.0] - 2025-11-28

### ✨ Añadido
- **Compatibilidad de Plataforma**:
  - Verificación automática de compatibilidad Windows (Knosthalij) vs Linux (Danenone).
  - Bloqueo de instalación de paquetes incompatibles con mensajes claros.
  - Función `check_platform_compatibility()` para validación.
- **Detección de Paquetes Instalados**:
  - Nueva función `find_installed_package()` para búsqueda exacta por nombre de carpeta.
  - Verificación automática al abrir paquetes locales o remotos.
  - Muestra botones "Ejecutar" y "Desinstalar" cuando el paquete ya está instalado.
- **Compartir Mejorado para Paquetes Locales**:
  - Extracción del campo `<author>` desde `details.xml`.
  - Generación de URLs de GitHub usando `author` y `app` para paquetes locales.
  - Botón "Compartir" habilitado para paquetes `.iflapp`.
- **Carga de Recursos Mejorada**:
  - Extracción automática de `details.xml`, splash e iconos desde paquetes `.iflapp`.
  - Fallback a recursos remotos si los locales no están disponibles.
  - Métodos `load_local_package_metadata()` y `load_local_assets_to_ui()`.

### ⚡ Mejorado
- **Formato de Carpetas de Instalación**:
  - Nuevo formato: `{publisher}.{app}.{version}-{platform}`.
  - Ejemplo: `Influent.packagemaker.v1.2-25.11-34.55-Knosthalij`.
  - Función `create_documents_app_folder()` actualizada con nuevos parámetros.
- **Parseo de XML**:
  - Reemplazado parseo basado en regex con `xml.etree.ElementTree`.
  - Manejo correcto de etiquetas XML anidadas.
  - Extracción de campos: `name`, `publisher`, `app`, `version`, `platform`, `author`.
  - Fallback a regex para XML malformado.
- **Metadatos de Paquetes**:
  - Almacenamiento de `meta_publisher`, `meta_app`, `meta_version`, `meta_platform`, `meta_author`.
  - Uso de metadatos para nombrado de carpetas y compartir.

### 🐛 Corregido
- **Parseo de XML**: Corregido bug donde las etiquetas XML se incluían en los valores extraídos.
- **Detección de Instalación**: Ahora usa coincidencia exacta de nombre de carpeta en lugar de coincidencia parcial.
- **Compartir**: URLs de GitHub generadas correctamente para paquetes locales usando información del autor.

## [Unreleased] - 2025-11-28

### ✨ Añadido
- **Soporte de Paquetes Offline (.iflapp)**:
  - Instalación directa desde archivos locales `.iflapp`.
  - Asociación de archivos automática con icono personalizado.
  - Extracción e instalación en `Documents/FLARM Apps`.
- **Integridad del Sistema**:
  - Verificación automática de modo Administrador al iniciar.
  - Comprobación y reparación de integridad del registro (protocolo y extensión).
  - **Reinicio Automático**: Reinicio del sistema tras aplicar correcciones en el registro.
- **Interfaz Full QSS**: Rediseño completo con estética moderna (Roboto, botones estilo Play Store).
- **Barra de Título Personalizada**: Estilo Windows 11 con botones de control (Minimizar, Maximizar, Cerrar) integrados.
- **Soporte Markdown**: Visualización renderizada de las descripciones de los paquetes (README.md) usando `markdown` y `QWebEngineView`.
- **Verificación de Registro**:
  - Detección automática de problemas con el protocolo `flarmstore://`.
  - Intento automático de reparación solicitando permisos de Administrador si es necesario.
- **Barra de Progreso**: Visualización del progreso de descarga en tiempo real.

### ⚡ Mejorado
- **Carga de Assets**:
  - Los iconos y banners se cargan dinámicamente desde el repositorio de GitHub del paquete.
  - Fallback a assets locales si la carga remota falla.
- **Generación de Enlaces**:
  - Corrección en la lógica de "Compartir" para generar enlaces válidos `flarmstore://`.
  - Copiado automático al portapapeles.
- **Manejo de Errores**: Mensajes más claros y opciones de recuperación (ej. abrir Releases en navegador si falla la instalación).

### 🐛 Corregido
- Validación de URLs para evitar duplicación de esquemas.
- Problemas de permisos al escribir en el registro de Windows.
