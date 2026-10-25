@echo off
rem DCS Tablette - retire les scripts de DCS et remet l'affichage d'avant.
rem DCS ferme, sinon l'affichage reste a remettre a la main.
title DCS Tablette - desinstallation
cd /d "%~dp0"
"%~dp0DCS-Tablette.exe" desinstaller
echo.
pause
