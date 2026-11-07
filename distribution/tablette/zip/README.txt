DCS TABLETTE — cockpit displays on your tablet
==============================================

The aircraft's displays (DDI, MFD, MPD…) show up on an iPad, an Android
tablet, a phone or a browser on another PC, with their buttons under your
finger. The page adapts by itself to the aircraft you fly in DCS and to the
size of the screen: one or two displays on a phone, three or the whole
panel on a large screen.

No Python to install. In flight, nothing goes over the internet (except,
once, the F-16 DED table, the first time the DED is shown): everything stays
on the PC and your home Wi-Fi.


INSTALLATION
------------
  1. Extract the zip anywhere: Downloads is fine, DCS Tablette then
     installs itself in the right place.
  2. Double-click "Installer.bat".
     If Windows shows "Windows protected your PC": click "More info",
     then "Run anyway".
     The executable isn't signed; the source code is on GitHub.
  3. Answer the window's questions. It starts by showing your displays and
     your DCS settings, then does the rest based on what you already
     have:

     Several displays? DCS shows on the Windows main display. It asks
     which one you want DCS on, by its number in the list of your displays
     (named by their model): Enter keeps the current main display. Another
     number, and it makes that one the Windows main display (the taskbar
     moves there too).

     Your DCS monitor setup already exports the cockpit displays (real
     MFDs, Helios, touchscreen…)?
         It offers to keep it: the tablet picks them up where they are,
         nothing is changed on your monitors or in DCS.

     1/3 Virtual display
         DCS draws the cockpit displays on a monitor: without a second
         monitor, they would cover your view. The installer sends them to
         a virtual display: invisible, nobody looks at it.
         - If there is none, it offers to install Virtual Display Driver
           (free, open source): answer O (yes). This step needs internet.
           Windows then asks:
             "Do you want to allow this app…" → Yes
             "Would you like to install this device software?" → Install
         - Then it sets it up the right way: right up against the right
           of the main display, same resolution and same refresh rate. If
           one of your monitors already sits on the right, the virtual
           display goes BELOW: DCS must never cover one of your monitors,
           it would stay black in flight. The desktop grows on that side:
           the mouse can wander off there.
           Nothing to touch in the display settings.
         - Your monitors are never used without asking: a monitor already
           next to the main one is only used if you answer that it is an
           HDMI dummy plug nobody looks at.
         - No room left (monitors on the right AND below): it offers test
           mode, or tells you which monitor to move.
         - One of your displays to the LEFT of the main one, higher or lower
           than it (or a display above the main one): DCS then opens its
           window from that display. It offers to align its top edge with
           the main display's: answer Y. Only its position changes, it stays
           on the left, and the choice is kept: if Windows offsets it again,
           DCS Tablette aligns it again, with DCS closed.
     2/3 Tablet scripts
         Two scripts copied to Saved Games\DCS\Scripts, one line added to
         Export.lua (a copy of the old one is kept next to it). Tacview,
         SRS and other tools keep working.
     3/3 DCS displays
         Selects in DCS the "Tablette DCS" monitor setup, the resolution
         that covers both displays, windowed (a copy of the original
         settings is kept alongside). If DCS is open, the window asks you
         to close it and waits.

     Then it installs the program in
     %LOCALAPPDATA%\Programs\DCS-Tablette, adds a "DCS Tablette" shortcut
     to the desktop and the Start menu, registers it in
     Settings → Apps → Installed apps, and starts it.
     The folder extracted from the zip is no longer needed: you can delete
     it.

     It also adds "DCS Tablette (écrans)" to the Windows Startup folder:
     see "At every Windows sign-in" below.
  4. If a step fails, the window says which one and what to do.
     See also "Manual setup" below: every step can be done there without
     the installer.

No virtual display wanted, just to try it out: "Installer.bat --essai"
puts the cockpit displays at the bottom of the view.

Launched directly ("DCS-Tablette.exe") without going through
"Installer.bat", DCS Tablette runs the installation first.


UPDATES
-------
Nothing to do: launch DCS Tablette as usual. On launch, it checks GitHub
for a newer version (a request of a few seconds at most, nothing if the PC
is offline). If there is one, it says what it brings, downloads it, checks
that it is the published one (SHA-256 checksum), closes, replaces its
files and restarts by itself, without asking anything — DCS can stay open.
Everything is kept: virtual display, DCS settings, shortcuts. The new
scripts are copied into DCS along the way (DCS picks them up at the next
mission), and the tablet page reloads by itself.

Up to 1.8.0, DCS Tablette asked "Mettre à jour maintenant ?" ("Update
now?"): from those versions, answer O (yes) one last time.

To never contact GitHub at all: launch "DCS-Tablette.exe
--sans-mise-a-jour". If the update fails (no internet, write-protected
folder…), the window says why and DCS Tablette starts on its current
version; the tablet's diagnostics report the new one.


IN FLIGHT
---------
  1. Launch "DCS Tablette" (desktop or Start menu). The window shows an
     address, for example http://192.168.1.20:8320
     On first launch, Windows asks whether to allow the program on the
     network: accept for PRIVATE networks.
  2. On the tablet or phone (same Wi-Fi), open that address:
     - iPad, iPhone: Safari, then Share → "Add to Home Screen";
     - Android: Chrome, then ⋮ → "Add to Home screen", or the ⛶ button
       at the top right for full screen.
     Opened from the home screen, the page takes up the whole screen.
  3. Start DCS and a mission: the page switches to the aircraft you fly.
     The menu at the top left also lets you pick your aircraft by hand,
     even before the mission. If it doesn't match the one DCS is flying,
     the status dot turns orange and the buttons are disabled.
  4. A display too dark (the F-16's TGP, for example) or too washed out:
     turn the round knob in the bottom-left corner of its frame — sliding
     your finger up or to the right brightens it. TAP the knob without
     turning it to open all of the display's settings: brightness,
     contrast, sharpness, resolution (Fine and Very fine: sharper, heavier
     on the Wi-Fi; Economy for weak Wi-Fi) and filters — "Auto levels"
     brings out a dark TGP or FLIR, "Inverted" switches to black-hot,
     "Night red" preserves your night vision. Set display by display and
     aircraft by aircraft, saved on the tablet; an amber dot on the knob
     means a setting is applied.
  5. "Instruments" (at the top): airspeed, attitude, altimeter, turn and
     slip, heading, vertical speed, G and RPM, laid out in a T as on the
     instrument panel, with fuel, gear and flaps as numbers. For ANY
     aircraft, warbirds and helicopters included, in its cockpit's units
     — it's the default view for aircraft without displays. Enough to keep
     your eyes outside: a glance at the tablet is all it takes. The MiG-29A
     and the L-39 follow the units chosen in the DCS options.
     This is DCS flight data, not the module's gauges (nor its failures,
     nor its altimeter setting). In multiplayer, some servers forbid
     exporting your own aircraft's data: the tablet says so, and the
     instruments stay empty.
  6. MiG-29A: "HDD" shows the MiG's small head-down display, which repeats
     the HUD — handy for hunting targets on the tablet. The TACT / DUBL
     button below it flips the SOURCE switch (tactical situation or HUD
     repeat). "HDD + instr." puts it next to the instruments.

DIAGNOSTICS
-----------
DCS Tablette checks everything the tablet needs, at launch and then every
10 seconds: DCS folder, scripts, virtual display, DCS displays and
settings, DCS running, script signal, images, PC network, tablet connected.

  - In the DCS Tablette window: the "Checks" list at launch, then every
    change, with the time.
  - On the tablet: tap the status dot at the top left, or the "⚠ 2" badge
    that shows up when something needs attention. "Check" rechecks right
    away.
  - Below the list, on the tablet, "Display layout": your displays, the
    DCS window, the exported displays and the kneeboard, to scale. In red,
    whatever gets in the way. A preview only: nothing is changed.

Each item says OK, FIXED, WAITING (DCS not running…), ACTION NEEDED or
MISSING, and for those last two, the steps to follow. Anything that can be
repaired safely is repaired automatically, and you are told:
  - scripts from an older version (after an update): copied again;
  - virtual display moved by a Windows or graphics driver update: put back
    in place;
  - monitor setup no longer matching the displays: rewritten;
  - display to the left of the main one but vertically offset (or above
    the main one): top-aligned with the main display, with DCS closed, if
    you agreed to it during installation (otherwise, the diagnostics tell
    you to run "Installer.bat" again);
  - DCS switched back to full screen, or to another monitor setup: set
    back, once DCS is closed (it rewrites its settings on exit).
Nothing is ever installed without asking: for a missing virtual display,
run "Installer.bat".

AT EVERY WINDOWS SIGN-IN
------------------------
On restart, an update of the virtual display driver or of Windows can
change the virtual display's resolution or position. DCS, still set for
the old layout, would then spread over one of your displays, and the
cockpit displays would no longer land on the virtual display.

To prevent this, "DCS Tablette (écrans)", in the Windows Startup folder,
puts everything back at every sign-in, before you start DCS: it waits for
the virtual display, puts it back (right of the main display, or below if
one of your displays takes the right), top-aligns again a left display that
Windows offset (if you agreed to it during installation), then sets
"Tablette DCS" and the DCS resolution. No window,
a few seconds; the displays may flicker once if something had to be put
back. It never touches DCS while it is running.

What it saw and did:
  %LOCALAPPDATA%\DCS-Tablette\ecrans.log
(the same text as the DCS Tablette "Checks" list): that's the file to send
if something goes wrong.

To do it by hand, at any time, with DCS closed: "DCS-Tablette.exe ecrans",
in the program folder. To stop running it at sign-in: Task Manager →
Startup apps → "DCS Tablette (écrans)" → Disable.

LANGUAGE
--------
  - On the tablet: the page is in French if the browser is in French, in
    English otherwise. To switch: tap the status dot at the top left (it
    opens the Diagnostics panel), then FR or EN. The choice is saved on
    that tablet: each tablet or phone keeps its own.
  - On the PC (DCS Tablette window, installation, updates): in French if
    Windows is in French, in English otherwise. To force a language, run
    "DCS-Tablette.exe --langue en" (or "--langue fr") once: the choice is
    saved, and "--langue auto" goes back to following Windows. The easiest
    way: Win + R, type
      %LOCALAPPDATA%\Programs\DCS-Tablette\DCS-Tablette.exe --langue en
    then press Enter. The option also works with
    "Installer.bat --langue en".

This guide also exists in French: LISEZ-MOI.txt.

KNEEBOARD
---------
The tablet's "Kneeboard" button shows the pages for the aircraft you fly,
read straight from the files (current mission, single or multiplayer,
module pages, your own, the map's charts), plus the DCS kneeboard, live.

In that tab, "DCS kneeboard on" chooses where it appears when you open it
in DCS (RShift+K, or holding K):
  - PC: at the bottom right of the screen, as usual;
  - Tablet: nothing on the PC, the tablet switches to it, and goes back to
    the displays when you close it. And without touching the keyboard:
    showing "DCS kneeboard (live)" on the tablet opens it in DCS, moving
    on to something else closes it.
If the tablet disconnects, it goes back to the PC after 10 seconds.

Closing the DCS Tablette window stops everything.

SCREENSHOTS AND STREAMING
-------------------------
DCS spans the main display AND the virtual display: its window is two
displays wide (5120 × 1440 for two 2560 × 1440 displays). Anything that
captures the whole window therefore also shows the virtual display.

Screenshots: while DCS Tablette is running, every new screenshot of the
whole DCS window is cropped to the main display automatically, at the same
quality — Steam's F12, Print Screen in DCS, Win + Print Screen (the whole
desktop), Win + Alt + Print Screen (Game Bar). Region screenshots
(Win + Shift + S) and older ones are left alone. To keep screenshots
whole: launch "DCS-Tablette.exe --captures-entieres".

Streaming and video: a window is always shared whole, nothing can crop it
live. Share the main SCREEN, not the application:
  - Discord: "Share Your Screen" → "Screens" tab → the main screen, not
    "Applications" → DCS (nor the Go Live offered for the game, which
    takes its window);
  - OBS: a "Display Capture" source on the main display; or a "Game
    Capture" with a "Crop/Pad" filter, right: the width of the virtual
    display (2560 for a 2560 × 1440 display);
  - Game Bar recording (Win + Alt + R) takes the whole window: use OBS
    instead.


MANUAL SETUP, IF THE INSTALLER CAN'T DO IT
------------------------------------------
The same steps as "Installer.bat", done yourself. After steps A and B, run
"Installer.bat" again: it checks and does the rest.

A. Install the virtual display
   1. Open https://github.com/VirtualDrivers/Virtual-Display-Driver/releases
      and download "VDD.Control.<version>.zip" (under "Assets").
   2. Extract the zip, run "VDD Control.exe", click "Install", accept
      Windows' prompts.
   3. Check: Device Manager → Display adapters → "Virtual Display Driver"
      is there.
   An HDMI dummy plug in the graphics card does the same thing, with
   nothing to install.

