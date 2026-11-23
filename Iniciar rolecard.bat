@echo off
rem Double-click launcher for rolecard on Windows. It checks for Python 3.12+, creates
rem .venv here the first time, installs requirements.txt (pinned, with hashes) and runs
rem "python -m rolecard", which opens the browser. Your data stays in ~/.rolecard.
setlocal
rem Never run a program that happens to sit in this folder instead of the real one.
set "NoDefaultCurrentDirectoryInExePath=1"
chcp 65001 >nul
cd /d "%~dp0"
set "RC_SELF=%~f0"
set "VENV_PY=.venv\Scripts\python.exe"
set "RC_LANG=en"
for /f %%L in ('powershell -NoProfile -Command "[Globalization.CultureInfo]::CurrentUICulture.TwoLetterISOLanguageName"') do set "RC_LANG=%%L"
if /i "%RC_LANG%"=="es" (call :texts_es) else (call :texts_en)

rem A .venv without the install marker was left half-made (closed window, Ctrl+C):
rem it is rebuilt.
if exist "%VENV_PY%" if exist .venv\rolecard-requirements.txt goto install
rem Output is not hidden: the Python install manager may install Python on first use and
rem ask a question here.
set "PY="
python -c "import sys; sys.exit(sys.version_info < (3, 12))" 2>nul && set "PY=python"
if not defined PY py -3 -c "import sys; sys.exit(sys.version_info < (3, 12))" 2>nul && set "PY=py -3"
if not defined PY goto no_python
echo %T_PREPARING%
set "FIRST=1"
if exist .venv rmdir /s /q .venv
%PY% -m venv .venv || (rmdir /s /q .venv 2>nul & goto failed)

:install
fc /b requirements.txt .venv\rolecard-requirements.txt >nul 2>&1 && goto run
if not defined FIRST echo %T_PREPARING%
"%VENV_PY%" -m pip install --disable-pip-version-check --require-hashes -r requirements.txt || goto failed
copy /y requirements.txt .venv\rolecard-requirements.txt >nul
if defined FIRST call :shortcut

:run
"%VENV_PY%" -m rolecard || goto failed
exit /b 0

:no_python
echo.
echo %T_NO_PYTHON%
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:failed
echo.
echo %T_FAILED%
pause
exit /b 1

:shortcut
set "ANSWER="
set /p "ANSWER=%T_SHORTCUT% "
if defined ANSWER set "ANSWER=%ANSWER:"=%"
if /i not "%ANSWER%"=="s" if /i not "%ANSWER%"=="y" exit /b 0
powershell -NoProfile -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'rolecard.lnk')); $s.TargetPath = $env:RC_SELF; $s.WorkingDirectory = Split-Path $env:RC_SELF; $s.Save()" >nul || echo %T_NO_SHORTCUT%
exit /b 0

:texts_es
set "T_PREPARING=Preparando rolecard (solo la primera vez)…"
set "T_NO_PYTHON=rolecard necesita Python 3.12 o superior. Instálalo desde python.org (se abre ahora), marca «Add python.exe to PATH» y vuelve a hacer doble clic aquí."
set "T_FAILED=Algo ha fallado: lee el mensaje de arriba. La guía de instalación (docs/install.es.md) explica qué hacer."
set "T_SHORTCUT=¿Crear un acceso directo «rolecard» en el escritorio? (S/N)"
set "T_NO_SHORTCUT=No se ha podido crear el acceso directo; puedes abrir rolecard desde esta carpeta."
exit /b 0

:texts_en
set "T_PREPARING=Preparing rolecard (first time only)…"
set "T_NO_PYTHON=rolecard needs Python 3.12 or newer. Install it from python.org (opening now), tick “Add python.exe to PATH” and double-click here again."
set "T_FAILED=Something went wrong: read the message above. The install guide (docs/install.en.md) explains what to do."
set "T_SHORTCUT=Create a “rolecard” shortcut on the desktop? (Y/N)"
set "T_NO_SHORTCUT=The shortcut could not be created; you can open rolecard from this folder."
exit /b 0
