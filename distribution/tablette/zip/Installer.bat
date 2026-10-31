@echo off
rem DCS Tablette - installe et place l'ecran virtuel, les scripts dans DCS,
rem regle les ecrans de DCS, copie le programme dans
rem %LOCALAPPDATA%\Programs\DCS-Tablette (raccourcis bureau et menu Demarrer),
rem puis le demarre. Voir LISEZ-MOI.txt, "A la main", pour chaque etape faite
rem sans lui. Sans second ecran, pour essayer : Installer.bat --essai
title DCS Tablette - installation
cd /d "%~dp0"
"%~dp0DCS-Tablette.exe" installer %*
echo.
pause
