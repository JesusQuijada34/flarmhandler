Bugs y planes

El Primer bug se debe a que la pantalla está toda desorganizada y cuando descomprime e "instala", no sé por qué descomprime el contenido de forma restrictive y tengo que manualmente aplicar los permisos a los archivos para facilitar la lectura y escritura en el disco

La Interfaz no carga bien los assets y la mayoría de los paquetes son descompuestos con la plataforma alpha cube siendo el paquete distinto de plataforma y los íconos no son cargados correctamente y los accesos directos no son instalados

La Interfaz parece antigua y deforme (.refs/bug.png) deberías de hacerla exactamente igual como la referencia ref.png en .refs/ y si no puedes leer imágenes pues te detallo claramente lo que está:

{bug: }

{ref: }

(recomiendo que si has podido usar vision de imágenes, procede a eliminar .refs/ después de haber visualizado la imagen. Solo Manus AI)
(si es open hands quien leyó la descripción y halló el error, procederá a eliminar la carpeta solamente una vez aprobada la corrección del error, aplica también con Manus AI. Open hands)
(exijo qué los 2 eliminen la carpeta una vez aprobé el bug fix y las mejoras solicitadas en este archivo mark down)
(si chat gpt logra en contra del error y hacia la mejora exigía en este Readme, solamente all to comprobar qué todo está a la perfección, le daré permiso a chat gpt pasta procesar la carpeta)
(hay 2 imágenes, una con el error y la otra con la referencia solicitada sumando más ajustes describidos en este Readme)

Y que si el icono tiene fondo transparente, pinta con el color del acento del sistema operativo, all igual que el acento de los controles, y me gustarían los botones con esa geometría y estilo uwp, actualiza los qss de package maker y del handler por favor

Y en vez del fondo sólido aplicar un banner borroso qué usa assets/splash.png, usarlo como container para el contenido y del resto hacia abajo aplicar la mica, si se detecta una pantalla vertical mostrar como relleno centrado assets/splash_setup.png y borroso, De lo contrario si no hay assets disponibles se usará una mica completa.

El Instalador debe de adoptar el icono del paquete como ícono de aplicación y ventana, y si detecta un asset llamado assets/landscape_splash.png, abre un frame como un splash integrado tipo como el de package maker, pero reemplazará la transparencia del splash por el color del sistema operativo, y si detecta assets/portrait_splash.png muestra eso como un splash, El mismo procedimiento pero solamente si la pantalla es resolución vertical. Cuando se detecte qué la ventana fue dibujada y cargada exitosamente, El splash desvanece y revela la pantalla. Y como saber si la pantalla es vertical? Viendo si el ancho es menor que el alto, y como se sabe si es horizontal? Pues al revés, ancho más largo qué el alto. Y si la pantalla es cúbica? Pues se ignora y se usa cualquier asset de splash.

Si No se encuentran los assets de splashes, se hacen manual, Solo es un marco completamente transparente y en el centro colocar a 512px app/app-icon.ico

Dimensions

Horizontal 1366 * 768
Vertical 768 * 1366
Cubico 1280px

Allí está el procedimiento. Aunque hay que hacer una librería global y compartida para que package maker haga esos splashes en los proyectos y que al compilar inyecté un cargador de splash tipo bootloader como si fuese un lanzador iflapp, pero para que quede instalado el engine de splash un proyecto iflapp debe de tener un importe necesario que el mismo package maker traslade a la carpeta de Liberia lib/ y al compilar edité el script para que después de todos los importes se incluya el bootloader y luego al final busque donde se crea la aplicación para que después qué sé cree la interfaz y todo, introduzca una línea qué desenlace el bootloader para hacer desvanecer el splash y revelar la aplicación detrás, así mismo como los uwp. Pero solamente es compatible con un proyecto pyqt6/leviathan-ui. Aunque como versión beta se puede adaptar a cualquier librería de interfaz gráfica sin ningún problema solamente con otro método para lograr la perfecta transición

Si no tienes JesusQuijada34/packagemaker.git o JesusQuijada34/flarmhandler.git, clona los y lee su funcionamiento, pero antes todo haz un pull y comparalos a ver que cambió después de tus acciones de push para saber como crear un change log o un release notes. Recuerda que por cada cambio empuja a main SIN CREAR PULLS REQUESTS SIN MI CONSENTIMIENTO NI OTRAS RAMAS RARAS. Recuerda marcar y eliminar tareas completas en cada push, y revisión principal de este archivo obligatorio para proceder con la comparación y cualquier contexto qué haya quedado después de cada tarea completada, sumalo a cada AGENTS.MD de cada repo actualizando la información y pasos y conocimiento a seguir