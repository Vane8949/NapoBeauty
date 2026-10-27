@echo off
chcp 65001 >nul
title Napo Beauty
cd /d "%~dp0"

echo ============================================
echo   Napo Beauty - preparar y abrir el sistema
echo ============================================

rem 1. Entorno virtual con Python 3.14 (los paquetes de SQL Server aun no existen para 3.15)
set "PY314=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 14) else 1)"
    if errorlevel 1 (
        echo El entorno virtual no es de Python 3.14: se vuelve a crear.
        rmdir /s /q venv
    )
)
if not exist "venv\Scripts\python.exe" (
    echo.
    echo Creando el entorno virtual con Python 3.14...
    if exist "%PY314%" (
        "%PY314%" -m venv venv
    ) else (
        py -V:3.14 -m venv venv
        if errorlevel 1 py -3.14 -m venv venv
    )
)
if not exist "venv\Scripts\python.exe" (
    echo No se pudo crear el entorno virtual. Revisa que Python 3.14 este instalado.
    pause
    exit /b 1
)
"venv\Scripts\python.exe" --version

rem 2. Paquetes del proyecto (Django, mssql-django, Pillow...)
echo.
echo Instalando o revisando los paquetes...
"venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
"venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo Fallo la instalacion de paquetes. Revisa tu conexion a internet.
    pause
    exit /b 1
)

rem 3. Tablas propias de Django (sesiones y mensajes) en la base NapoBeauty
echo.
echo Preparando las tablas de Django en SQL Server...
"venv\Scripts\python.exe" manage.py migrate --noinput

rem 4. Prueba de conexion con SQL Server
echo.
"venv\Scripts\python.exe" manage.py probar_bd
if errorlevel 1 (
    echo.
    echo No se pudo conectar a SQL Server. Revisa que el servicio SQL Server este encendido.
    pause
    exit /b 1
)

rem 5. Abrir el sistema
echo.
echo Abriendo http://127.0.0.1:8000/dashboard/  (cierra esta ventana para apagarlo)
start "" http://127.0.0.1:8000/dashboard/
"venv\Scripts\python.exe" manage.py runserver
pause
