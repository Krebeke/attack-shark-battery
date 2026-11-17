# Attack Shark Battery — User Guide

Shows your Attack Shark mouse battery level as digits next to the Windows clock.
Confirmed on **X11** (2.4G receiver). No administrator rights required.

> The app speaks Ukrainian and English. To switch: Settings → General → Language → English.
> Menu and button names below are given as they appear in the English interface.

---

## 1. Installation

1. Open the **Releases** page:
   https://github.com/Krebeke/attack-shark-battery/releases
2. In the latest release, download `AttackSharkBattery-Setup.exe`.
3. Run it. If Windows shows "Windows protected your PC", click
   **More info → Run anyway**. The app is not code-signed, so this warning is expected.
4. Keep "Start with Windows" checked if you want the app to start automatically.
5. A battery icon with digits appears next to the clock. If you don't see it, click the **^** arrow
   near the clock and drag the icon onto the taskbar.

To uninstall: **Settings → Apps → Attack Shark Battery → Uninstall**.

---

## 2. Using the app

### Tray icon
- **Digits**: current battery percentage.
- **Hover**: tooltip, e.g. "Attack Shark X11: 57%".
- **Left click**: main window.
- **Right click**: menu (Refresh now, Settings, Mini widget, Start with Windows, Exit).

| What you see | Meaning |
|---|---|
| A number (57) | Battery level |
| Gray number | Mouse is asleep, showing last known level |
| `--` | Mouse not found: turned off or receiver unplugged |
| `!` | Error in `config.json` |

### Main window
Large battery number, charging status, estimated time left, a history graph (24 h / 7 / 30 days)
and an **Export CSV…** button to save the history for Excel.

### Mini widget
Turn it on from the tray menu → "Mini widget", or in Settings → "Widget".
- **Drag** it with the mouse. It snaps to screen edges.
- **Mouse wheel** over the widget changes its size.
- **Double-click** opens the main window. **Right-click** opens its menu.
- **Position**: "Always on top" or "Pinned to the desktop" (stays under windows, like a desktop gadget).
- **Size**: digits only / digits + gauge / with mini graph.
- **Opacity**, hide in fullscreen games, red frame when the battery is low.
- **"Click through the widget"**: the widget ignores the mouse. You can turn this off only from the
  tray menu → "Widget: click-through".

### Notifications
- Battery below the threshold (15% by default), with a repeat reminder every 30 minutes.
- "Fully charged (100%)" when charging finishes.

### Multiple mice
Settings → **Mice** tab:
- **Add detected** adds a connected mouse of a known model.
- **Add new (learn)…** opens the wizard for any other mouse (see section 3).
- **Rename…** and **Remove** change the selected mouse.

The tray icon shows the mouse with the **lowest** battery, and the tooltip lists them all.
The main window gets a mouse selector at the top.

---

## 3. Mouse not found

1. Make sure the mouse is **on** and the receiver is plugged in. Move the mouse, then right-click
   the icon → "Refresh now".
2. Settings → Mice → **Find mouse…**:
   - **Known models**: if your mouse is listed, select it and click "Use selected".
   - **Learn**: open the official Attack Shark app and note the battery % it shows. Enter that number,
     pick the receiver and click "Start". Don't touch the mouse for 12 seconds.
     Then select the first result and click "Apply selected".
   - **Charging status**: click "Record NOT charging", put the mouse on charge, wait 3 seconds,
     then click "Record WHILE charging".
3. If learning finds nothing, your model only reports the battery when asked. In that case a
   USBPcap + Wireshark capture is needed. Open a GitHub Issue and attach the `.pcapng` file.

---

## 4. Updates

The app checks GitHub once a day. When a new version is out:
1. You get a notification, and the tray menu shows **"Update to X.Y.Z…"**.
2. Click it and confirm. The installer downloads, is verified (size + SHA-256) and installs silently,
   then the app restarts. Settings and history are kept.

To check manually: Settings → General → Updates → **Check now**.
To disable: uncheck "Check for new versions on GitHub".

Version 1.0.0 can't update itself, so you need to install a newer Setup.exe manually once.

---

## 5. Where data is stored

Folder `%APPDATA%\AttackSharkBattery\` (paste this path into the File Explorer address bar):
- `config.json`: all settings;
- `history.csv`: battery history for the last 30 days;
- `battery.log`: log file (useful if something goes wrong).

To reset settings: exit the app (icon → Exit) and delete `config.json`.
Uninstalling the app does not delete this folder.

---

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| "The app is already running" | The icon is already near the clock, maybe behind the **^** arrow |
| Always `--` | Mouse is off or it's a different model. See section 3 |
| Icon is gray | Mouse fell asleep. Move it and the level appears in a few seconds |
| Charging status "unknown" | Not learned yet. See section 3, "Charging status" |
| `--` while charging by cable | The mouse switched to wired mode and the receiver goes silent. This is normal |
| Can't see the widget | It's in "Pinned to the desktop" mode, so it's under your windows. Press Win+D |
| Widget ignores clicks | Click-through is on. Turn it off from the tray menu |
| No notifications | Windows Settings → System → Notifications: enable them and turn off Do Not Disturb |
| Windows blocks Setup.exe | "More info" → "Run anyway" |

If the problem persists, open an **Issue** on GitHub, describe it and attach `battery.log`.

---

## 7. Sharing with a friend

Send them the Releases page link (section 1) or the `AttackSharkBattery-Setup.exe` file itself.
Nothing else is needed: Python and all libraries are bundled in the installer.

---

## 8. For developers: building and releasing

### One-time setup
1. Install **Python 3** (check "Add python.exe to PATH") and **Inno Setup 6**
   (https://jrsoftware.org/isdl.php). Visual Studio is not needed.
2. Get the code: green **Code → Download ZIP** button and unzip, or `git clone`.

### Run from source (for testing)
```
cd path\to\folder
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python tray_battery.py
```

### Build the installer
Run `build.bat`. Output: `installer_output\AttackSharkBattery-Setup.exe`.

If you get **"EndUpdateResource failed… antivirus"**, run `build.bat` again, or add the project folder
to Windows Defender exclusions (Windows Security → Virus & threat protection → Manage settings →
Exclusions).

### Releasing a new version
1. Bump the number in `version.py`, e.g. `VERSION = "1.2.2"`.
2. Run `build.bat`.
3. On GitHub: **Releases → Draft a new release**.
   - **Choose a tag**: type `v1.2.2` (with a `v`, same number) → "Create new tag on publish".
   - Add a title and a short description of the changes.
   - Drag `installer_output\AttackSharkBattery-Setup.exe` into the attachments area.
   - **Publish release**.
4. Within a day, every installed copy will offer the update.

The file name must end with `Setup.exe`, and the release must not be a draft or pre-release.
Otherwise the app won't see it.

### Project files
| File | Purpose |
|---|---|
| `tray_battery.py` | Entry point: tray icon, menu, notifications |
| `service.py` | Background polling of the mice |
| `hidreader.py` | Reading battery over HID, `config.json` handling |
| `detect.py` | Known models, learning, auto-detection |
| `ui.py` | All windows and the widget |
| `history.py` | Battery history, CSV export |
| `updater.py`, `version.py` | Auto-update, version number |
| `iconrender.py`, `theme.py`, `i18n.py`, `winutil.py`, `uimanager.py` | Icon drawing, theme, translations, Windows helpers |
| `find_device.py` | Console tool: list HID devices, test reading |
| `build.bat`, `installer.iss` | Building the .exe and the installer |

Technical details (`config.json` keys, X11 protocol) are in [README.md](README.md).
