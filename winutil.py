# -*- coding: utf-8 -*-
"""Дрібні Windows-специфічні речі: автозапуск, тема панелі, список шрифтів, один екземпляр.

Усе загорнуто так, щоб модуль імпортувався і поза Windows (для тестів).
"""
import ctypes
import os
import sys

try:
    import winreg
except ImportError:  # не Windows
    winreg = None

APP_NAME = "AttackSharkBattery"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
THEME_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
FONTS_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"


# ── автозапуск ──

def autostart_command():
    if getattr(sys, "frozen", False):
        return '"%s"' % sys.executable
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pyw if os.path.exists(pyw) else sys.executable
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tray_battery.py")
    return '"%s" "%s"' % (exe, script)


def autostart_enabled():
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
        return value.strip().lower() == autostart_command().strip().lower()
    except OSError:
        return False


def set_autostart(enable):
    if winreg is None:
        return
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enable:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


# ── тема, DPI, екземпляр ──

def taskbar_is_light():
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, THEME_KEY) as key:
            return winreg.QueryValueEx(key, "SystemUsesLightTheme")[0] == 1
    except OSError:
        return False


def apps_use_light():
    """Тема застосунків Windows (для вікон програми): True = світла."""
    if winreg is None:
        return True
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, THEME_KEY) as key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 1
    except OSError:
        return True


def system_language():
    """'uk' для українського/російського інтерфейсу Windows, інакше 'en'."""
    try:
        lang = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
        return "uk" if lang in (0x22, 0x19) else "en"
    except Exception:
        return "uk"


def idle_seconds():
    """Скільки секунд у системі не було вводу (миша/клавіатура). 0 поза Windows."""
    try:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        tick = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
        return ((tick - info.dwTime) & 0xFFFFFFFF) / 1000.0
    except Exception:
        return 0.0


def process_stats():
    """(пам'ять MB, середнє навантаження CPU % від усіх ядер з моменту запуску) або None."""
    try:
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

        k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), wintypes.DWORD]
        k32.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        proc = k32.GetCurrentProcess()
        pmc = PMC()
        pmc.cb = ctypes.sizeof(pmc)
        psapi.GetProcessMemoryInfo(proc, ctypes.byref(pmc), pmc.cb)

        def ft(f):
            return ((f.dwHighDateTime << 32) | f.dwLowDateTime) / 1e7

        c, e, k, u = (wintypes.FILETIME() for _ in range(4))
        k32.GetProcessTimes(proc, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u))
        now = wintypes.FILETIME()
        k32.GetSystemTimeAsFileTime(ctypes.byref(now))
        wall = max(ft(now) - ft(c), 1.0)
        cpu = (ft(k) + ft(u)) / wall / (os.cpu_count() or 1) * 100.0
        return pmc.WorkingSetSize / 1048576.0, cpu
    except Exception:
        return None


def tray_icon_size():
    try:
        size = ctypes.windll.user32.GetSystemMetrics(49)  # SM_CXSMICON
    except Exception:
        size = 16
    return max(16, min(int(size), 64))


def set_dpi_aware():
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


_mutex = None


def single_instance():
    """False, якщо програма вже запущена."""
    global _mutex
    try:
        _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\AttackSharkBatteryTray")
        return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return True


# ── шрифти ──

FALLBACK_FONTS = [
    ("Segoe UI", "segoeui.ttf"),
    ("Segoe UI Semibold", "seguisb.ttf"),
    ("Segoe UI Bold", "segoeuib.ttf"),
    ("Segoe UI Light", "segoeuil.ttf"),
    ("Bahnschrift", "bahnschrift.ttf"),
    ("Arial Bold", "arialbd.ttf"),
    ("Consolas Bold", "consolab.ttf"),
]


def list_fonts():
    """[(назва для показу, файл або повний шлях)] — шрифти TrueType/OpenType з реєстру Windows."""
    result = {}
    if winreg is not None:
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                key = winreg.OpenKey(hive, FONTS_KEY)
            except OSError:
                continue
            with key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                    except OSError:
                        break
                    i += 1
                    if not isinstance(value, str) or not value.lower().endswith((".ttf", ".otf")):
                        continue
                    for suffix in (" (TrueType)", " (OpenType)"):
                        if name.endswith(suffix):
                            name = name[: -len(suffix)]
                    result[name] = value
    if not result:
        return list(FALLBACK_FONTS)
    return sorted(result.items(), key=lambda kv: kv[0].lower())


# ───────── віконні допоміжні функції для віджета ─────────

def virtual_screen():
    """(x, y, ширина, висота) усіх моніторів разом або None."""
    try:
        gm = ctypes.windll.user32.GetSystemMetrics
        w, h = gm(78), gm(79)
        if w <= 0 or h <= 0:
            return None
        return gm(76), gm(77), w, h
    except Exception:
        return None


