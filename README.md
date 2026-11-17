# Attack Shark Battery

Battery level of your **Attack Shark** wireless mouse, shown as digits in the Windows 10/11 tray.
Lightweight, no admin rights, works without the official driver running.

🇺🇦 **Українською: [інструкція](ІНСТРУКЦІЯ.md)** · 🇬🇧 **Full guide: [GUIDE.md](GUIDE.md)**

## Download

**[⬇ Latest release](https://github.com/Krebeke/attack-shark-battery/releases/latest)**: download
`AttackSharkBattery-Setup.exe` and run it. If Windows says "Windows protected your PC", click
**More info → Run anyway** (the app isn't code-signed).

## Features

- **Tray icon with the battery %**: Windows-style or colored digits, tooltip with charging status.
  A gray icon means the mouse is asleep, and `--` means it's off.
- **Main window**: big number, estimated time left, history graph (24 h / 7 / 30 days), CSV export.
- **Floating widget**: three sizes, resize with the mouse wheel, opacity, snaps to screen edges.
  It can stay always on top or be pinned to the desktop, supports click-through and hides in
  fullscreen games.
- **Notifications**: low battery with reminders, and "fully charged".
- **Multiple mice**: the tray shows the lowest battery, and each mouse gets its own history and alerts.
- **Mouse finder**: picks up known models automatically, or learns a new mouse from the percentage
  shown in the official app.
- **Auto-update** from GitHub Releases (SHA-256 verified, can be turned off).
- Ukrainian / English, light / dark theme, start with Windows.
- **Light on resources**: the UI thread exists only while a window is open, and polling slows down
  when you're away. Real RAM/CPU usage is shown in Settings.

## Supported mice

| Model | Connection | Status |
|---|---|---|
| Attack Shark X11 | 2.4G receiver `1D57:FA60` | ✅ Confirmed |
| Other Attack Shark models | — | Try the built-in learning wizard (Settings → Mice → Find mouse…) |

Have another model working, or not working? Open an
[issue](https://github.com/Krebeke/attack-shark-battery/issues). A USBPcap capture (`.pcapng`) helps
add a profile.

## How it works (X11)

The receiver sends an HID input report on interface 2 (usage page `0x000A`) every ~2 seconds:
`03 55 40 01 39`, where byte 4 is the battery percentage (`0x39` = 57%). A report starting with
`03 55 01` means the mouse is asleep. The app only listens and never sends commands to the mouse.

## Configuration

Settings live in `%APPDATA%\AttackSharkBattery\config.json` (along with `history.csv` and
`battery.log`). Almost everything is editable in the Settings window. Main keys:

| Key | Meaning |
|---|---|
| `vid`, `pid`, `usage_page`, `usage`, `interface_number`, `serial` | Which HID interface to read |
| `method` | `input`, `feature`, `feature_get`, `output_input` |
| `request_hex`, `response_prefix_hex`, `sleep_prefix_hex` | Request bytes, expected reply prefix, "asleep" prefix |
| `battery_byte_index`, `battery_mask`, `battery_raw_max` | Where the battery byte is |
| `charging_byte_index`, `charging_mask`, `charging_value` | Charging flag (`null` = unknown) |
| `poll_seconds`, `idle_after_seconds`, `idle_poll_seconds` | Polling and idle slowdown |
| `low_battery_percent`, `low_reminder_minutes`, `notify_full` | Notifications |
| `widget_*` | Widget mode, size, scale, opacity, snapping, click-through, fullscreen hiding |
| `extra_mice` | Additional mice (same device keys plus `name`) |
| `icon_style`, `icon_*` | Tray icon look |
| `check_updates`, `update_repo` | Auto-update |

## Building from source

Requirements: Python 3 and [Inno Setup 6](https://jrsoftware.org/isdl.php) (for the installer).

```
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python tray_battery.py          # run from source
build.bat                       # build dist\ and installer_output\AttackSharkBattery-Setup.exe
```

`find_device.py` is a console helper to list HID devices and test reading (`list`, `probe`, `listen`).

The release procedure is described in [GUIDE.md](GUIDE.md#releasing-a-new-version).

## Privacy

The only network access is the daily update check to `api.github.com` (and the download from
`github.com` when you accept an update). No data about you or your mouse is sent anywhere.

## Disclaimer

Unofficial project, not affiliated with Attack Shark.
