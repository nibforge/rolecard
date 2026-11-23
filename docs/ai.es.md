# Usa tu propia IA

[English](ai.en.md) · [Inicio](index.md)

rolecard no tiene un servicio de IA propio ni una cuenta en la que registrarse. Usa el
que tú elijas: un nivel gratuito, un modelo en tu propio equipo o un plan que ya pagas.

## Por qué tu propia IA

rolecard está pensado para pocas candidaturas bien hechas, no para muchas enviadas a
ciegas. Cada CV y cada carta se adaptan a una oferta, cada frase muestra el hecho de tu
perfil del que sale, tú la revisas y te presentas tú desde la oferta original. Eso
necesita poca IA: puntuar 100 ofertas y preparar 10 CV y 10 cartas gastó unos 92.000
tokens de entrada y 20.000 de salida en nuestra medición (abajo). Cabe en un nivel
gratuito, y en uno de pago cuesta céntimos.

Usar tu propia IA también significa que decides adónde va tu CV, y puedes cambiar de
proveedor cuando quieras en **Ajustes**.

## Las opciones

| Opción | Coste | Adónde van tus datos | Cómo la usa rolecard |
|---|---|---|---|
| Gemini (Google AI Studio) | Nivel gratuito; pago por uso si activas la facturación | Servidores de Google | Compatible con OpenAI |
| Ollama | Gratis | Se quedan en tu equipo (modelos locales) | Compatible con OpenAI |
| Claude Code | Tu plan de Claude (Pro, Max…) | Servidores de Anthropic | Claude Code |
| API de OpenAI | Pago por uso | Servidores de OpenAI | Compatible con OpenAI |
| API de Anthropic | Pago por uso | Servidores de Anthropic | Claude Code con tu clave (`ANTHROPIC_API_KEY`) |
| Planes de ChatGPT (Codex) | — | — | No compatible |

Los planes de ChatGPT incluyen Codex, pero no hay una vía documentada para que otra
aplicación use Codex con la sesión de tu cuenta, así que rolecard no lo hace.

## ¿Qué es una clave de API?

Una clave de API es una contraseña que identifica tu cuenta ante el servicio de IA.
Quien la tenga puede gastar tu cuota o tu saldo. Por eso:

- **No la compartas nunca**, ni en capturas ni en mensajes.
- **No la subas a ningún sitio**: ni a un repositorio, ni a un foro, ni a un documento
  compartido.
- **Si se filtra, revócala** en la web del proveedor y crea otra.

rolecard guarda la clave en `config.toml`, dentro de tu carpeta de datos (`~/.rolecard`,
o la que indiques con `ROLECARD_HOME`), nunca en el código ni en el repositorio. Si
prefieres no guardarla en ese archivo, deja el campo vacío y pon la clave en la variable
de entorno `ROLECARD_OPENAI_API_KEY`.

Claude Code con tu plan y Ollama no usan clave: Claude Code usa la sesión iniciada en tu equipo y
Ollama corre en tu propio ordenador.

## Configurar Gemini (gratis)

