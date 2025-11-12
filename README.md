# Influent Handler GUI/CLI para paquetes Flarm-Windows
<div align="center">
   <img src="assets/splash.png" alt="Handler Prev" width="50%"/>
</div>
Mejoré el código para que tenga un asistente de 3 páginas con mejor diseño, efectos visuales y manejo de imágenes como se solicita. Aquí está la versión mejorada:
### Mejoras realizadas:

1. **Asistente de 3 páginas**:
    - Página de bienvenida con imagen lateral y logo del producto
    - Página de licencia con checkbox de aceptación
    - Página de instalación con barra de progreso y lista de archivos

2. **Splash screen**:
    - Muestra una imagen de bienvenida durante 5 segundos al inicio
    - Soporta imágenes personalizadas o predeterminadas

3. **Diseño mejorado**:
    - Estilo CSS personalizado para botones con efectos hover y pressed
    - Paleta de colores consistente
    - Diseño responsivo con paneles laterales

4. **Experiencia de instalación**:
    - Barra de progreso animada
    - Lista de archivos mostrando el progreso
    - Validación de pasos completos

5. **Compatibilidad multiplataforma**:
    - Mantiene la funcionalidad de asociación de archivos en Windows
    - Funciona en Linux y otros sistemas operativos

6. **Manejo de recursos**:
    - Busca imágenes en el paquete primero, luego en assets locales
    - Manejo elegante cuando faltan recursos

El código ahora proporciona una experiencia de instalación más profesional y pulida, con mejoras visuales y de usabilidad significativas.
---
# Uso en la línea de comandos:
## **Implementar un paquete Danenone Packaged o Bundled (.iflapp/b)**
1. En Windows:
    - Abre la actividad para ejecutar procesos pulsando `WIN + R` y escribe `cmd` o ejecuta como administrador si quieres implementar el reconocimiento de paquetes al sistema para no hacer el resto
    - En la ventana del `CMD` navega hasta el paquete desolado (descomprimido) y usando `cd <nombre de carpeta>`
    - Con Python instalado, escribe `autorun.bat` para instalar dependencias y asegurar el lanzamiento de la app junto con las implementaciones al registro en los paquetes Flarm
    - Normalmente se cierra la app cuando no hay argumentos, al menos que edites el bat incluído en el paquete
    - Escribimos `python flarmhandler.py/exe <paquete>.iflapp/b` (variaciones de paquetes en las últimas atualizaciones de sistema y plataforma)
    - Ahora se presenta un splash si se encuentra disponible en la app (OJO: No todos los paquetes incluyen assets de instalación, a excepción de los Bundle en el 2026 que incluíran actividades xml en vez de `.py` (estilo android para facilitar dudas)
    - Sigue los pasos hasta la página de instalación (no antes aceptar los términos de Licencia) y espera a que llegue a 100%, normalmente tarda dependiendo el contenido dentro del paquete
    - Después de la instalación, debes de ejecutar el entorno Danenone para ejecutar la app con su actividad, si está compilado en esta versión no mostrará el paquete en el escritorio Danenone
    - Ejecuta la app y disfruta del contenido, si quieres ver los assets de cada app debes de ejecutar cada paquete manual, ya que se ha restringido para evitar fraudes dentro de la plataforma
2. En Linux:
    - Abre la terminal en `SUPER + ALT + T` (Dependiendo de que SO ejecutas)
    - En la terminal navega hasta el paquete desolado usando `cd <nombre de la carpeta>`
    - Si tienes python preinstalado o instalado escribe `chmod +x ./autourn && ./autorun && python/3 flarmhandler/.py <ruta del pack>.iflapp/b`
    - Ahora sigue el proceso de instalación y navega hasta tu carpeta documentos, abre una terminal en la carpeta del paquete y ejecuta `chmod +x ./autorun`
    - Disfruta del entorno usando DaneDesk, para aprender a usarlo, lee nuestro README para mayor uso
---

# Wiki
Desarrollaremos una wiki para que puedas aprender usos básicos sobre este paquete pronto sea posible, asi como usos de la Flarm Store en instalación de paquetes. Y también ![ICON](app/app-icon.ico) ![IPM](github.com/JesusQuijada34/packagemaker/)
