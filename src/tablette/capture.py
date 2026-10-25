"""Capture des écrans exportés de DCS, et liste des écrans de Windows.

Uniquement la bibliothèque standard (ctypes) et Pillow, déjà présent : aucune
dépendance nouvelle.

Deux façons de copier, choisies zone par zone :

- BitBlt de la zone à l'écran : 4 ms pour 480 × 480. Juste seulement si DCS
  est bien ce qu'on voit à cet endroit — on le vérifie aux coins et au
  centre avant de copier. Vu en vrai : sans cette vérification, la tablette
  recevait l'application ou la barre des tâches qui recouvrait DCS.
- PrintWindow (PW_RENDERFULLCONTENT) : Windows rend le contenu de la fenêtre
  de DCS elle-même, même masquée, et rien d'autre. Mais toute la fenêtre, à
  chaque fois : 30 ms à 2560 × 1440, le double quand DCS s'étend sur un
  second écran. Réservé aux zones recouvertes.

Sur un écran virtuel que personne ne regarde, rien ne recouvre DCS : c'est
la voie rapide en permanence.
"""
from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import wintypes
from typing import Dict, Optional, Tuple

from PIL import Image

from .copie import Copie, Rect, dans

if sys.platform == "win32":
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    # Coordonnées en pixels physiques, même si l'affichage est mis à
    # l'échelle (125 %, 150 %) : sinon la fenêtre paraîtrait plus petite
    # qu'elle n'est et les zones seraient décalées.
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        pass

    user32.GetDC.restype = wintypes.HDC
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             ctypes.c_int, wintypes.HDC, ctypes.c_int, ctypes.c_int,
                             wintypes.DWORD]
    gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT,
                                wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p,
                                wintypes.UINT]
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]

    ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [ENUM_PROC, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                                ctypes.POINTER(wintypes.DWORD)]
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4

    MONITOR_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                      ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                                           MONITOR_PROC, wintypes.LPARAM]
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]

SRCCOPY = 0x00CC0020
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PW_CLIENTONLY = 0x1
PW_RENDERFULLCONTENT = 0x2
GA_ROOT = 2
# Chercher la fenêtre parcourt toutes celles du bureau : une fois par
# seconde suffit, entre-temps on garde la même.
VALIDITE_FENETRE_S = 1.0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


def moniteurs() -> list:
    """Écrans branchés (ou virtuels) : [(x, y, largeur, hauteur, principal)]."""
    trouves = []

    def visiter(hmon, _hdc, _rect, _):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            r = info.rcMonitor
            trouves.append((r.left, r.top, r.right - r.left, r.bottom - r.top,
                            bool(info.dwFlags & 1)))
        return True

    user32.EnumDisplayMonitors(None, None, MONITOR_PROC(visiter), 0)
    return trouves


def zone_utile_principale() -> Optional[Rect]:
    """L'écran principal moins la barre des tâches : (x, y, largeur, hauteur)."""
    zones = []

    def visiter(hmon, _hdc, _rect, _):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(info)) and info.dwFlags & 1:
            r = info.rcWork
            zones.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True

    user32.EnumDisplayMonitors(None, None, MONITOR_PROC(visiter), 0)
    return zones[0] if zones else None


def _nom_exe(pid: int) -> str:
    processus = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not processus:
        return ""
    try:
        taille = wintypes.DWORD(1024)
        tampon = ctypes.create_unicode_buffer(1024)
        if kernel32.QueryFullProcessImageNameW(processus, 0, tampon, ctypes.byref(taille)):
            return os.path.basename(tampon.value).lower()
        return ""
    finally:
        kernel32.CloseHandle(processus)


def _taille_client(hwnd) -> Tuple[int, int]:
    client = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(client))
    return client.right, client.bottom


