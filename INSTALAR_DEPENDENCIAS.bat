@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo =============================================
echo   TABLETA DE SONIDOS - INSTALACION
echo =============================================
where py >nul 2>nul
if errorlevel 1 (
  echo No se encontro Python. Instalalo desde https://www.python.org/downloads/windows/
  echo Durante la instalacion marca "Add Python to PATH".
  pause
  exit /b 1
)
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Hubo un error instalando las dependencias.
  pause
  exit /b 1
)
echo.
echo Instalacion terminada. Ahora ejecuta INICIAR.bat
pause
