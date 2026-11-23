# Instalar rolecard sin usar la terminal

[English](install.en.md) · [Inicio](index.md) · [Guía](guide.es.md)

Esta guía es para ti si nunca has usado una terminal ni una herramienta de programación.
No vas a escribir ninguna orden: descargas un archivo, haces doble clic y usas rolecard
en tu navegador.

rolecard necesita una cosa instalada en tu ordenador: **Python**, el programa gratuito
sobre el que funciona. Se instala una vez, siguiendo los pasos de abajo. La primera vez
tarda unos 10 minutos; después, rolecard se abre en unos segundos.

## Qué necesitas

- Un ordenador con Windows o macOS (también funciona en Linux).
- Conexión a internet la primera vez.
- Python 3.12 o posterior. Si no sabes si lo tienes, sigue igualmente la sección
  siguiente: instalarlo otra vez no hace daño.

## 1. Instalar Python en Windows

1. Abre [python.org/downloads](https://www.python.org/downloads/).
2. Pulsa **Download Python install manager**. Si en su lugar la página muestra un botón
   **Download Python 3.x.y** para Windows, pulsa ese.
3. Abre el archivo que has descargado y pulsa **Install**.
4. Si aparece la casilla **Add python.exe to PATH**, márcala. (PATH es la lista de
   sitios donde Windows busca los programas; marcarla permite a rolecard encontrar
   Python.)
5. Si te pregunta si añadir una carpeta a tu PATH, responde que sí.
6. Cuando diga que ha terminado, ciérralo.

Fuente oficial: [Usar Python en Windows](https://docs.python.org/3/using/windows.html#python-install-manager).
Con el install manager, Python puede terminar de instalarse la primera vez que abras
rolecard y hacerte una pregunta en la ventana negra: responde que sí.

## 2. Instalar Python en macOS

1. Abre [python.org/downloads](https://www.python.org/downloads/).
2. Pulsa el botón amarillo **Download Python 3.x.y**.
3. Abre el archivo `.pkg` descargado y sigue los pasos (**Continuar**, **Aceptar**,
   **Instalar**).
4. Cuando diga que ha terminado, ciérralo.

Fuente oficial: [Usar Python en macOS](https://docs.python.org/3/using/mac.html#installation-steps).

## 3. Descargar rolecard

1. Descarga [rolecard.zip](https://github.com/nibforge/rolecard/releases/latest/download/rolecard.zip).
2. En Windows, abre la carpeta **Descargas**, haz clic derecho en `rolecard.zip` y elige
   **Extraer todo…** y después **Extraer**. No abras nada desde dentro del zip: no
   funcionará.
3. En macOS, haz doble clic en `rolecard.zip` en **Descargas**: aparece una carpeta
   `rolecard` a su lado.
4. Si quieres, mueve la carpeta `rolecard` a un sitio cómodo, como **Documentos**.

Cómo descomprimir en Windows, según Microsoft: [Comprimir y descomprimir archivos](https://support.microsoft.com/windows/zip-and-unzip-files-8d28fa72-f2f9-712f-67df-f80cf89fd4e5).

## 4. Abrir rolecard

1. Abre la carpeta `rolecard`.
2. Haz doble clic en **Iniciar rolecard**: `Iniciar rolecard.bat` en Windows,
   `Iniciar rolecard.command` en macOS. En Linux, ejecuta `start.sh`.
3. La primera vez, una ventana negra dice «Preparando rolecard (solo la primera vez)…»
   mientras descarga lo que rolecard necesita. Espera unos minutos.
4. En Windows, después pregunta si crear un acceso directo «rolecard» en el escritorio:
   escribe S y pulsa Intro (o N si no lo quieres).
5. rolecard se abre en tu navegador. Ya está.

Si Windows o macOS muestran un aviso de seguridad, mira la sección siguiente.

## 5. Avisos de seguridad que puedes ver

rolecard es nuevo y gratuito, así que no lo firma una empresa que Microsoft o Apple
conozcan. La primera vez, tu ordenador puede avisarte. Es lo esperado.

### Windows: «Windows protegió su PC»

1. Pulsa **Más información**.
2. Pulsa **Ejecutar de todas formas**.

Solo aparece la primera vez. Qué es este aviso, según Microsoft:
[Microsoft Defender SmartScreen](https://learn.microsoft.com/windows/security/operating-system-security/virus-and-threat-protection/microsoft-defender-smartscreen/).

### macOS: «Iniciar rolecard.command» no se puede abrir

1. Pulsa **OK** (o **Aceptar**) para cerrar el aviso.
2. Abre el menú Apple, después **Ajustes del Sistema** y después **Privacidad y
   seguridad**.
3. En **Seguridad**, pulsa **Abrir igualmente** (está ahí durante una hora más o menos
   tras el aviso).
4. Escribe la contraseña de tu Mac y pulsa **Aceptar**.

Desde entonces se abre con doble clic. En versiones antiguas de macOS, haz clic derecho
(o Control y clic) en el archivo y elige **Abrir**. Apple explica las dos formas:
[Abrir una app de un desarrollador no identificado](https://support.apple.com/guide/mac-help/mh40616/mac).

## 6. La ventana negra

La ventana negra (una terminal: una ventana donde los programas muestran texto) es
rolecard funcionando. Tu navegador habla con ella en `http://127.0.0.1:8765`, una
dirección que solo puede abrir tu ordenador. Dice «rolecard está abierto en tu
navegador». Déjala abierta mientras uses rolecard; puedes minimizarla.

Si cierras solo la pestaña del navegador, rolecard sigue funcionando en la ventana negra.
Para volver, haz doble clic otra vez en **Iniciar rolecard**: se da cuenta de que ya está
abierto y solo abre tu navegador.

## 7. Cerrar rolecard

- Pulsa **Salir**, abajo en el menú de la izquierda. La página dice «rolecard se ha
  cerrado»; ahora cierra la pestaña.
- O cierra la ventana negra.

Lo que haces se guarda sobre la marcha, así que no pierdes nada de ninguna forma.

## 8. Abrirlo otro día

- Haz doble clic en el acceso directo **rolecard** del escritorio (en Windows, si lo
  creaste) o en **Iniciar rolecard**, dentro de la carpeta `rolecard`.
- Se abre en unos segundos: la preparación solo ocurre la primera vez.

## 9. Actualizar a una versión nueva

Tus datos no están en la carpeta `rolecard`: están en una carpeta llamada `.rolecard`
dentro de tu carpeta de usuario. Actualizar no los toca.

1. Cierra rolecard (**Salir**).
2. Descarga el nuevo [rolecard.zip](https://github.com/nibforge/rolecard/releases/latest/download/rolecard.zip)
   y descomprímelo, como en el paso 3.
3. Borra la carpeta `rolecard` antigua y pon la nueva en el mismo sitio (así el acceso
   directo del escritorio sigue funcionando).
4. Haz doble clic en **Iniciar rolecard**. Se prepara otra vez, una sola vez.

Para guardar antes una copia de tus datos: en Windows, abre el Explorador de archivos,
escribe `%USERPROFILE%\.rolecard` en la barra de direcciones y copia esa carpeta; en
macOS, en el Finder pulsa Cmd+Mayúsculas+G, escribe `~/.rolecard` y cópiala.

## Si algo falla

- **«rolecard necesita Python 3.12 o superior»**: instala Python (paso 1 o 2), cierra la
  ventana negra y vuelve a hacer doble clic en **Iniciar rolecard**.
- **«Algo ha fallado» mientras se prepara**: comprueba tu conexión a internet y vuelve a
  hacer doble clic en **Iniciar rolecard**.
- **En macOS no pasa nada**: mira el aviso de macOS en el paso 5.
- Cualquier otra cosa: la ventana negra se queda abierta con el mensaje. Apúntalo o haz
  una captura y [abre una incidencia](https://github.com/nibforge/rolecard/issues).
