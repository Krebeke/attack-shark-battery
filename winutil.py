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
