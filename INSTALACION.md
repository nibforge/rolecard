# Instalación

[Installation in English](INSTALL.md) · [README en español](README.es.md) · [Guía completa](docs/guide.es.md)

## Lo sencillo: descargar y hacer doble clic

1. Instala Python 3.12 o posterior desde [python.org](https://www.python.org/downloads/).
2. Descarga [rolecard.zip](https://github.com/nibforge/rolecard/releases/latest/download/rolecard.zip) y descomprímelo.
3. Haz doble clic en `Iniciar rolecard.bat` (Windows) o `Iniciar rolecard.command`
   (macOS), o ejecuta `start.sh` (Linux).

Cada paso, con lo que hay que pulsar, en [Instalar sin usar la terminal](docs/install.es.md).
El resto de esta página es para desarrolladores.

## Requisitos
- Python 3.12 o posterior.
- Un proveedor de IA (opcional para empezar): ver [Usa tu propia IA](docs/ai.es.md).

## Instalar
```
python -m venv venv
venv/Scripts/python -m pip install -r requirements.txt   # Linux/macOS: venv/bin/
venv/Scripts/python -m pip install -e . --no-deps
```

## Configurar
Todo se configura en **Ajustes**, dentro de la aplicación. Opcionalmente, con variables
de entorno (`.env.example`):
- `ROLECARD_HOME`: carpeta de datos (por defecto `~/.rolecard`).
- `ROLECARD_OPENAI_API_KEY`: clave de un proveedor compatible con OpenAI, en vez de
  guardarla en Ajustes.

## Comprobar que funciona
```
venv/Scripts/rolecard
```
Abre `http://127.0.0.1:8765`. En **Ajustes**, **Probar conexión** comprueba la IA. Los
tests: `venv/Scripts/python -m pip install -r requirements-dev.txt` y
`venv/Scripts/python -m pytest -q`.

## Actualizar
Con rolecard cerrado, copia tu carpeta de datos como respaldo, sustituye el código por
la versión nueva y repite los dos `pip install`. Al arrancar, la base de datos se migra
sola y antes se guarda una copia junto a ella.