Necesitas una cuenta de Google (la de Gmail sirve). Si no tienes, créala antes en
[Google](https://accounts.google.com/signup).

1. Entra en [Google AI Studio](https://aistudio.google.com/) e inicia sesión con tu
   cuenta de Google.
2. La primera vez, AI Studio te pide aceptar sus condiciones de servicio. Acéptalas: a
   las cuentas nuevas les crea entonces un proyecto y una clave por defecto.
3. Abre la página **API Keys** ([aistudio.google.com/api-keys](https://aistudio.google.com/api-keys)).
   Si ya ves una clave en la lista, sáltate el paso siguiente.
4. Si no hay ninguna, pulsa **Create API key**. Si ya usabas Google Cloud y no tienes
   proyecto en AI Studio, impórtalo antes: en **Projects**, **Import projects**, elige el
   proyecto y pulsa **Import**. Al terminar, la clave aparece en la tabla junto a su
   proyecto.
5. Abre la clave y cópiala entera. Guárdala solo donde la vayas a usar.
6. Comprueba que no tienes facturación activada: en la página de proyectos
   ([aistudio.google.com/projects](https://aistudio.google.com/projects)), la columna
   **Billing Tier** debe indicar el nivel gratuito (**Free**) o **Set up billing**. Sin
   una cuenta de facturación vinculada, Google no puede cobrarte nada.
7. En rolecard, abre **Ajustes** y elige **Compatible con OpenAI**. Rellena:
   - **Dirección del servicio**: `https://generativelanguage.googleapis.com/v1beta/openai`
   - **Modelo**: `gemini-3.5-flash-lite`
   - **Clave de API**: pega tu clave (o déjala vacía y pon la variable de entorno
     `ROLECARD_OPENAI_API_KEY`).
8. Pulsa **Guardar ajustes** y después **Probar conexión**. Si todo va bien, verás
   «Conexión correcta con…» y el nombre del proveedor.

**Revocar la clave.** Google indica desactivarla o borrarla en la página de credenciales
de [Google Cloud console](https://console.cloud.google.com/apis/credentials), y crear
una nueva si la anterior se ha filtrado. La documentación de AI Studio no describe un
botón de borrado en su propia web. Fuente: [claves de la API de Gemini](https://aistudio.google.com/docs/api-key).

Recomendamos `gemini-3.5-flash-lite`: respondió bien a las cuatro operaciones a la
primera. `gemini-3.8-flash` también funciona, pero su nivel gratuito solo permitió 20
peticiones al día en nuestra prueba, que no llegan para puntuar 100 ofertas.
`gemini-2.5-flash` ya no está disponible para cuentas nuevas.

**Límites del nivel gratuito.** Google fija límites diarios y por minuto por proyecto,
que se ven en AI Studio y en su [página de límites](https://ai.google.dev/gemini-api/docs/rate-limits).
Cuando llegas a uno, rolecard te lo dice y, cuando Google indica cuánto esperar, cuándo
volver a intentarlo. Envía una sola petición y no reintenta en bucle, y la puntuación en
bloque se para al primer error, así que un límite agotado no gasta más peticiones. A
veces Gemini responde «high demand» (HTTP 503) cuando sus servidores están ocupados:
rolecard tampoco lo reintenta; prueba unos minutos después.

**Privacidad en el nivel gratuito.** En el nivel gratuito, Google usa lo que envías y las
respuestas para mejorar sus productos y su IA, y pueden leerlo revisores humanos
(desvinculado de tu cuenta); Google pide no enviar información personal o confidencial.
**Excepción:** en el Espacio Económico Europeo, Suiza y el Reino Unido rigen para todo el
uso, también el gratuito, las condiciones de los servicios de pago, y con ellas tus datos
no se usan para mejorar productos. En el resto, activar la facturación te da esas
condiciones. No hay otro interruptor. Fuente: [condiciones de la API de Gemini](https://ai.google.dev/gemini-api/terms),
«How Google Uses Your Data».

## Configurar Ollama (local, gratis)

1. Descarga Ollama desde su [página de descarga](https://ollama.com/download) e
   instálalo:
   - **Windows**: ejecuta `OllamaSetup.exe`. No pide permisos de administrador y queda
     funcionando en segundo plano.
   - **macOS**: abre `ollama.dmg` y arrastra Ollama a **Aplicaciones**.
   - **Linux**: en una terminal, `curl -fsSL https://ollama.com/install.sh | sh`.

   Requisitos de cada sistema: [Windows](https://docs.ollama.com/windows),
   [macOS](https://docs.ollama.com/macos), [Linux](https://docs.ollama.com/linux).
2. Elige un modelo en la [biblioteca de Ollama](https://ollama.com/library) y
   descárgalo con `ollama pull <modelo>`. Los modelos ocupan varios GB y piden memoria:
   mira lo que indica su ficha antes de elegir. No hemos medido ninguno con rolecard.
3. Comprueba que funciona con `ollama run <modelo>`: se abre un chat; escribe algo, mira
   que responde y sal con `/bye`. En Linux, si no está en marcha, arráncalo con
   `ollama serve`. Ollama escucha en `http://localhost:11434`.
4. En **Ajustes**, elige **Compatible con OpenAI**:
   - **Dirección del servicio**: `http://localhost:11434/v1`
   - **Modelo**: el mismo nombre que usaste en `ollama pull`
   - **Clave de API**: déjala vacía; con modelos locales Ollama no la pide.
5. **Guardar ajustes** y después **Probar conexión**.

Fuentes: [inicio rápido de Ollama](https://docs.ollama.com/quickstart),
[compatibilidad con OpenAI](https://docs.ollama.com/api/openai-compatibility).

Con modelos locales, Ollama no recoge, guarda ni envía tus prompts ni las respuestas. Sus
modelos «cloud» son otra cosa: se ejecutan en los servidores de Ollama. Fuentes:
[privacidad de Ollama](https://ollama.com/privacy), [FAQ de Ollama](https://docs.ollama.com/faq).
La velocidad y la calidad de las respuestas dependen de tu equipo y del modelo; no lo
hemos medido.

## Configurar Claude Code (con tu plan)

Aquí **no hay clave que copiar**: Claude Code es un programa que instalas en tu equipo
e inicia sesión con tu cuenta de Claude. rolecard lo ejecuta y usa esa sesión.

1. **Requisitos.** Un [plan de Claude](https://claude.com/pricing) que incluya Claude
   Code (Pro, Max, Team, Enterprise…). El plan gratuito de claude.ai no lo incluye.
2. **Instálalo** con el instalador oficial. Abre una terminal y ejecuta:
   - macOS y Linux:
     ```
     curl -fsSL https://claude.ai/install.sh | bash
     ```
   - Windows, en **PowerShell**:
     ```
     irm https://claude.ai/install.ps1 | iex
     ```
   - Windows, en **Símbolo del sistema** (CMD):
     ```
     curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
     ```
   En Windows no hace falta ser administrador. Si PowerShell dice que `&&` no es válido,
   estás en PowerShell con el comando de CMD (o al revés si dice que `irm` no se
   reconoce): usa el del otro apartado.
3. **Inicia sesión.** Cierra y vuelve a abrir la terminal, escribe `claude` y sigue las
   indicaciones: se abre el navegador para entrar con tu cuenta de Claude. Al terminar,
   vuelves a la terminal con la sesión iniciada; ya puedes cerrarla.
4. **Compruébalo** con `claude --version`, que muestra la versión instalada, o con
   `claude doctor`, que revisa la instalación sin abrir una sesión.
5. En rolecard, abre **Ajustes** y elige **Claude Code** (o **Automático**, que lo usa
   cuando no hay un servicio compatible con OpenAI configurado). Al lado debe poner
   «Encontrado en este equipo». Pulsa **Guardar ajustes** y después **Probar conexión**.

**Con una clave de la API de Anthropic (pago por uso).** Claude Code también funciona
con una cuenta de Claude Console, que cobra cada petición en lugar de usar un plan. Pon tu
clave en la variable de entorno `ANTHROPIC_API_KEY` antes de arrancar rolecard y elige
**Claude Code** en **Ajustes**. rolecard no guarda ni lee esa clave: solo deja que llegue
a Claude Code, igual que el resto de variables `ANTHROPIC_*`
([SECURITY.md](https://github.com/nibforge/rolecard/blob/main/SECURITY.md)). Si la tienes
puesta, Claude Code puede usarla en lugar de tu plan; quítala si prefieres la
suscripción. No hemos medido su consumo. Fuente: [instalación de Claude Code](https://code.claude.com/docs/en/setup),
«Authenticate».

Fuentes: [instalación de Claude Code](https://code.claude.com/docs/en/setup),
[inicio rápido](https://code.claude.com/docs/en/quickstart).

rolecard lo ejecuta sin herramientas, en modo seguro y en una carpeta temporal vacía
([SECURITY.md](https://github.com/nibforge/rolecard/blob/main/SECURITY.md)). Gasta la
cuota de tu plan, no un precio por token. Que Anthropic pueda entrenar con tus sesiones
depende del ajuste «Help improve Claude» de tu
[configuración de privacidad](https://claude.ai/settings/data-privacy-controls). Fuentes:
[uso de datos de Claude Code](https://code.claude.com/docs/en/data-usage),
[cuánto tiempo guarda Anthropic tus datos](https://privacy.claude.com/en/articles/10023548-how-long-do-you-store-my-data).

## Configurar la API de OpenAI (pago por uso)

La API de OpenAI **no es ChatGPT**: tiene su propia cuenta y su propia facturación, y
pagar ChatGPT (Plus u otro plan) no incluye el uso de la API
([fuente](https://help.openai.com/en/articles/8156019)).

1. Entra en la [plataforma de desarrolladores de OpenAI](https://platform.openai.com/)
   y crea una cuenta o inicia sesión.
2. **Añade saldo.** En la página de facturación
   ([Billing](https://platform.openai.com/settings/organization/billing)), pulsa **Add
   payment details**, introduce tu medio de pago y elige el importe inicial (el mínimo
   es de 5 $). La recarga automática (**Use auto-reload**) viene activada: desactívala si
   no quieres que se recargue sola. Más adelante, **Buy credits** o **Add to credit
   balance** añade más. Fuente: [saldo prepago](https://help.openai.com/en/articles/8264644-how-can-i-set-up-prepaid-billing).
3. **Pon un límite de gasto.** En [Limits](https://platform.openai.com/settings/organization/limits),
   en **Spend**, pulsa **Edit spend limit**, escribe tu tope en **Monthly spend limit**,
   activa **Enforce a hard limit** y pulsa **Save**. OpenAI avisa de que el corte no es
   instantáneo y el gasto puede pasarse un poco. Fuente: [límites de gasto](https://developers.openai.com/api/docs/guides/spend-limits).
4. **Crea la clave** en la página [API keys](https://platform.openai.com/api-keys). Copia
   la clave en cuanto aparezca: no cuentes con poder volver a verla después; si la
   pierdes, crea otra.
5. En rolecard, abre **Ajustes** y elige **Compatible con OpenAI**: **Dirección del
   servicio** `https://api.openai.com/v1`, el **Modelo** que quieras de los que lista
   OpenAI y, en **Clave de API**, tu clave.
6. **Guardar ajustes** y después **Probar conexión**.

**Revocar la clave.** OpenAI indica rotarla desde la misma página **API keys**: crear una
nueva y revocar la vieja cuando la nueva funcione. Fuente: [seguridad de las claves](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety).

OpenAI no entrena con los datos de la API salvo
que lo actives, y los guarda hasta 30 días para vigilar abusos. Fuente:
[OpenAI: tus datos](https://developers.openai.com/api/docs/guides/your-data). No hemos
medido su consumo.

## Lo que hemos medido

Medido el 2026-11-22 con `scripts/measure_usage.py` y los datos ficticios de
demostración. Los tokens son los que informó cada proveedor en sus respuestas; nada es
estimado.

| Operación | Gemini 3.5 Flash-Lite (entrada / salida) | Claude Code 2.1.330 (entrada / salida) |
|---|---|---|
| Leer el CV | 534 / 351 | 3.079 / 514 |
| Puntuar una oferta | 750 / 111 | 3.335 / 232 |
| CV adaptado | 888 / 539 | 3.575 / 549 |
| Carta | 785 / 304 | 3.418 / 662 |

La salida de Gemini incluye sus tokens de «thinking». La mayor parte de la entrada de
Claude Code es el contexto propio de la CLI, no el prompt de rolecard.

Coste de 100 ofertas con Gemini 3.5 Flash-Lite, al precio oficial de pago de 0,30 $ por
millón de tokens de entrada y 2,50 $ por millón de salida
([precios](https://ai.google.dev/gemini-api/docs/pricing), consultado el 2026-11-22):

| Caso | Peticiones | Tokens (entrada / salida) | Nivel de pago | Nivel gratuito |
|---|---|---|---|---|
| 100 puntuaciones + 10 CV + 10 cartas | 120 | 91.730 / 19.530 | 0,08 $ | 0 $ |
| 100 puntuaciones + 100 CV + 100 cartas | 300 | 242.300 / 95.400 | 0,31 $ | 0 $ |

Claude Code no tiene precio en dólares: gasta la cuota de tu plan, que Anthropic no
expresa en tokens. Lanza el script tú mismo para medir tu propio proveedor.

## Problemas frecuentes

- **«La clave no puede tener espacios ni saltos de línea, ni pasar de 500 caracteres.»**
  Al copiar se ha colado un espacio o un salto de línea dentro de la clave. rolecard
  quita los del principio y el final, pero no los de en medio: vuelve a copiarla entera,
  de una vez, y pégala de nuevo.
- **Probar conexión falla.** La prueba usa los ajustes guardados: pulsa antes **Guardar
  ajustes**. Si ves «El servicio de IA ha rechazado la petición. Revisa la dirección, el
  modelo y la clave.», revisa esos tres campos letra a letra. Si ves «No se puede llegar
  al servicio de IA. Comprueba que está en marcha y que la dirección es correcta.»,
  revisa tu conexión o, con Ollama, que esté en marcha.
- **«Se ha agotado el límite de uso del servicio de IA…»** Has llegado al límite del
  nivel gratuito (suele ser diario). rolecard no reintenta; cuando Google indica cuánto
  esperar, el mensaje lo dice. Vuelve a probar más tarde.
- **«El servicio de IA está ocupado ahora mismo…»** Gemini ha respondido «high demand»
  (HTTP 503): sus servidores están ocupados. No es un problema de tu clave. rolecard no
  reintenta: prueba unos minutos después.
- **Claude Code sin sesión iniciada.** Si ves «La IA no ha podido responder. Comprueba
  que funciona y que tienes la sesión iniciada.», abre una terminal, ejecuta `claude` e
  inicia sesión. Si ves «Claude Code no está instalado o no está en el PATH…», vuelve a
  abrir la terminal tras instalarlo o revisa la [solución de problemas de
  instalación](https://code.claude.com/docs/en/troubleshoot-install).
