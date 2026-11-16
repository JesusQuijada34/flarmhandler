# Changelog

## Sin publicar — Fase 1 del plan `bugs.md`

Corrección de los bugs críticos del instalador (Fase 1):

- **Titlebar sin artefactos:** `CustomTitleBar.create_btn` rellena el `QPixmap`
  con transparencia antes de pintar y activa el antialiasing, eliminando el ruido
  gráfico sobre los botones de minimizar/maximizar/cerrar.
- **Permisos de descompresión:** nueva `normalize_install_permissions()` que deja
  el árbol instalado con permisos funcionales (directorios `0o755`, ficheros
  `0o644` conservando `+x`; en Windows limpia el atributo de sólo lectura). Se
  aplica antes de `ensure_executable_bits()` en los flujos offline y online.
- **Plataforma e iconos:** el icono del paquete se pinta sobre un cuadrado del
  color de acento del SO (`render_app_icon`); sin icono válido se muestran las
  iniciales. Se eliminó el recuadro gris vacío.
- **Acento dinámico del SO:** `system_accent_color()` (DWM en Windows, `gsettings`
  en GNOME, con respaldo `#0078D4`); `GLOBAL_QSS` pasa a plantilla resuelta por
  `build_global_qss()`.
- **Geometría UWP:** cabecera con título grande y metadatos Editor/Versión/Origen,
  panel de estado con borde de acento, botones primario/secundario/peligro y pie
  con icono informativo.
- **`BlurredBanner` reparado:** restauradas `scaled_pix`/`cover_pix` (antes
  `NameError`) y oculto hasta que exista un splash real.

## v1.0-26.08-21.56

- Identidad normalizada: publisher `influent` y author `JesusQuijada34`.
- Versión pública normalizada sin sufijo de plataforma.
- MoonFix aplicado con estructura PackageMaker 3.2.7.
- Documentación y archivos estructurales verificados.
