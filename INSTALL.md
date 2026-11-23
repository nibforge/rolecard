# Installation

[Instalación en español](INSTALACION.md) · [README](README.md) · [Full guide](docs/guide.en.md)

## Requirements
- Python 3.12 or later.
- An AI provider (optional to get started): see [Use your own AI](docs/ai.en.md).

## Install
```
python -m venv venv
venv/Scripts/python -m pip install -r requirements.txt   # Linux/macOS: venv/bin/
venv/Scripts/python -m pip install -e . --no-deps
```

## Configure
Everything is configured in **Settings**, inside the app. Optionally, with environment
variables (`.env.example`):
- `ROLECARD_HOME`: data folder (`~/.rolecard` by default).
- `ROLECARD_OPENAI_API_KEY`: key for an OpenAI-compatible provider, instead of saving
  it in Settings.

## Check that it works
```
venv/Scripts/rolecard
```
Open `http://127.0.0.1:8765`. In **Settings**, **Test connection** checks the AI. The
tests: `venv/Scripts/python -m pip install -r requirements-dev.txt` and
`venv/Scripts/python -m pytest -q`.

## Update
With rolecard closed, copy your data folder as a backup, replace the code with the new
version and repeat both `pip install` commands. On start, the database migrates itself,
and a copy is saved next to it first.