def monitor_work_area(x, y):
    """(left, top, right, bottom) робочої області монітора, що містить точку (без панелі завдань) або None."""
    try:
        from ctypes import wintypes

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

        user32 = ctypes.windll.user32
        user32.MonitorFromPoint.restype = ctypes.c_void_p
        user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
        mon = user32.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 2)  # MONITOR_DEFAULTTONEAREST
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(info)
        if not mon or not user32.GetMonitorInfoW(mon, ctypes.byref(info)):
            return None
        r = info.rcWork
        return r.left, r.top, r.right, r.bottom
    except Exception:
        return None


def foreground_fullscreen():
    """True, якщо активне вікно чужої програми займає весь монітор без рамки (гра, відео на весь екран)."""
    try:
        from ctypes import wintypes

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.GetDesktopWindow.restype = ctypes.c_void_p
        user32.GetShellWindow.restype = ctypes.c_void_p
        user32.MonitorFromWindow.restype = ctypes.c_void_p
        user32.MonitorFromWindow.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
        user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.RECT)]
        user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user32.GetClassNameW.argtypes = [ctypes.c_void_p, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]

        hwnd = user32.GetForegroundWindow()
        if not hwnd or hwnd in (user32.GetDesktopWindow(), user32.GetShellWindow()):
            return False
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, cls, 64)
        if cls.value in ("Progman", "WorkerW", "Shell_TrayWnd"):
            return False
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == os.getpid():
            return False
        if (user32.GetWindowLongW(hwnd, -16) & 0xC00000) == 0xC00000:  # WS_CAPTION → звичайне вікно
            return False
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(info)
        mon = user32.MonitorFromWindow(hwnd, 2)
        if not mon or not user32.GetMonitorInfoW(mon, ctypes.byref(info)):
            return False
        m = info.rcMonitor
        return rect.left <= m.left and rect.top <= m.top and rect.right >= m.right and rect.bottom >= m.bottom
    except Exception:
        return False


def toplevel_hwnd(widget):
    """HWND вікна верхнього рівня для tkinter-віджета (або 0)."""
    try:
        widget.update_idletasks()
        hwnd = int(widget.winfo_id())
        user32 = ctypes.windll.user32
        user32.GetParent.restype = ctypes.c_void_p
        parent = user32.GetParent(hwnd)
        return int(parent or hwnd)
    except Exception:
        return 0


def send_to_bottom(hwnd):
    """Опускає вікно під усі інші (віджет «на робочому столі»), не забираючи фокус."""
    try:
        user32 = ctypes.windll.user32
        user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        return bool(user32.SetWindowPos(hwnd, 1, 0, 0, 0, 0, 0x13))  # HWND_BOTTOM, NOSIZE|NOMOVE|NOACTIVATE
    except Exception:
        return False


def set_click_through(hwnd, enable):
    """Клікі проходять крізь вікно (WS_EX_TRANSPARENT), коли enable=True. Повертає True, якщо вдалось."""
    try:
        user32 = ctypes.windll.user32
        user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
        style = user32.GetWindowLongW(hwnd, -20) | 0x80000  # WS_EX_LAYERED
        style = (style | 0x20) if enable else (style & ~0x20)
        user32.SetWindowLongW(hwnd, -20, style)
        return True
    except Exception:
        return False


# ───────── глобальні гарячі клавіші (WinAPI) ─────────

_MOD_MAP = {
    "alt": 0x0001,
    "ctrl": 0x0002,
    "control": 0x0002,
    "shift": 0x0004,
    "win": 0x0008,
}


def parse_hotkey(text):
    """Розбирає рядок типу 'Ctrl+Alt+B' у (modifiers, vk) або None, якщо порожньо/некоректно."""
    if not text or not isinstance(text, str):
        return None
    parts = [p.strip().lower() for p in text.split("+") if p.strip()]
    if not parts:
        return None
    mods = 0
    key = None
    for p in parts:
        if p in _MOD_MAP:
            mods |= _MOD_MAP[p]
        else:
            key = p
    if not key or not mods:
        return None
    if len(key) == 1 and ("a" <= key <= "z" or "0" <= key <= "9"):
        vk = ord(key.upper())
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    else:
        return None
    return mods | 0x4000, vk  # MOD_NOREPEAT


