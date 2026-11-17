# -*- coding: utf-8 -*-
"""Палітри світлої/темної теми для вікон (tkinter + ttk) та темний заголовок вікна."""
import ctypes

import winutil

PALETTES = {
    "light": dict(bg="#f3f3f3", fg="#1b1b1b", muted="#6b6b6b", field="#ffffff", border="#d0d0d0",
                  accent="#3b82f6", graph_bg="#ffffff", grid="#ebebeb", bar_bg="#e6e6e6",
                  bar_border="#c8c8c8", btn="#e5e5e5", btn_active="#d6d6d6"),
    "dark": dict(bg="#202124", fg="#e8e8e8", muted="#9a9a9a", field="#2b2d31", border="#3c3f44",
                 accent="#5b9dff", graph_bg="#1a1b1e", grid="#2d2f33", bar_bg="#2f3136",
                 bar_border="#44474c", btn="#35383d", btn_active="#40444a"),
}


def is_dark(setting):
    setting = str(setting).lower()
    if setting == "dark":
        return True
    if setting == "light":
        return False
    return not winutil.apps_use_light()


def apply(root, style, pal, dark):
    """Застосовує палітру до ttk-стилів і кореневого вікна."""
    root.configure(bg=pal["bg"])
    if not dark:
        try:
            style.theme_use("vista")
        except Exception:
            pass
        return
    style.theme_use("clam")
    bg, fg, field, border = pal["bg"], pal["fg"], pal["field"], pal["border"]
    style.configure(".", background=bg, foreground=fg, fieldbackground=field, bordercolor=border,
                    lightcolor=border, darkcolor=border, troughcolor=field, focuscolor=bg,
                    insertcolor=fg, selectbackground=pal["accent"], selectforeground="#ffffff")
    for name in ("TFrame", "TLabel", "TLabelframe", "TCheckbutton"):
        style.configure(name, background=bg, foreground=fg)
    style.configure("TLabelframe.Label", background=bg, foreground=fg)
    style.configure("TButton", background=pal["btn"], foreground=fg, bordercolor=border, padding=(10, 4))
    style.map("TButton",
              background=[("active", pal["btn_active"]), ("pressed", pal["btn_active"]), ("disabled", bg)],
              foreground=[("disabled", pal["muted"])])
    style.map("TCheckbutton", background=[("active", bg)], foreground=[("disabled", pal["muted"])],
              indicatorcolor=[("selected", pal["accent"]), ("!selected", field)])
    style.configure("TCombobox", fieldbackground=field, background=pal["btn"], foreground=fg,
                    arrowcolor=fg, bordercolor=border)
    style.map("TCombobox", fieldbackground=[("readonly", field)], foreground=[("readonly", fg)],
              selectbackground=[("readonly", field)], selectforeground=[("readonly", fg)])
    style.configure("TSpinbox", fieldbackground=field, background=pal["btn"], foreground=fg,
                    arrowcolor=fg, bordercolor=border)
    style.configure("TEntry", fieldbackground=field, foreground=fg, bordercolor=border)
    style.configure("Horizontal.TScale", background=bg, troughcolor=field)
    style.configure("Horizontal.TProgressbar", background=pal["accent"], troughcolor=field, bordercolor=border)
    root.option_add("*TCombobox*Listbox.background", field)
    root.option_add("*TCombobox*Listbox.foreground", fg)
    root.option_add("*TCombobox*Listbox.selectBackground", pal["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")


def dark_title_bar(win, dark):
    """Темний/світлий заголовок вікна Windows 10 (1809+) / 11."""
    try:
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        value = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (новий і старий номер)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass
