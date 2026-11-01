# DCS Tablette

**Version française :** [README.md](README.md)

[![Discord: L'atelier DCS OS](https://img.shields.io/badge/Discord-L%27atelier%20DCS%20OS-5865F2?logo=discord&logoColor=white)](https://discord.gg/4KJYjt7pbc)
[![Latest release](https://img.shields.io/github/v/release/led5014/dcs-tablette?label=version)](../../releases/latest)

**Help, ideas, community**: join the **[L'atelier DCS OS](https://discord.gg/4KJYjt7pbc)**
Discord — free, French-speaking, English questions welcome. Ask for help in
#aide, request aircraft and features in #idées, and catch new releases in
#annonces.

DCS World's cockpit displays on a tablet, with their buttons under your
finger. The page adapts by itself to the aircraft you fly and to the screen
showing it: iPad, Android tablet, phone, browser on another PC.

- **Live displays**: DDIs, MFDs, MPDs… mirrored from DCS, flicker-free.
- **Touch buttons**: every press goes to the cockpit, held for as long as
  your finger stays down.
- **Per-display adjustments**, beyond what DCS offers: the knob in the
  bottom-left corner of each frame sets the brightness; tap it to open that
  display's panel — brightness, contrast, sharpness, resolution (upscaled
  and sharpened by the PC, or lightened for weak Wi-Fi) and filters: auto
  levels for a dark TGP or FLIR, black and white, inverted, green, amber,
  night red. Saved per aircraft.
- **Basic instruments for any aircraft** — warbirds, helicopters, jets:
  airspeed, attitude, altimeter, turn and slip, heading, vertical speed, G,
  RPM, plus fuel, gear, flaps… as numbers, in the cockpit's own units (mph
  and feet for a P-51, km/h and meters for a Bf 109, knots for a NATO jet).
  Enough to keep your eyes outside. Taken from DCS flight data, not from the
  module's gauges: in multiplayer, a server that forbids exporting your own
  aircraft's data turns them off, and the tablet tells you so.
- **Hornet front panel** redrawn: touch UFC, IFEI, standby instruments,
  warning lights.
- **Kneeboard**: the pages for the aircraft you fly, read straight from the
  files and sharp at any size — current mission (single or multiplayer),
  module pages, your own, the map's charts — plus the DCS kneeboard, live.
  Your choice: the DCS kneeboard key shows it on the PC as usual, or on the
  tablet, which then switches to it by itself — and in that mode, opening it
  on the tablet opens it in DCS, no keyboard needed.
- **Every screen size**: the page only offers layouts that stay comfortable
  to touch on the screen in use — one or two displays on a phone, three on a
  tablet in landscape, the whole panel on a large screen — and rearranges
  itself when you rotate it.

No Python to install, nothing over the internet in flight: the server runs
on the PC, and the iPad connects to it over your home Wi-Fi.

## Download

Latest release: **[Releases](../../releases/latest)** → `DCS-Tablette-x.y.z.zip`.

The zip contains `DCS-Tablette.exe`, `Installer.bat`, `Desinstaller.bat` and
a `README.txt` (in French: `LISEZ-MOI.txt`) covering what follows.

**Updating: nothing to do.** On launch, DCS Tablette checks whether a newer
version exists and updates itself, without asking: verified download
(SHA-256), its files replaced, restart — your settings stay, DCS can stay
open. That is its only request to the internet, at launch;
`--sans-mise-a-jour` turns it off. From 1.5.0 to 1.8.0, it asked "Mettre à jour
maintenant ?" ("Update now?"): answer O (yes) one last time. From an
older version, extract the zip over the old folder one last time.

## Aircraft

| Aircraft | Displays + buttons | Also |
|---|---|---|
| F/A-18C Hornet | Left DDI, right DDI, AMPCD | touch UFC, IFEI, standby instruments, warning lights |
| F-16C Viper | Left MFD, right MFD | — |
| AH-64D Apache | Left MPD, right MPD (+ FCR, WPN, TSD…), TEDAC (display only) | Pilot / CPG seat |
| OH-58D Kiowa | Left MFD, right MFD | — |
| A-10C / A-10C II | Left MFCD, right MFCD | — |
| AV-8B Harrier | Left MPCD, right MPCD | — |
| F-15E Strike Eagle | Left MPD, right MPD, MPCD (front seat) | — |
| JF-17 Thunder | Left, center and right MFCD (portrait, 26 buttons) | — |
| Ka-50 Black Shark II / III | Shkval (display only), ABRIS and its 5 buttons | — |
| MiG-29A Fulcrum | HDD, the HUD repeater (TACT / DUBL switch) | HDD + instruments side by side, kneeboard |
| Warbirds: P-51D, TF-51D, P-47D, F4U-1D, Spitfire IX, Mosquito, Bf 109 K-4, Fw 190 A-8 / D-9, I-16, Yak-52 | — (round-gauge cockpits) | instruments in their own units, kneeboard |
| Korea: F-86F, MiG-15bis | — | instruments, kneeboard |
| F-14, F-4E, Mirage 2000C, Mirage F1, F-5E, MiG-21bis, MiG-19P, AJS-37, L-39, C-101, MB-339, FC3 | — | instruments, kneeboard |
| CH-47F, Mi-8MTV2, Mi-24P, UH-1H, SA342 | — | helicopter instruments, kneeboard |

Any other aircraft gets the basic instruments and the kneeboard. Units on the
MiG-29A and the L-39 follow your DCS options ("Avionics Units" on the
MiG-29, avionics language on the L-39): the tablet reads `options.lua`.

The HUD itself can't be exported from any module: DCS offers no export
viewport for it. The MiG-29A is the exception, through its HDD, the small
head-down display that repeats the HUD (DUBL position) or shows the tactical
situation (TACT): the module sends it to the RIGHT_MFCD viewport of
"Tablette DCS" by itself, nothing to set up.

Button numbers for the F-16C, OH-58D, AV-8B, F-15E, JF-17 and Ka-50 come
from [DCS-BIOS](https://github.com/DCS-Skunkworks/dcs-bios) and still need
confirming in flight (especially button placement around the JF-17 and
F-15E displays): feedback is welcome.

On the Hornet, the Apache and the A-10C, each button sits right across from
the label the module draws on the display (positions read from the module's
scripts). On the F-16C and the OH-58D, the buttons are evenly spaced along
the frame: a screenshot of their MFDs would let us line them up too.

## Installation

1. Extract the zip anywhere (Downloads is fine), then double-click
   **`Installer.bat`**.
2. If Windows shows "Windows protected your PC": *More info* → *Run
   anyway*. The executable isn't signed; it is built from this repository
   (`scripts/construire_tablette.py`).
3. Answer the window's questions. It first shows your displays and your DCS
   settings, then does the rest based on what you already have. If your DCS
   monitor setup already exports the cockpit displays (real MFDs, Helios…),
   it offers to keep it: the tablet picks them up where they are.

   1. **Virtual display.** DCS draws exported displays on a monitor: without
      a second monitor, they cover your view. If there is no virtual
      display, the installer offers to install
      [Virtual Display Driver](https://github.com/VirtualDrivers/Virtual-Display-Driver)
      (free, open source; this step needs internet). Windows asks for
      administrator permission, then to confirm the driver.
      It then places it **to the right** of the main display, or **below**
      if one of your monitors already sits on the right (the DCS window must
      not cover any of your monitors), at the same resolution and refresh
      rate: nothing to set in Settings → System → Display. One of your own
      monitors is only used if you say it is an HDMI dummy plug; with no
      free spot left, it offers test mode.
   2. **Tablet scripts** in `Saved Games\DCS\Scripts`.
   3. **DCS displays**: "Tablette DCS" monitor setup, resolution spanning
      both displays, windowed. If DCS is open, the window waits for you to
      close it.

   Then it installs the program in `%LOCALAPPDATA%\Programs\DCS-Tablette`
   (for you only, no administrator rights), adds a **DCS Tablette** shortcut
   to the desktop and the Start menu, registers it in *Settings → Apps →
   Installed apps* and starts it. The folder extracted from the zip can then
   be deleted.

If a step fails, the window says which one and what to do. Each step can
also be done by hand: "Manual setup" section of `README.txt`
([source](distribution/tablette/zip/README.txt)). In short: install Virtual
Display Driver with *VDD Control*; in Settings → System → Display, "Extend
these displays", virtual display at the main display's resolution and
refresh rate, dragged to its right, top edges aligned; run `Installer.bat`
again.

### In flight

1. Launch **DCS Tablette** (desktop or Start menu): the window shows the
   address to open on the tablet (`http://192.168.x.x:8320`). On first
   launch, allow the program on **private** networks.
2. On the tablet or phone, open the address:
   - iPad, iPhone: Safari, then *Share* → *Add to Home Screen*;
   - Android: Chrome, then ⋮ → *Add to Home screen*, or the ⛶ button for
     full screen.
3. Start DCS and a mission.

Browsers: the page avoids recent features, so it also runs on iPads stuck on
an older iOS and on entry-level Android devices. Minimum: **iOS / iPadOS
13** (iPad Air 2, iPad mini 4, iPad 5th generation and later) — before that,
the buttons don't respond to touch. Tested in Chrome at common phone, tablet
and PC screen sizes; feedback on your device is welcome.

## What the installer changes

In DCS, only `Saved Games\DCS`, never the DCS install folder (the
multiplayer integrity check is not affected):

| File | Change | Backup kept |
|---|---|---|
| Windows: virtual display | installed if missing and if you accept (Virtual Display Driver 25.7.23, checksum verified, settings in `C:\VirtualDisplayDriver`); placed to the right of the main display, or below | — |
| `%LOCALAPPDATA%\DCS-Tablette\installation.json` | what you chose during installation (your setup kept, HDMI dummy display…), read back by the diagnostics | — |
| `Scripts\DCS-Tablette-Export.lua`, `Scripts\DCS-Tablette-Appareils.lua` | added | — |
| `Scripts\Export.lua` | one line added at the end; Tacview, SRS… untouched | `Export.lua.avant-tablette-<date>` |
| `Config\MonitorSetup\tablette.lua` | "Tablette DCS" monitor setup | — |
| `Config\options.lua` | monitor setup, resolution, windowed | `options.lua.avant-tablette` |
| `%LOCALAPPDATA%\Programs\DCS-Tablette` | the program (what the zip contains) | — |
| Desktop, Start menu | "DCS Tablette" shortcut | — |
| Registry, `HKCU\…\Uninstall\DCS-Tablette` | the *Installed apps* entry | — |

The Lua script only accepts commands for the buttons shown (an allowlist per
aircraft) and releases any button held for more than 5 seconds.

**Uninstall**: with DCS and DCS Tablette closed, *Settings → Apps →
Installed apps → DCS Tablette → Uninstall* (or `Desinstaller.bat` in the
program folder) removes everything, restores the previous display settings
and deletes the program — only the files the zip put there. The virtual
display stays (Device Manager → Display adapters → Virtual Display Driver →
*Uninstall device* to remove it).

## Screenshots and streaming

DCS spans the main display **and** the virtual display: its window is two
displays wide (5120 × 1440 for two 2560 × 1440 displays). Anything that
captures the whole window also shows the virtual display.

- **Screenshots**: while DCS Tablette is running, every new screenshot of the
  whole DCS window is cropped to the main display automatically, at the same
  quality — Steam's F12, *Print Screen* in DCS, *Win + Print Screen*, Game
  Bar. Region screenshots and older ones are left alone;
  `--captures-entieres` keeps them whole.
- **Streaming**: a window is always shared whole, nothing can crop it live.
  Share the main **screen**, not the application: in Discord, *Share Your
  Screen* → *Screens* tab → the main screen (not *Applications* → DCS); in
  OBS, a *Display Capture* of the main display, or a *Game Capture* with a
  *Crop/Pad* filter (right: the width of the virtual display).

## Aircraft: detected or chosen

At the top left, the **aircraft** menu: on *Auto*, the page follows the
aircraft DCS reports (the status dot turns green when DCS is talking to the
tablet). You can also pick your aircraft by hand, to set up the page before
starting the mission. If the chosen aircraft isn't the one DCS is flying,
the dot turns orange and the buttons are disabled: from one module to
another, the same number means a completely different button.

## Diagnostics

DCS Tablette checks everything the tablet needs, at launch and then every 10
seconds: DCS folder, scripts, virtual display, DCS displays and settings,
DCS running, script signal (with the last `DCS-TABLETTE` line of dcs.log),
images, PC network (Public or Private), tablet connected.

- **On the PC**: the "Checks" list in the window at launch, then every
  change, timestamped.
- **On the tablet**: tap the status dot at the top left, or the "⚠ n" badge
  that shows up when something needs attention. *Check* rechecks right away.

Each item is *OK*, *repaired*, *waiting* (DCS not running…), *action needed*
or *missing*, with the steps to follow. Anything that can be repaired safely
is repaired automatically, and you are told: scripts from an older version,
virtual display moved by a Windows update, monitor setup no longer matching
the displays, DCS switched back to full screen or to another monitor setup
(once DCS is closed: it rewrites its settings on exit). Nothing gets
installed without asking: for a missing virtual display, run
`Installer.bat`.

## Language

- **On the tablet**: the page is in French if the browser is in French, in
  English otherwise. To switch: tap the status dot at the top left (it opens
  the Diagnostics panel), then **FR** or **EN**. The choice is saved on that
  tablet: each tablet or phone keeps its own.
- **On the PC** (DCS Tablette window, installation, updates): in French if
  Windows is in French, in English otherwise. To force a language, run
  `DCS-Tablette.exe --langue en` (or `--langue fr`) once: the choice is
  saved, and `--langue auto` goes back to following Windows. The easiest
  way: *Win + R*, type
  `%LOCALAPPDATA%\Programs\DCS-Tablette\DCS-Tablette.exe --langue en` and
  press Enter. The option also works with the installer:
  `Installer.bat --langue en`.

## Common problems

First, the diagnostics above. The most frequent cases:

- **"DCS: no signal" while the displays do show up**: the images come from
  the display, but the buttons and the aircraft name go through the tablet
  script inside DCS. The diagnostics show the last `DCS-TABLETTE` line of
  `Saved Games\DCS\Logs\dcs.log`: there, the script says whether it is
  ready, which aircraft it sees, or why it can't start. No line at all: run
  `Installer.bat` again, then the mission.

- **The page won't open on the iPad**: the PC's Wi-Fi may be set to a
  *Public* network in Windows; switch it to *Private*.
- **Black displays**: restart DCS after installing (it only reads the
  monitor setup at startup) and check in Options → System → Monitors that
  "Tablette DCS" is selected.
- **The cockpit displays cover the view**: the virtual display is no longer
  where it should be (Windows or graphics driver update). DCS Tablette puts
  it back by itself; quit DCS and start it again.
- **The DCS kneeboard lands on the virtual display**: that's intended. In
  the tablet's Kneeboard tab, "DCS kneeboard on" chooses where it appears
  when you open it: *PC* (a window mirrors it at the bottom right of the
  main display) or *Tablet* (the tablet switches to it, nothing on the PC).
  If the tablet disconnects, it goes back to the PC after 10 s.
- **A stream or screenshot shows two displays side by side**: see
  [Screenshots and streaming](#screenshots-and-streaming).
- **The tablet shows an old version after an update**: from 1.2.1 on it
  reloads by itself; before that, close the app (or the tab) and reopen it.

## From source

Python 3.12, Windows.

```bat
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python.exe scripts\installer_dcs.py
.venv\Scripts\python.exe scripts\configurer_ecrans_dcs.py --second-ecran
launch_tablette.bat
```

- Tests: `set PYTHONPATH=src` then
  `.venv\Scripts\python.exe -m unittest tests.test_tablette`
- Without DCS: `scripts\simuler_dcs_tablette.py [aircraft name]` pretends to
  be the game.
- Build the zip: `.venv\Scripts\python.exe scripts\construire_tablette.py`
- Add an aircraft: one file in `src/tablette/appareils/`, then
  `scripts\generer_lua_appareils.py`.

How it works in detail, design choices and rejected approaches (in French):
[docs/tablette.md](docs/tablette.md).

---

Free and open source, under the [MIT license](LICENSE): free to use, modify
and redistribute, as long as you keep the license notice.

Community tool, not affiliated with Eagle Dynamics. DCS World is a trademark
of Eagle Dynamics SA.