B. Place the virtual display (Settings → System → Display)
   1. At the top, click "Identify" to find out which number is the virtual
      display (the number that doesn't show up on any real monitor).
   2. In the "Multiple displays" list: "Extend these displays".
   3. Click the MAIN display and note its "Display resolution" (for
      example 2560 × 1440); in "Advanced display", note its refresh rate
      (for example 144 Hz). Check that "Make this my main display" is
      ticked for it.
   4. Click the VIRTUAL display: same resolution, same refresh rate
      ("Advanced display"). If that resolution isn't offered, pick the
      same height (1440, 1080…).
   5. Drag the virtual display right up against the RIGHT of the main one,
      TOP edges level (Windows snaps the edges: let go when they are
      aligned), then "Apply".
   If one of your monitors is already to the right of the main one, put
   the virtual display BELOW it instead, LEFT edges level. The DCS window
   must not cover any of your monitors.
   6. A display to the LEFT of the main one: TOP edges exactly level with
      the main one. Higher or lower, or a display ABOVE the main one, and
      DCS opens its window from that display.

C. Tablet scripts
   "Installer.bat" always does this, even when the rest fails.

D. Set up DCS (with DCS open, then restart it)
   Options → System:
   - "Monitors": "Tablette DCS";
   - "Resolution": what both displays cover — side by side, the sum of the
     widths (2560 × 1440 + 2560 × 1440 → 5120 × 1440); one above the
     other, the sum of the heights (→ 2560 × 2880); the "Installer.bat"
     window shows the right value;
   - "Full Screen" unticked.
   Then quit DCS and start it again: it only reads the displays at
   startup.


TROUBLESHOOTING
---------------
First, the diagnostics (see above): the DCS Tablette window, or the status
dot on the tablet. They say what is missing and how to fix it.

- The page won't open on the tablet: the PC's Wi-Fi may be set to a
  "Public" network in Windows; switch it to "Private".
- "DCS: no signal" while the displays do show up: search for DCS-TABLETTE
  in Saved Games\DCS\Logs\dcs.log; the tablet script says there whether it
  is ready, or why it can't start.
- The displays stay black: restart DCS after installing (it only reads the
  monitor setup at startup), and check in Options → System → Monitors that
  "Tablette DCS" is selected.
- The cockpit displays cover the view: the virtual display isn't where it
  should be (a Windows or graphics card update can move it). DCS Tablette
  puts it back by itself; quit DCS and start it again. If it can't, the
  diagnostics say why.
- DCS shows on another of your displays:
  - that display is to the left of the main one, higher or lower than it,
    or above the main one, in Settings → System → Display ("Identify"
    shows it): DCS then starts from it. Run "Installer.bat" again, with
    DCS closed: it offers to top-align it with the main display;
  - or it isn't the Windows main display: run "Installer.bat" again and
    give the number of the display you want DCS on;
  - or the virtual display changed resolution or position, and one of
    your displays took its place: close DCS with DCS Tablette left open,
    wait until the diagnostics say FIXED, then start DCS again — or
    restart Windows: "DCS Tablette (écrans)" puts everything back.
  Otherwise, send %LOCALAPPDATA%\DCS-Tablette\ecrans.log and a screenshot
  of Settings → System → Display.
- The mouse wanders off to the right (or downward) and disappears: it's on
  the virtual display. Bring it back to the main display.
- A stream or screenshot shows two displays side by side: see
  "Screenshots and streaming".
- The buttons don't respond on an old iPad: it needs iOS / iPadOS 13 or
  later (iPad Air 2, mini 4, 5th generation and later).


UNINSTALLING
------------
With DCS and DCS Tablette closed (otherwise the window asks and waits):
Settings → Apps → Installed apps → DCS Tablette → Uninstall (or
"Desinstaller.bat", in the program folder). It removes the Export.lua
line, the scripts, the shortcuts (Startup folder included) and the
Windows entry, puts the DCS
display settings back as they were, then deletes the program. Only the
files the zip put there are deleted: a folder where you put anything else
stays, with your files.

The virtual display stays installed (it may be useful for something
else). To remove it: Device Manager → Display adapters → "Virtual Display
Driver", right-click → "Uninstall device".


Community tool, not affiliated with Eagle Dynamics.
