@echo off
rem DCS Tablette - retire les scripts de DCS, remet l'affichage d'avant, retire
rem raccourcis et entree de Windows, puis efface le programme.
rem DCS ferme, sinon l'affichage reste a remettre a la main.
rem Aussi : Parametres - Applications installees - DCS Tablette - Desinstaller.
title DCS Tablette - desinstallation
cd /d "%~dp0"
"%~dp0DCS-Tablette.exe" desinstaller --attendre
