@echo off
rem DCS Tablette - lance le serveur de la tablette et affiche l'adresse a
rem ouvrir sur l'iPad. Fermer cette fenetre arrete le serveur.
cd /d "%~dp0"
title DCS Tablette
set PYTHONPATH=src
.venv\Scripts\python.exe -m tablette %*

rem Le serveur ne s'arrete de lui-meme que sur une erreur (port deja pris,
rem module introuvable) : on garde la fenetre ouverte pour lire le message.
pause