class HotkeyListener:
    """Слухає одну глобальну гарячу клавішу в окремому потоці Windows."""

    def __init__(self, callback):
        self.callback = callback
        self._thread = None
        self._tid = None
        self._spec = None

    def start(self, hotkey_text):
        self.stop()
        parsed = parse_hotkey(hotkey_text)
        if not parsed:
            return False
        self._spec = parsed
        import threading
        self._thread = threading.Thread(target=self._run, args=parsed, name="hotkey", daemon=True)
        self._thread.start()
        return True

    def stop(self):
        tid = self._tid
        self._tid = None
        if tid:
            try:
                ctypes.windll.user32.PostThreadMessageW(tid, 0x0012, 0, 0)  # WM_QUIT
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    def _run(self, mods, vk):
        try:
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            k32 = ctypes.windll.kernel32
            self._tid = k32.GetCurrentThreadId()
            if not user32.RegisterHotKey(None, 1, mods, vk):
                return
            try:
                msg = wintypes.MSG()
                while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                    if msg.message == 0x0312 and msg.wParam == 1:  # WM_HOTKEY
                        try:
                            self.callback()
                        except Exception:
                            pass
            finally:
                user32.UnregisterHotKey(None, 1)
        except Exception:
            pass


# ───────── читання заряду Bluetooth-пристроїв (Windows PnP) ─────────

def list_bluetooth_batteries():
    """Повертає [(назва_пристрою, відсоток)] для всіх підключених Bluetooth-пристроїв із рівнем заряду."""
    if os.name != "nt":
        return []
    try:
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        class DEVPROPKEY(ctypes.Structure):
            _fields_ = [("fmtid", GUID), ("pid", wintypes.ULONG)]

        class SP_DEVINFO_DATA(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("ClassGuid", GUID),
                ("DevInst", wintypes.DWORD),
                ("Reserved", ctypes.c_void_p),
            ]

        setupapi = ctypes.windll.setupapi
        setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
        setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.DWORD]
        setupapi.SetupDiEnumDeviceInfo.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(SP_DEVINFO_DATA)]
        setupapi.SetupDiGetDevicePropertyW.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA), ctypes.POINTER(DEVPROPKEY),
            ctypes.POINTER(wintypes.ULONG), ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), wintypes.DWORD,
        ]
        setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

        # DEVPKEY_Device_BatteryLevel = {104EA319-6EE2-4701-BD47-8DDBF425BBE5}, 2
        key_batt = DEVPROPKEY(
            GUID(0x104EA319, 0x6EE2, 0x4701, (ctypes.c_ubyte * 8)(0xBD, 0x47, 0x8D, 0xDB, 0xF4, 0x25, 0xBB, 0xE5)),
            2,
        )
        # DEVPKEY_NAME = {B725F130-47EF-101A-A5F1-02608C9EEBAC}, 10
        key_name = DEVPROPKEY(
            GUID(0xB725F130, 0x47EF, 0x101A, (ctypes.c_ubyte * 8)(0xA5, 0xF1, 0x02, 0x60, 0x8C, 0x9E, 0xEB, 0xAC)),
            10,
        )

        hdev = setupapi.SetupDiGetClassDevsW(None, "BTHENUM", None, 0x02 | 0x04)  # DIGCF_PRESENT | DIGCF_ALLCLASSES
        if not hdev or hdev == ctypes.c_void_p(-1).value:
            return []

        found = {}
        try:
            idx = 0
            while True:
                info = SP_DEVINFO_DATA()
                info.cbSize = ctypes.sizeof(info)
                if not setupapi.SetupDiEnumDeviceInfo(hdev, idx, ctypes.byref(info)):
                    break
                idx += 1
                ptype = wintypes.ULONG()
                batt = ctypes.c_ubyte()
                req = wintypes.DWORD()
                ok = setupapi.SetupDiGetDevicePropertyW(
                    hdev, ctypes.byref(info), ctypes.byref(key_batt),
                    ctypes.byref(ptype), ctypes.byref(batt), 1, ctypes.byref(req), 0
                )
                if not ok:
                    continue
                pct = int(batt.value)
                if not (0 <= pct <= 100):
                    continue
                buf = ctypes.create_unicode_buffer(256)
                ok_n = setupapi.SetupDiGetDevicePropertyW(
                    hdev, ctypes.byref(info), ctypes.byref(key_name),
                    ctypes.byref(ptype), buf, ctypes.sizeof(buf), ctypes.byref(req), 0
                )
                name = buf.value.strip() if ok_n and buf.value.strip() else "Bluetooth Device"
                found[name] = pct
        finally:
            setupapi.SetupDiDestroyDeviceInfoList(hdev)
        return sorted(found.items(), key=lambda kv: kv[0].lower())
    except Exception:
        return []


def read_bluetooth_battery(name_query):
    """Повертає відсоток (0..100) для Bluetooth-пристрою за назвою або None."""
    query = (name_query or "").strip().lower()
    if not query:
        return None
    for name, pct in list_bluetooth_batteries():
        if query in name.lower() or name.lower() in query:
            return pct
    return None
