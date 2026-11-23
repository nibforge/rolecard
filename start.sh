#!/usr/bin/env bash
# Launcher for rolecard on macOS and Linux. It checks for Python 3.12+, creates .venv
# here the first time, installs requirements.txt (pinned, with hashes) and runs
# "python -m rolecard", which opens the browser. Your data stays in ~/.rolecard.
cd "$(dirname "$0")" || exit 1

if [ "$(uname)" = Darwin ]; then
  lang=$(defaults read -g AppleLanguages 2>/dev/null | sed -n 2p | tr -d ' "')
else
  lang=${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}
fi
case "$lang" in es*) ES=1 ;; *) ES= ;; esac

say() { if [ -n "$ES" ]; then echo "$1"; else echo "$2"; fi; }
wait_key() {
  echo
  read -r -n 1 -s -p "$(say 'Pulsa una tecla para cerrar…' 'Press any key to close…')"
  echo
}
fail() {
  echo
  say "Algo ha fallado: lee el mensaje de arriba. La guía de instalación (docs/install.es.md) explica qué hacer." \
      "Something went wrong: read the message above. The install guide (docs/install.en.md) explains what to do."
  wait_key
  exit 1
}

find_python() {
  for c in python3.15 python3.14 python3.13 python3.12 python3; do
    command -v "$c" >/dev/null 2>&1 || continue
    # On macOS, /usr/bin/python3 is Apple's (too old) and may ask to install developer tools.
    [ "$(uname)" = Darwin ] && [ "$(command -v "$c")" = /usr/bin/python3 ] && continue
    if "$c" -c 'import sys; sys.exit(sys.version_info < (3, 12))' >/dev/null 2>&1; then
      echo "$c"
      return
    fi
  done
}

# A .venv without the install marker was left half-made (closed window, Ctrl+C): rebuild it.
if [ ! -x .venv/bin/python ] || [ ! -f .venv/rolecard-requirements.txt ]; then
  PY=$(find_python)
  if [ -z "$PY" ]; then
    say "rolecard necesita Python 3.12 o superior. Instálalo desde python.org (se abre ahora) y vuelve a abrir este archivo." \
        "rolecard needs Python 3.12 or newer. Install it from python.org (opening now) and open this file again."
    url=https://www.python.org/downloads/
    if command -v open >/dev/null 2>&1; then open "$url"; else xdg-open "$url" >/dev/null 2>&1; fi
    wait_key
    exit 1
  fi
  say "Preparando rolecard (solo la primera vez)…" "Preparing rolecard (first time only)…"
  FIRST=1
  rm -rf .venv
  "$PY" -m venv .venv || { rm -rf .venv; fail; }
fi

if ! cmp -s requirements.txt .venv/rolecard-requirements.txt; then
  [ -n "$FIRST" ] || say "Preparando rolecard (solo la primera vez)…" "Preparing rolecard (first time only)…"
  .venv/bin/python -m pip install --disable-pip-version-check --require-hashes -r requirements.txt || fail
  cp requirements.txt .venv/rolecard-requirements.txt
fi

.venv/bin/python -m rolecard || fail
