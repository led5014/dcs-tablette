@echo off
rem DCS Tablette - installe les scripts dans DCS et regle les ecrans.
rem De preference DCS ferme : il reecrit ses reglages en quittant.
rem Sans second ecran, pour essayer : Installer.bat --essai
title DCS Tablette - installation
cd /d "%~dp0"
"%~dp0DCS-Tablette.exe" installer %*
echo.
pause
