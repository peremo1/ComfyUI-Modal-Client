@echo off
title Instalador ComfyUI + Chroma
echo.
echo  Instalador de ComfyUI + Chroma1-HD
echo  Carpeta de instalacion por defecto: C:\IA
echo  (para otra carpeta: INSTALAR.bat D:\IA)
echo.
set "DEST=%~1"
if "%DEST%"=="" set "DEST=C:\IA"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1" -InstallDir "%DEST%"
echo.
pause