def _chercher_fenetre():
    """La plus grande fenêtre visible de DCS.exe : le processus en ouvre
    plusieurs (lanceur, console), le simulateur est la plus grande."""
    trouvees = []

    def visiter(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if _nom_exe(pid.value) != "dcs.exe":
            return True
        l, h = _taille_client(hwnd)
        if l > 0 and h > 0:
            trouvees.append((l * h, hwnd))
        return True

    user32.EnumWindows(ENUM_PROC(visiter), 0)
    return max(trouvees)[1] if trouvees else None


_fenetre = (0.0, None)          # (instant de la recherche, hwnd)


def _fenetre_dcs():
    global _fenetre
    instant, hwnd = _fenetre
    if time.monotonic() - instant > VALIDITE_FENETRE_S or not (hwnd and user32.IsWindow(hwnd)):
        hwnd = _chercher_fenetre()
        _fenetre = (time.monotonic(), hwnd)
    return hwnd


def _image_du_dc(memoire, bitmap, l: int, h: int) -> Optional[Image.Image]:
    entete = BITMAPINFOHEADER()
    entete.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    entete.biWidth = l
    entete.biHeight = -h              # négatif : lignes de haut en bas
    entete.biPlanes = 1
    entete.biBitCount = 32
    tampon = ctypes.create_string_buffer(l * h * 4)
    if not gdi32.GetDIBits(memoire, bitmap, 0, h, tampon, ctypes.byref(entete), 0):
        return None
    return Image.frombuffer("RGB", (l, h), tampon, "raw", "BGRX", 0, 1)


def _copier(l: int, h: int, dessiner) -> Optional[Image.Image]:
    """Prépare un bitmap l × h, y fait dessiner, et le rend en image."""
    ecran = user32.GetDC(None)
    memoire = gdi32.CreateCompatibleDC(ecran)
    bitmap = gdi32.CreateCompatibleBitmap(ecran, l, h)
    ancien = gdi32.SelectObject(memoire, bitmap)
    try:
        if not dessiner(memoire, ecran):
            return None
        return _image_du_dc(memoire, bitmap, l, h)
    finally:
        gdi32.SelectObject(memoire, ancien)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memoire)
        user32.ReleaseDC(None, ecran)


def _visible(hwnd, zone: Rect) -> bool:
    """DCS est-il ce qu'on voit aux quatre coins et au centre de la zone ?"""
    x, y, l, h = zone
    points = ((x + 2, y + 2), (x + l - 3, y + 2), (x + 2, y + h - 3),
              (x + l - 3, y + h - 3), (x + l // 2, y + h // 2))
    for px, py in points:
        dessus = user32.WindowFromPoint(wintypes.POINT(px, py))
        if not dessus or (user32.GetAncestor(dessus, GA_ROOT) or dessus) != hwnd:
            return False
    return True


def lancement_dcs() -> Optional[float]:
    """Heure de lancement de DCS (secondes depuis 1970), None s'il ne tourne pas.

    DCS ne lit sa configuration d'écrans qu'au lancement : un fichier modifié
    après cette heure n'est pas celui qu'il applique.
    """
    hwnd = _fenetre_dcs()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    processus = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not processus:
        return None
    try:
        temps = [wintypes.FILETIME() for _ in range(4)]
        if not kernel32.GetProcessTimes(processus, *[ctypes.byref(t) for t in temps]):
            return None
        creation = (temps[0].dwHighDateTime << 32) | temps[0].dwLowDateTime
        return (creation - 116444736000000000) / 1e7     # FILETIME → époque Unix
    finally:
        kernel32.CloseHandle(processus)


def origine_dcs() -> Optional[Tuple[int, int]]:
    """Coin haut-gauche de la zone cliente de DCS, en coordonnées écran."""
    hwnd = _fenetre_dcs()
    if not hwnd:
        return None
    origine = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origine))
    return origine.x, origine.y


def capturer_dcs(zones: Dict[str, Rect]) -> Optional[Copie]:
    """Les zones demandées, en coordonnées de la fenêtre de DCS. None si DCS
    est fermé, réduit ou illisible."""
    hwnd = _fenetre_dcs()
    if not hwnd or user32.IsIconic(hwnd):
        return None
    taille = _taille_client(hwnd)
    if taille[0] <= 0 or taille[1] <= 0:
        return None
    origine = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origine))

    voulues = {nom: z for nom, z in zones.items() if dans(z, taille)}
    images, masquees = {}, {}
    for nom, (x, y, l, h) in voulues.items():
        sx, sy = origine.x + x, origine.y + y
        if _visible(hwnd, (sx, sy, l, h)):
            images[nom] = _copier(l, h, lambda m, e, sx=sx, sy=sy, l=l, h=h:
                                  gdi32.BitBlt(m, 0, 0, l, h, e, sx, sy, SRCCOPY))
        else:
            masquees[nom] = (x, y, l, h)

    if masquees:
        fenetre = _copier(taille[0], taille[1], lambda m, _e: user32.PrintWindow(
            hwnd, m, PW_CLIENTONLY | PW_RENDERFULLCONTENT))
        if fenetre is None:
            return None
        for nom, (x, y, l, h) in masquees.items():
            images[nom] = fenetre.crop((x, y, x + l, y + h))

    if any(image is None for image in images.values()):
        return None
    return Copie(taille, images)
