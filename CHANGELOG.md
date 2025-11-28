# Changelog

Todas las mejoras y cambios notables en este proyecto serán documentados en este archivo.

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
