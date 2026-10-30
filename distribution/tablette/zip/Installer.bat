@echo off
rem DCS Tablette - installe et place l'ecran virtuel, les scripts dans DCS,
rem et regle les ecrans de DCS. Voir LISEZ-MOI.txt, "A la main", pour chaque
rem etape faite sans lui.
rem Sans second ecran, pour essayer : Installer.bat --essai
title DCS Tablette - installation
cd /d "%~dp0"
"%~dp0DCS-Tablette.exe" installer %*
echo.
pause
