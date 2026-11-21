# -*- coding: utf-8 -*-
"""Вікна програми (tkinter). Виконується лише в потоці інтерфейсу (див. uimanager.py).

Точки входу для UiManager.call(name, ...): open_main, open_settings, open_wizard,
sync_widget, update.
"""
import os
import threading
import time
import urllib.parse
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk

import detect
import hidreader as hr
import history
import iconrender
import theme
import version
import winutil
from i18n import set_language, t
from service import EMPTY

FONT = "Segoe UI"


def hexcolor(rgb):
    return "#%02x%02x%02x" % tuple(rgb)


def fmt_hours(hours):
    if hours is None:
        return "—"
    if hours >= 48:
        return "≈ " + t("unit_d", "%.1f" % (hours / 24.0))
    if hours >= 1:
        return "≈ " + t("unit_h", round(hours))
    return "≈ " + t("unit_m", max(1, round(hours * 60)))


def _cfg():
    try:
        return hr.load_config()
    except hr.ConfigError:
        return dict(hr.DEFAULT_CONFIG)


def status_text(state):
    if state.ok:
        if state.charging is None:
            return t("status_unknown")
        return t("status_charging") if state.charging else t("status_not_charging")
    if state.error == "asleep":
        return t("status_asleep")
    if state.error == "config":
        return t("status_config")
    return t("status_off")


# ═════════════════════════ точки входу ═════════════════════════

def setup_root(mgr):
    cfg = _cfg()
    set_language(cfg.get("language", "auto"))
    mgr.dark = theme.is_dark(cfg.get("window_theme", "auto"))
    mgr.pal = theme.PALETTES["dark" if mgr.dark else "light"]
    root = tk.Tk()
    root.withdraw()
    theme.apply(root, ttk.Style(root), mgr.pal, mgr.dark)
    mgr.root = root


def reload_theme(mgr):
    """Перечитує мову/тему і перебудовує відкриті головне вікно та віджет."""
    cfg = _cfg()
    set_language(cfg.get("language", "auto"))
    mgr.dark = theme.is_dark(cfg.get("window_theme", "auto"))
    mgr.pal = theme.PALETTES["dark" if mgr.dark else "light"]
    theme.apply(mgr.root, ttk.Style(mgr.root), mgr.pal, mgr.dark)
    had_main = "main" in mgr.windows
    had_widget = "widget" in mgr.windows
    for name in ("main", "widget"):
        win = mgr.windows.get(name)
        if win:
            win.destroy()
    if had_main:
        open_main(mgr)
    if had_widget or cfg.get("widget_enabled"):
        sync_widget(mgr)


def open_main(mgr):
    win = mgr.windows.get("main")
    if win is not None:
        win.show()
        return
    win = MainWindow(mgr)
    mgr.windows["main"] = win
    win.show()


def open_settings(mgr):
    win = mgr.windows.get("settings")
    if win is not None:
        win.win.lift()
        return
    mgr.windows["settings"] = SettingsWindow(mgr)


def open_wizard(mgr, parent=None, target=0):
    """target: 0 — основна мишка, k — k-та додаткова, -1 — нова мишка."""
    win = mgr.windows.get("wizard")
    if win is not None:
        win.top.lift()
        return
    mgr.windows["wizard"] = WizardWindow(mgr, parent or mgr.root, target)


def sync_widget(mgr):
    enabled = bool(_cfg().get("widget_enabled"))
    win = mgr.windows.get("widget")
    if enabled and win is None:
        mgr.windows["widget"] = MiniWidget(mgr)
    elif not enabled and win is not None:
        win.destroy()
    elif win is not None:
        win.apply_config()


def confirm_update(mgr, info):
    notes = info.get("notes") or ""
    if messagebox.askyesno(t("upd_title"), t("upd_confirm", info["version"], version.VERSION, notes),
                           parent=mgr.root):
        mgr.app.apply_update(info)


def current_results(mgr, cfg=None):
    """Останні результати опитування; якщо їх ще нема — одна порожня мишка."""
    results = list(getattr(mgr.app.service, "results", None) or [])
    if not results:
        results = [(dict(cfg or _cfg(), _id=0), EMPTY)]
    return results


def update(mgr, results, cfg):
    for name in ("main", "widget"):
        win = mgr.windows.get(name)
        if win is not None:
            try:
                win.update_state(results, cfg)
            except tk.TclError:
                mgr.windows.pop(name, None)


# ═════════════════════════ головне вікно ═════════════════════════

class MainWindow:
    RANGES = [("range_24h", 1), ("range_7d", 7), ("range_30d", 30)]

    def __init__(self, mgr):
        self.mgr = mgr
        self.app = mgr.app
        self.pal = mgr.pal
        self.win = tk.Toplevel(mgr.root)
        self.win.title(t("main_title"))
        self.win.geometry("640x580")
        self.win.minsize(520, 480)
        self.win.configure(bg=self.pal["bg"])
        self.win.protocol("WM_DELETE_WINDOW", self.destroy)
        theme.dark_title_bar(self.win, mgr.dark)
        self._percent = None
        self._dev = 0
        self.sel = 0
        self.results = []
        self._build()
        self.update_state(current_results(mgr), self.app.service.cfg)

    def _build(self):
        pal = self.pal
        root = ttk.Frame(self.win, padding=16)
        root.pack(fill="both", expand=True)

        self.model = ttk.Label(root, text="Attack Shark", font=(FONT, 13, "bold"))
        self.model.pack(anchor="w")

        self.sel_frame = ttk.Frame(root)  # з'являється, лише коли мишок більше однієї
        ttk.Label(self.sel_frame, text=t("lbl_mouse")).pack(side="left")
        self.sel_var = tk.StringVar()
        self.sel_combo = ttk.Combobox(self.sel_frame, textvariable=self.sel_var, state="readonly", width=34)
        self.sel_combo.pack(side="left", padx=6)
        self.sel_combo.bind("<<ComboboxSelected>>", self._on_select)

        top = ttk.Frame(root)
        top.pack(fill="x", pady=(6, 0))
        self.big = tk.Label(top, text="--", font=(FONT, 56, "bold"), bg=pal["bg"], anchor="w", width=4)
        self.big.pack(side="left")
        info = ttk.Frame(top)
        info.pack(side="left", fill="x", expand=True, padx=(12, 0))
        self.status = ttk.Label(info, text="", font=(FONT, 12), wraplength=340, justify="left")
        self.status.pack(anchor="w", pady=(14, 2))
        self.left = ttk.Label(info, text="", font=(FONT, 10))
        self.left.pack(anchor="w")
        self.stats_lbl = ttk.Label(info, text="", font=(FONT, 9), foreground=pal["muted"])
        self.stats_lbl.pack(anchor="w", pady=(1, 0))
        self.updated = ttk.Label(info, text="", font=(FONT, 9), foreground=pal["muted"])
        self.updated.pack(anchor="w", pady=(2, 0))

        self.bar = tk.Canvas(root, height=16, highlightthickness=0, bg=pal["bg"])
        self.bar.pack(fill="x", pady=(6, 12))
        self.bar.bind("<Configure>", lambda e: self._draw_bar())

        head = ttk.Frame(root)
        head.pack(fill="x")
        ttk.Label(head, text=t("history"), font=(FONT, 10, "bold")).pack(side="left")
        self.range_var = tk.StringVar(value=t(self.RANGES[1][0]))
        combo = ttk.Combobox(head, textvariable=self.range_var, state="readonly", width=12,
                             values=[t(k) for k, _ in self.RANGES])
        combo.pack(side="right")
        combo.bind("<<ComboboxSelected>>", lambda e: self.redraw_graph())

        self.graph = tk.Canvas(root, bg=pal["graph_bg"], highlightthickness=1,
                               highlightbackground=pal["border"])
        self.graph.pack(fill="both", expand=True, pady=(6, 4))
        self.graph.bind("<Configure>", lambda e: self.redraw_graph())
        ttk.Label(root, text=t("legend"), font=(FONT, 8), foreground=pal["muted"]).pack(anchor="w")

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text=t("btn_refresh"), command=self.app.service.refresh).pack(side="left")
        ttk.Button(buttons, text=t("btn_settings"),
                   command=lambda: open_settings(self.mgr)).pack(side="left", padx=8)
        ttk.Button(buttons, text=t("btn_export"), command=self.export).pack(side="left")
        ttk.Button(buttons, text=t("btn_close"), command=self.destroy).pack(side="right")
        credit = ttk.Label(
            buttons,
            text=f"by {version.AUTHOR}",
            foreground=self.pal["muted"],
            font=(FONT, 8),
            cursor="hand2",
        )
        credit.pack(side="right", padx=(0, 12))
        credit.bind("<Button-1>", lambda e: webbrowser.open(version.GITHUB_URL))

    # --- керування вікном ---
    def show(self):
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()
        self.redraw_graph()

    def destroy(self):
        self.mgr.windows.pop("main", None)
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def export(self):
        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile="attack_shark_history.csv")
        if not path:
            return
        try:
            names = {d["_id"]: hr.device_name(d) for d, _ in self.results}
            rows = history.export_csv(path, names=names)
            messagebox.showinfo(t("main_title"), t("export_done", rows), parent=self.win)
        except OSError as e:
            messagebox.showerror(t("main_title"), t("export_error", e), parent=self.win)

    # --- дані ---
    def _on_select(self, _evt=None):
        names = [hr.device_name(d) for d, _ in self.results]
        try:
            self.sel = names.index(self.sel_var.get())
        except ValueError:
            self.sel = 0
        self.update_state(self.results, _cfg())

    def update_state(self, results, cfg):
        self.results = results
        self.sel = max(0, min(self.sel, len(results) - 1))
        if len(results) > 1:
            names = [hr.device_name(d) for d, _ in results]
            self.sel_combo.config(values=names)
            self.sel_var.set(names[self.sel])
            if not self.sel_frame.winfo_ismapped():
                self.sel_frame.pack(anchor="w", pady=(4, 0), after=self.model)
        elif self.sel_frame.winfo_ismapped():
            self.sel_frame.pack_forget()
        dcfg, state = results[self.sel]
        self._dev = dcfg["_id"]
        self.model.config(text=hr.device_name(dcfg))
        percent = state.percent
        if state.ok:
            color = iconrender.status_color(percent)
        elif state.error == "asleep" and percent is not None:
            color = iconrender.GRAY
        else:
            percent, color = None, iconrender.GRAY
        self._percent = percent
        self._bar_color = color
        self.big.config(text="--" if percent is None else str(percent), fg=hexcolor(color))
        self.status.config(text=status_text(state))
        if state.ts:
            self.updated.config(text=t("updated", time.strftime("%H:%M:%S", time.localtime(state.ts))))
        samples_2d = history.load(2, device=self._dev)
        left = history.estimate_hours_left(samples_2d) if state.ok else None
        self.left.config(text=t("left", fmt_hours(left)))
        st_info = history.stats(history.load(30, device=self._dev))
        rate_s = t("stats_rate", "%.1f" % st_info["drain_per_hour"]) if st_info["drain_per_hour"] else "—"
        ago_s = t("stats_ago", fmt_hours(st_info["last_full_hours"]).lstrip("≈ ")) if st_info["last_full_hours"] is not None else "—"
        self.stats_lbl.config(text=t("stats_line", rate_s, ago_s))
        self._draw_bar()
        self.redraw_graph()

    def _draw_bar(self):
        c, pal = self.bar, self.pal
        c.delete("all")
        w = max(c.winfo_width(), 50)
        c.create_rectangle(0, 0, w - 1, 15, outline=pal["bar_border"], fill=pal["bar_bg"])
        if self._percent is not None:
            c.create_rectangle(1, 1, 1 + (w - 3) * self._percent / 100.0, 14, outline="",
                               fill=hexcolor(self._bar_color))

    def redraw_graph(self):
        c, pal = self.graph, self.pal
        c.delete("all")
        w, h = max(c.winfo_width(), 200), max(c.winfo_height(), 120)
        days = dict((t(k), d) for k, d in self.RANGES)[self.range_var.get()]
        now = time.time()
        t0 = now - days * 86400
        left, right, top, bottom = 40, 12, 12, 28
        pw, ph = w - left - right, h - top - bottom

        def X(ts):
            return left + (ts - t0) / (now - t0) * pw

        def Y(p):
            return top + (100 - p) / 100.0 * ph

        for p in (0, 25, 50, 75, 100):
            y = Y(p)
            c.create_line(left, y, w - right, y, fill=pal["grid"])
            c.create_text(left - 6, y, text=str(p), anchor="e", fill=pal["muted"], font=(FONT, 8))
        for i in range(5):
            ts = t0 + (now - t0) * i / 4.0
            fmt = "%H:%M" if days == 1 else "%d.%m"
            c.create_text(X(ts), h - bottom + 8, text=time.strftime(fmt, time.localtime(ts)),
                          anchor="n", fill=pal["muted"], font=(FONT, 8))

        samples = history.load(days, now, device=self._dev)
        if not samples:
            c.create_text(w / 2, h / 2, text=t("no_history"), fill=pal["muted"], font=(FONT, 10))
            return
        prev = None
        for s in samples:
            if prev is not None and s[0] - prev[0] <= 6 * 3600:
                color = "#2ecc71" if (s[2] or prev[2]) else pal["accent"]
                c.create_line(X(prev[0]), Y(prev[1]), X(s[0]), Y(s[1]), fill=color, width=2)
            prev = s
        last = samples[-1]
        c.create_oval(X(last[0]) - 3, Y(last[1]) - 3, X(last[0]) + 3, Y(last[1]) + 3,
                      fill=pal["accent"], outline="")


# ═════════════════════════ міні-віджет ═════════════════════════

WIDGET_MODES = [("wmode_top", "top"), ("wmode_desktop", "desktop")]
WIDGET_SIZES = [("wsize_compact", "compact"), ("wsize_bar", "bar"), ("wsize_graph", "graph")]


def _clampf(value, lo, hi, default):
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return default


class MiniWidget:
    """Плаваюча панель поверх екрана: одна мишка або кілька, три розміри, масштаб колесом,
    прозорість, прилипання до країв, «крізь клік», автоприховування в повноекранних програмах."""

    def __init__(self, mgr):
        self.mgr = mgr
        self.app = mgr.app
        self.cfg = _cfg()
        self.results = current_results(mgr, self.cfg)
        self.hidden = False
        self._after = None
        self._dx = self._dy = 0
        self.rows = []
        self.scale = 1.0
        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", self._on_top())

        self.menu = tk.Menu(self.win, tearoff=0)
        self.menu.add_command(label=t("w_open"), command=lambda: open_main(self.mgr))
        self.menu.add_command(label=t("btn_refresh"), command=self.app.service.refresh)
        self.menu.add_command(label=t("w_click"), command=self.enable_click_through)
        self.menu.add_separator()
        self.menu.add_command(label=t("w_close"), command=self.disable)

        self._build()
        x, y = self.cfg.get("widget_x"), self.cfg.get("widget_y")
        if x is None or y is None:
            l, tp, r, b = self._bounds()
            x, y = r - self.win.winfo_reqwidth() - 24, b - self.win.winfo_reqheight() - 80
        self._place(x, y)
        self._apply_flags()
        self._tick()

    def _on_top(self):
        return str(self.cfg.get("widget_mode", "top")).lower() != "desktop"

    def _lower(self):
        """У режимі «на робочому столі» тримає віджет під усіма вікнами."""
        if not self._on_top():
            hwnd = winutil.toplevel_hwnd(self.win)
            if hwnd:
                winutil.send_to_bottom(hwnd)

    # --- геометрія ---
    def _bounds(self):
        vs = winutil.virtual_screen()
        if vs:
            return vs[0], vs[1], vs[0] + vs[2], vs[1] + vs[3]
        return 0, 0, self.win.winfo_screenwidth(), self.win.winfo_screenheight()

    def _place(self, x, y):
        self.win.update_idletasks()
        l, tp, r, b = self._bounds()
        w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        x = max(l, min(int(x), r - w))
        y = max(tp, min(int(y), b - h))
        self.win.geometry("+%d+%d" % (x, y))

    def _snap(self):
        if not self.cfg.get("widget_snap", True):
            return
        self.win.update_idletasks()
        x, y = self.win.winfo_x(), self.win.winfo_y()
        w, h = self.win.winfo_width(), self.win.winfo_height()
        area = winutil.monitor_work_area(x + w // 2, y + h // 2)
        if not area:
            area = (0, 0, self.win.winfo_screenwidth(), self.win.winfo_screenheight())
        l, tp, r, b = area
        thr, margin = 24, 8
        if abs(x - l) <= thr:
            x = l + margin
        elif abs(r - (x + w)) <= thr:
            x = r - w - margin
        if abs(y - tp) <= thr:
            y = tp + margin
        elif abs(b - (y + h)) <= thr:
            y = b - h - margin
        self.win.geometry("+%d+%d" % (x, y))

    # --- побудова ---
    def _build(self):
        pal = self.mgr.pal
        cfg = self.cfg
        for child in self.win.winfo_children():
            child.destroy()
        size = str(cfg.get("widget_size", "bar")).lower()
        if size not in ("compact", "bar", "graph"):
            size = "bar"
        sc = _clampf(cfg.get("widget_scale", 1.0), 0.7, 2.5, 1.0)
        self.scale, self.size = sc, size
        multi = len(self.results) > 1
        self.win.configure(bg=pal["border"])
        inner = tk.Frame(self.win, bg=pal["bg"], padx=int(10 * sc), pady=int(6 * sc))
        inner.pack(padx=2, pady=2)

        small = (FONT, max(7, int(8 * sc)))
        self.rows = []
        for i, (dcfg, _) in enumerate(self.results):
            row = tk.Frame(inner, bg=pal["bg"])
            row.pack(anchor="w", pady=(0 if i == 0 else int(6 * sc), 0))
            w = {"id": dcfg["_id"]}
            w["pct"] = tk.Label(row, text="--", font=(FONT, max(9, int(22 * sc)), "bold"),
                                bg=pal["bg"], fg=pal["fg"])
            w["pct"].pack(side="left")
            if size != "compact" or multi:
                right = tk.Frame(row, bg=pal["bg"])
                right.pack(side="left", padx=(int(8 * sc), 0))
                w["name"] = tk.Label(right, text="", font=small, bg=pal["bg"], fg=pal["muted"], anchor="w")
                w["name"].pack(anchor="w")
                if size != "compact":
                    w["bar_w"], w["bar_h"] = int(72 * sc), max(4, int(6 * sc))
                    w["bar"] = tk.Canvas(right, width=w["bar_w"], height=w["bar_h"], bg=pal["bar_bg"],
                                         highlightthickness=0)
                    w["bar"].pack(anchor="w", pady=2)
                    w["sub"] = tk.Label(right, text="", font=small, bg=pal["bg"], fg=pal["muted"], anchor="w")
                    w["sub"].pack(anchor="w")
            if size == "graph":
                w["gw"], w["gh"] = int(120 * sc), int(34 * sc)
                w["graph"] = tk.Canvas(row, width=w["gw"], height=w["gh"], bg=pal["graph_bg"],
                                       highlightthickness=1, highlightbackground=pal["border"])
                w["graph"].pack(side="left", padx=(int(8 * sc), 0))
            self.rows.append(w)
        self._bind_all(self.win)
        self._paint()

    def _bind_all(self, widget):
        widget.bind("<ButtonPress-1>", self._press)
        widget.bind("<B1-Motion>", self._drag)
        widget.bind("<ButtonRelease-1>", self._release)
        widget.bind("<Double-Button-1>", lambda e: open_main(self.mgr))
        widget.bind("<Button-3>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))
        widget.bind("<MouseWheel>", self._wheel)
        for child in widget.winfo_children():
            self._bind_all(child)

    def _apply_flags(self):
        alpha = min(0.99, _clampf(self.cfg.get("widget_opacity", 0.93), 0.3, 1.0, 0.93))
        try:
            self.win.attributes("-alpha", alpha)
        except tk.TclError:
            pass
        try:
            self.win.attributes("-topmost", self._on_top())
        except tk.TclError:
            pass
        hwnd = winutil.toplevel_hwnd(self.win)
        if hwnd:
            winutil.set_click_through(hwnd, bool(self.cfg.get("widget_clickthrough")))
        self._lower()

    def apply_config(self):
        """Перечитує налаштування (з меню значка чи вікна налаштувань) і перебудовує віджет."""
        self.cfg = _cfg()
        self.results = current_results(self.mgr, self.cfg)
        self._build()
        self._place(self.win.winfo_x(), self.win.winfo_y())
        self._apply_flags()

    # --- малювання ---
    def _paint(self):
        cfg, pal = self.cfg, self.mgr.pal
        threshold = hr.to_int(cfg.get("low_battery_percent"), 15)
        red_low = bool(cfg.get("widget_red_low", True))
        any_low = False
        for w, (dcfg, state) in zip(self.rows, self.results):
            percent = state.percent
            if state.ok:
                color = iconrender.status_color(percent)
            elif state.error == "asleep" and percent is not None:
                color = iconrender.GRAY
            else:
                percent, color = None, iconrender.GRAY
            low = state.ok and state.charging is not True and percent is not None and percent < threshold
            if low and red_low:
                color, any_low = iconrender.RED, True
            text = "--" if percent is None else str(percent)
            if self.size == "compact" and state.ok and state.charging:
                text += " ⚡"
            w["pct"].config(text=text, fg=hexcolor(color))
            if "name" in w:
                w["name"].config(text=hr.device_name(dcfg))
            if "bar" in w:
                bar = w["bar"]
                bar.delete("all")
                if percent is not None:
                    bar.create_rectangle(0, 0, w["bar_w"] * percent / 100.0, w["bar_h"], outline="",
                                         fill=hexcolor(color))
            if "sub" in w:
                if state.ok:
                    sub = "⚡ " + t("tip_charging") if state.charging else ""
                elif state.error == "asleep":
                    sub = "z z z"
                else:
                    sub = t("tip_not_found")
                w["sub"].config(text=sub)
            if "graph" in w:
                self._draw_graph(w, dcfg["_id"], state.ok and state.charging is True)
        self.win.configure(bg=hexcolor(iconrender.RED) if any_low and red_low else pal["border"])

    def _draw_graph(self, w, device, charging):
        c, pal = w["graph"], self.mgr.pal
        c.delete("all")
        gw, gh = w["gw"], w["gh"]
        now = time.time()
        t0 = now - 86400
        samples = history.load(1, now, device=device)
        for p in (20, 50, 80):  # тонкі лінії-орієнтири
            y = 3 + (100 - p) / 100.0 * (gh - 6)
            c.create_line(0, y, gw, y, fill=pal["grid"])
        if len(samples) < 2:
            return
        pts = []
        prev = None
        for ts, pct, ch in samples:
            x = (ts - t0) / (now - t0) * (gw - 2) + 1
            y = 3 + (100 - pct) / 100.0 * (gh - 6)
            if prev is not None and ts - prev <= 3 * 3600:
                pts.append((x, y))
            else:
                if len(pts) >= 2:
                    c.create_line(*[v for p in pts for v in p], fill=pal["accent"], width=2)
                pts = [(x, y)]
            prev = ts
        if len(pts) >= 2:
            c.create_line(*[v for p in pts for v in p], fill="#2ecc71" if charging else pal["accent"], width=2)

    # --- події ---
    def _press(self, e):
        self._dx, self._dy = e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y()

    def _drag(self, e):
        self._place(e.x_root - self._dx, e.y_root - self._dy)

    def _release(self, e):
        self._snap()
        self._lower()
        try:
            hr.save_config({"widget_x": self.win.winfo_x(), "widget_y": self.win.winfo_y()})
        except OSError:
            pass

    def _wheel(self, e):
        scale = round(_clampf(self.scale + (0.1 if e.delta > 0 else -0.1), 0.7, 2.5, 1.0), 2)
        if abs(scale - self.scale) < 0.01:
            return
        try:
            hr.save_config({"widget_scale": scale})
        except OSError:
            return
        self.cfg = _cfg()
        self._build()
        self._place(self.win.winfo_x(), self.win.winfo_y())
        self._snap()

    def _tick(self):
        """Кожні 2 с: ховає віджет у повноекранних програмах і не дає іншим вікнам його перекрити."""
        try:
            if not self._on_top():       # на робочому столі: лише тримаємо внизу, ховати не треба
                if self.hidden:
                    self.win.deiconify()
                    self.hidden = False
                self._lower()
                self._after = self.win.after(2000, self._tick)
                return
            fs = bool(self.cfg.get("widget_hide_fullscreen", True)) and winutil.foreground_fullscreen()
            if fs and not self.hidden:
                self.win.withdraw()
                self.hidden = True
            elif not fs:
                if self.hidden:
                    self.win.deiconify()
                    self.hidden = False
                self.win.attributes("-topmost", True)
            self._after = self.win.after(2000, self._tick)
        except tk.TclError:
            pass

    def enable_click_through(self):
        try:
            hr.save_config({"widget_clickthrough": True})
        except OSError:
            return
        self.cfg = _cfg()
        self._apply_flags()

    def disable(self):
        try:
            hr.save_config({"widget_enabled": False})
        except OSError:
            pass
        self.destroy()

    def destroy(self):
        self.mgr.windows.pop("widget", None)
        try:
            if self._after:
                self.win.after_cancel(self._after)
            self.win.destroy()
        except tk.TclError:
            pass

    def update_state(self, results, cfg):
        self.cfg = cfg
        old = [w["id"] for w in self.rows]
        self.results = results
        if old != [d["_id"] for d, _ in results]:
            self._build()
            self._place(self.win.winfo_x(), self.win.winfo_y())
        else:
            self._paint()


# ═════════════════════════ налаштування ═════════════════════════

STYLE_KEYS = [("style_windows", "windows"), ("style_colored", "colored")]
COLOR_KEYS = [("color_theme", "theme"), ("color_status", "status")]
LANG_KEYS = [("lang_auto", "auto"), ("lang_uk", "uk"), ("lang_en", "en")]
THEME_KEYS = [("theme_auto", "auto"), ("theme_light", "light"), ("theme_dark", "dark")]


def _label_for(options, value, default=0):
    for key, v in options:
        if v == value:
            return t(key)
    return t(options[default][0])


def _value_for(options, label):
    for key, v in options:
        if t(key) == label:
            return v
    return options[0][1]


class SettingsWindow:
    def __init__(self, mgr):
        self.mgr = mgr
        self.app = mgr.app
        self.pal = mgr.pal
        self.cfg = _cfg()
        self.win = tk.Toplevel(mgr.root)
        self.win.title(t("set_title"))
        self.win.resizable(False, False)
        self.win.configure(bg=self.pal["bg"])
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        theme.dark_title_bar(self.win, mgr.dark)
        self.previews = []
        self._after = None
        self._build()
        self._preview()
        self._tick()

    def _build(self):
        cfg = self.cfg
        style = iconrender.icon_style(cfg)
        self.fonts = winutil.list_fonts()
        self.font_map = dict(self.fonts)
        cur = str(style["icon_font"])
        cur_name = next((n for n, f in self.fonts
                         if f.lower() == cur.lower() or os.path.basename(f).lower() == cur.lower()), None)
        if cur_name is None:
            self.font_map[cur] = cur
            cur_name = cur

        pad = dict(padx=8, pady=3)
        outer = ttk.Frame(self.win, padding=12)
        outer.pack(fill="both", expand=True)
        nb = ttk.Notebook(outer)
        nb.pack(fill="both", expand=True)

        def tab(key):
            frame = ttk.Frame(nb, padding=8)
            nb.add(frame, text=t(key))
            return frame

        tab_icon, tab_work = tab("tab_icon"), tab("tab_work")
        tab_widget, tab_mice = tab("tab_widget"), tab("tab_mice")

        # --- вигляд ---
        box = ttk.LabelFrame(tab_icon, text=t("grp_icon"), padding=8)
        box.pack(fill="x")

        ttk.Label(box, text=t("lbl_style")).grid(row=0, column=0, sticky="w", **pad)
        self.style_var = tk.StringVar(value=_label_for(STYLE_KEYS, str(cfg.get("icon_style", "windows")).lower()))
        c1 = ttk.Combobox(box, textvariable=self.style_var, state="readonly", width=36,
                          values=[t(k) for k, _ in STYLE_KEYS])
        c1.grid(row=0, column=1, sticky="w", **pad)
        c1.bind("<<ComboboxSelected>>", self._on_style)

        ttk.Label(box, text=t("lbl_font")).grid(row=1, column=0, sticky="w", **pad)
        self.font_var = tk.StringVar(value=cur_name)
        c2 = ttk.Combobox(box, textvariable=self.font_var, state="readonly", width=36,
                          values=[n for n, _ in self.fonts])
        c2.grid(row=1, column=1, sticky="w", **pad)
        c2.bind("<<ComboboxSelected>>", lambda e: self._preview())

        ttk.Label(box, text=t("lbl_color")).grid(row=2, column=0, sticky="w", **pad)
        self.color_var = tk.StringVar(value=_label_for(COLOR_KEYS, str(style["icon_color_mode"]).lower()))
        c3 = ttk.Combobox(box, textvariable=self.color_var, state="readonly", width=36,
                          values=[t(k) for k, _ in COLOR_KEYS])
        c3.grid(row=2, column=1, sticky="w", **pad)
        c3.bind("<<ComboboxSelected>>", lambda e: self._preview())

        self.outline_var = tk.BooleanVar(value=bool(style["icon_outline"]))
        ttk.Checkbutton(box, text=t("chk_outline"), variable=self.outline_var,
                        command=self._preview).grid(row=3, column=1, sticky="w", **pad)
        self.red_var = tk.BooleanVar(value=bool(style["icon_red_when_low"]))
        ttk.Checkbutton(box, text=t("chk_red"), variable=self.red_var,
                        command=self._preview).grid(row=4, column=1, sticky="w", **pad)

        ttk.Label(box, text=t("lbl_height")).grid(row=5, column=0, sticky="w", **pad)
        sc = ttk.Frame(box)
        sc.grid(row=5, column=1, sticky="w", **pad)
        self.stretch_var = tk.DoubleVar(value=float(style["icon_stretch"]))
        ttk.Scale(sc, from_=1.0, to=1.6, variable=self.stretch_var, length=220,
                  command=lambda v: self._preview()).pack(side="left")
        self.stretch_lbl = ttk.Label(sc, width=6)
        self.stretch_lbl.pack(side="left", padx=6)

        prev = ttk.Frame(box)
        prev.grid(row=6, column=0, columnspan=2, pady=(6, 0))
        ttk.Label(prev, text=t("lbl_preview")).grid(row=0, column=0, columnspan=4, sticky="w")
        self.prev_labels = []
        for i in range(4):
            lbl = tk.Label(prev, bd=0, bg=self.pal["bg"])
            lbl.grid(row=1, column=i, padx=6, pady=4)
            self.prev_labels.append(lbl)

        # --- робота ---
        work = ttk.LabelFrame(tab_work, text=t("grp_work"), padding=8)
        work.pack(fill="x")
        self.poll_var = tk.StringVar(value=str(hr.to_int(cfg["poll_seconds"], 60)))
        self.low_var = tk.StringVar(value=str(hr.to_int(cfg["low_battery_percent"], 15)))
        self.remind_var = tk.StringVar(value=str(hr.to_int(cfg["low_reminder_minutes"], 30)))
        self.idle_var = tk.StringVar(value=str(hr.to_int(cfg["idle_after_seconds"], 300) // 60))
        for row, (key, var, lo, hi) in enumerate((
                ("lbl_poll", self.poll_var, 5, 3600), ("lbl_low", self.low_var, 1, 50),
                ("lbl_remind", self.remind_var, 0, 1440), ("lbl_idle", self.idle_var, 0, 120))):
            ttk.Label(work, text=t(key)).grid(row=row, column=0, sticky="w", **pad)
            ttk.Spinbox(work, from_=lo, to=hi, textvariable=var, width=7).grid(row=row, column=1, sticky="w", **pad)
        self.full_var = tk.BooleanVar(value=bool(cfg.get("notify_full", True)))
        ttk.Checkbutton(work, text=t("chk_full"), variable=self.full_var).grid(
            row=4, column=0, columnspan=2, sticky="w", **pad)
        self.detect_var = tk.BooleanVar(value=bool(cfg.get("auto_detect", True)))
        ttk.Checkbutton(work, text=t("chk_detect"), variable=self.detect_var).grid(
            row=5, column=0, columnspan=2, sticky="w", **pad)
        self.quiet_fs_var = tk.BooleanVar(value=bool(cfg.get("quiet_fullscreen", True)))
        ttk.Checkbutton(work, text=t("chk_quiet_fs"), variable=self.quiet_fs_var).grid(
            row=6, column=0, columnspan=2, sticky="w", **pad)

        # --- програма ---
        app = ttk.LabelFrame(tab_work, text=t("grp_app"), padding=8)
        app.pack(fill="x", pady=(8, 0))
        ttk.Label(app, text=t("lbl_lang")).grid(row=0, column=0, sticky="w", **pad)
        self.lang_var = tk.StringVar(value=_label_for(LANG_KEYS, cfg.get("language", "auto")))
        ttk.Combobox(app, textvariable=self.lang_var, state="readonly", width=18,
                     values=[t(k) for k, _ in LANG_KEYS]).grid(row=0, column=1, sticky="w", **pad)
        ttk.Label(app, text=t("lbl_theme")).grid(row=1, column=0, sticky="w", **pad)
        self.theme_var = tk.StringVar(value=_label_for(THEME_KEYS, cfg.get("window_theme", "auto")))
        ttk.Combobox(app, textvariable=self.theme_var, state="readonly", width=18,
                     values=[t(k) for k, _ in THEME_KEYS]).grid(row=1, column=1, sticky="w", **pad)
        self.auto_var = tk.BooleanVar(value=winutil.autostart_enabled())
        ttk.Checkbutton(app, text=t("chk_autostart"), variable=self.auto_var).grid(
            row=2, column=0, columnspan=2, sticky="w", **pad)

        # --- оновлення ---
        upd = ttk.LabelFrame(tab_work, text=t("grp_update"), padding=8)
        upd.pack(fill="x", pady=(8, 0))
        self.upd_var = tk.BooleanVar(value=bool(cfg.get("check_updates", True)))
        ttk.Checkbutton(upd, text=t("chk_updates"), variable=self.upd_var).pack(side="left")
        ttk.Button(upd, text=t("btn_check_updates"),
                   command=lambda: self.app.check_updates(manual=True)).pack(side="right")
        author_lbl = ttk.Label(
            upd,
            text=f"{t('lbl_version', version.VERSION)} • by {version.AUTHOR}",
            foreground=self.pal["accent"],
            cursor="hand2",
        )
        author_lbl.pack(side="right", padx=10)
        author_lbl.bind("<Button-1>", lambda e: webbrowser.open(version.GITHUB_URL))

        # --- віджет ---
        wbox = ttk.LabelFrame(tab_widget, text=t("grp_widget"), padding=8)
        wbox.pack(fill="x")
        self.widget_var = tk.BooleanVar(value=bool(cfg.get("widget_enabled", False)))
        ttk.Checkbutton(wbox, text=t("chk_widget"), variable=self.widget_var).grid(
            row=0, column=0, columnspan=2, sticky="w", **pad)
        ttk.Label(wbox, text=t("lbl_wmode")).grid(row=9, column=0, sticky="w", **pad)
        self.wmode_var = tk.StringVar(value=_label_for(WIDGET_MODES, str(cfg.get("widget_mode", "top")).lower()))
        ttk.Combobox(wbox, textvariable=self.wmode_var, state="readonly", width=34,
                     values=[t(k) for k, _ in WIDGET_MODES]).grid(row=9, column=1, sticky="w", **pad)
        ttk.Label(wbox, text=t("lbl_wsize")).grid(row=1, column=0, sticky="w", **pad)
        self.wsize_var = tk.StringVar(value=_label_for(WIDGET_SIZES, str(cfg.get("widget_size", "bar")).lower(), 1))
        ttk.Combobox(wbox, textvariable=self.wsize_var, state="readonly", width=34,
                     values=[t(k) for k, _ in WIDGET_SIZES]).grid(row=1, column=1, sticky="w", **pad)
        ttk.Label(wbox, text=t("lbl_wscale")).grid(row=2, column=0, sticky="w", **pad)
        sc = ttk.Frame(wbox)
        sc.grid(row=2, column=1, sticky="w", **pad)
        self.wscale_var = tk.DoubleVar(value=_clampf(cfg.get("widget_scale", 1.0), 0.7, 2.5, 1.0))
        ttk.Scale(sc, from_=0.7, to=2.5, variable=self.wscale_var, length=220,
                  command=lambda v: self._wlabels()).pack(side="left")
        self.wscale_lbl = ttk.Label(sc, width=7)
        self.wscale_lbl.pack(side="left", padx=6)
        ttk.Label(wbox, text=t("lbl_wopacity")).grid(row=3, column=0, sticky="w", **pad)
        op = ttk.Frame(wbox)
        op.grid(row=3, column=1, sticky="w", **pad)
        self.wopacity_var = tk.DoubleVar(value=_clampf(cfg.get("widget_opacity", 0.93), 0.3, 1.0, 0.93))
        ttk.Scale(op, from_=0.3, to=1.0, variable=self.wopacity_var, length=220,
                  command=lambda v: self._wlabels()).pack(side="left")
        self.wopacity_lbl = ttk.Label(op, width=7)
        self.wopacity_lbl.pack(side="left", padx=6)
        self.wsnap_var = tk.BooleanVar(value=bool(cfg.get("widget_snap", True)))
        self.wclick_var = tk.BooleanVar(value=bool(cfg.get("widget_clickthrough", False)))
        self.whide_var = tk.BooleanVar(value=bool(cfg.get("widget_hide_fullscreen", True)))
        self.wred_var = tk.BooleanVar(value=bool(cfg.get("widget_red_low", True)))
        for row, (key, var) in enumerate((("chk_wsnap", self.wsnap_var), ("chk_wclick", self.wclick_var),
                                          ("chk_whide", self.whide_var), ("chk_wred", self.wred_var)), 4):
            ttk.Checkbutton(wbox, text=t(key), variable=var).grid(
                row=row, column=0, columnspan=2, sticky="w", **pad)
        ttk.Label(wbox, text=t("lbl_whotkey")).grid(row=10, column=0, sticky="w", **pad)
        cur_hk = str(cfg.get("widget_hotkey") or "").strip()
        self.whotkey_var = tk.StringVar(value=cur_hk or t("hotkey_none"))
        ttk.Combobox(wbox, textvariable=self.whotkey_var, state="readonly", width=22,
                     values=[t("hotkey_none"), "Ctrl+Alt+B", "Ctrl+Alt+M", "Ctrl+Shift+B", "Alt+F12"]).grid(
            row=10, column=1, sticky="w", **pad)
        ttk.Label(wbox, text=t("widget_hint"), wraplength=520, justify="left",
                  foreground=self.pal["muted"]).grid(row=11, column=0, columnspan=2, sticky="w", **pad)
        self._wlabels()

        # --- мишки ---
        mice = ttk.LabelFrame(tab_mice, text=t("grp_mice"), padding=8)
        mice.pack(fill="both", expand=True)
        ttk.Label(mice, text=t("mice_hint"), wraplength=520, justify="left",
                  foreground=self.pal["muted"]).pack(anchor="w", pady=(0, 6))
        pal = self.pal
        self.mice_list = tk.Listbox(mice, height=6, width=74, exportselection=False, bg=pal["field"],
                                    fg=pal["fg"], selectbackground=pal["accent"], selectforeground="#ffffff",
                                    highlightthickness=1, highlightbackground=pal["border"], relief="flat")
        self.mice_list.pack(fill="x")
        mb = ttk.Frame(mice)
        mb.pack(fill="x", pady=(8, 0))
        ttk.Button(mb, text=t("btn_add_known"), command=self.add_known).pack(side="left")
        ttk.Button(mb, text=t("btn_add_learn"),
                   command=lambda: open_wizard(self.mgr, self.win, -1)).pack(side="left", padx=6)
        ttk.Button(mb, text=t("btn_add_bt"), command=self.add_bluetooth).pack(side="left")
        ttk.Button(mb, text=t("btn_remove"), command=self.remove_mouse).pack(side="right")
        ttk.Button(mb, text=t("btn_rename"), command=self.rename_mouse).pack(side="right", padx=6)
        ttk.Button(mice, text=t("btn_find"),
                   command=lambda: open_wizard(self.mgr, self.win, self._sel_pos())).pack(anchor="w", pady=(8, 0))
        self.dcfgs = []
        self._refresh_mice()

        self.res = ttk.Label(outer, text="", foreground=self.pal["muted"], font=(FONT, 8))
        self.res.pack(anchor="w", pady=(8, 0))

        btns = ttk.Frame(outer)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text=t("btn_save"), command=self.save).pack(side="right")
        ttk.Button(btns, text=t("btn_cancel"), command=self.close).pack(side="right", padx=8)

    # --- логіка ---
    def _tick(self):
        stats = winutil.process_stats()
        if stats:
            self.res.config(text=t("res_line", "%.0f" % stats[0], "%.2f" % stats[1]))
        self._refresh_mice()
        self._after = self.win.after(2000, self._tick)

    def _wlabels(self):
        self.wscale_lbl.config(text="%d%%" % round(float(self.wscale_var.get()) * 100))
        self.wopacity_lbl.config(text="%d%%" % round(float(self.wopacity_var.get()) * 100))

    # --- список мишок (зміни застосовуються одразу) ---
    def _sel_pos(self):
        sel = self.mice_list.curselection()
        return sel[0] if sel else 0

    def _refresh_mice(self):
        keep = self.mice_list.curselection()
        self.dcfgs = hr.device_configs(_cfg())
        states = {d["_id"]: st for d, st in current_results(self.mgr)}
        self.mice_list.delete(0, "end")
        for d in self.dcfgs:
            if str(d.get("method", "")).lower() == "bluetooth":
                ids = "Bluetooth"
            else:
                try:
                    ids = "%04X:%s" % (hr.to_int(d["vid"]), ",".join("%04X" % p for p in hr.int_list(d["pid"])))
                except hr.ConfigError:
                    ids = "?"
            st = states.get(d["_id"])
            if st is not None and st.ok:
                stat = "%d%%" % st.percent
            elif st is not None and st.error == "asleep":
                stat = t("tip_asleep_nopct")
            else:
                stat = t("tip_not_found")
            self.mice_list.insert("end", t("mice_row", hr.device_name(d), ids, stat))
        if keep and keep[0] < len(self.dcfgs):
            self.mice_list.selection_set(keep[0])

    def add_known(self):
        found = detect.new_known(self.dcfgs)
        if not found:
            messagebox.showinfo(t("set_title"), t("mice_none_known"), parent=self.win)
            return
        names = []
        for profile in found:
            try:
                hr.save_device(-1, profile["updates"])
                names.append(profile["updates"].get("model_name") or profile["name"])
            except (OSError, hr.ConfigError) as e:
                messagebox.showerror(t("set_title"), t("err_save", e), parent=self.win)
                return
        self.app.service.refresh()
        self._refresh_mice()
        messagebox.showinfo(t("set_title"), t("mice_added", ", ".join(names)), parent=self.win)

    def add_bluetooth(self):
        devs = winutil.list_bluetooth_batteries()
        if not devs:
            messagebox.showinfo(t("bt_title"), t("bt_none"), parent=self.win)
            return
        dlg = tk.Toplevel(self.win)
        dlg.title(t("bt_title"))
        dlg.resizable(False, False)
        dlg.configure(bg=self.pal["bg"])
        theme.dark_title_bar(dlg, self.mgr.dark)
        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=t("bt_pick")).pack(anchor="w", pady=(0, 6))
        pal = self.pal
        lb = tk.Listbox(frm, height=min(8, max(3, len(devs))), width=48, bg=pal["field"], fg=pal["fg"],
                        selectbackground=pal["accent"], selectforeground="#ffffff",
                        highlightthickness=1, highlightbackground=pal["border"], relief="flat")
        for name, pct in devs:
            lb.insert("end", "%s (%d%%)" % (name, pct))
        lb.selection_set(0)
        lb.pack(fill="x")

        def ok():
            sel = lb.curselection()
            if not sel:
                return
            name, _ = devs[sel[0]]
            try:
                hr.save_device(-1, {"name": name, "model_name": name, "bt_name": name, "method": "bluetooth"})
            except (OSError, hr.ConfigError) as e:
                messagebox.showerror(t("bt_title"), t("err_save", e), parent=dlg)
                return
            dlg.destroy()
            self.app.service.refresh()
            self._refresh_mice()
            messagebox.showinfo(t("bt_title"), t("bt_added", name), parent=self.win)

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text=t("btn_apply"), command=ok).pack(side="right")
        ttk.Button(btns, text=t("btn_cancel"), command=dlg.destroy).pack(side="right", padx=8)

    def rename_mouse(self):
        pos = self._sel_pos()
        if pos >= len(self.dcfgs):
            return
        name = simpledialog.askstring(t("btn_rename"), t("ask_name"), parent=self.win,
                                      initialvalue=hr.device_name(self.dcfgs[pos]))
        if name is None:
            return
        try:
            hr.save_device(pos, {"name": name.strip()})
        except (OSError, hr.ConfigError) as e:
            messagebox.showerror(t("set_title"), t("err_save", e), parent=self.win)
            return
        self.app.service.refresh()
        self._refresh_mice()

    def remove_mouse(self):
        pos = self._sel_pos()
        if pos >= len(self.dcfgs):
            return
        if len(self.dcfgs) < 2:
            messagebox.showinfo(t("set_title"), t("mice_only_one"), parent=self.win)
            return
        if not messagebox.askyesno(t("set_title"), t("mice_confirm_remove", hr.device_name(self.dcfgs[pos])),
                                   parent=self.win):
            return
        try:
            hr.remove_device(pos)
        except (OSError, hr.ConfigError) as e:
            messagebox.showerror(t("set_title"), t("err_save", e), parent=self.win)
            return
        self.app.service.refresh()
        self._refresh_mice()

    def _on_style(self, _evt=None):
        key = _value_for(STYLE_KEYS, self.style_var.get())
        preset = iconrender.PRESETS[key]
        cur = preset["icon_font"]
        name = next((n for n, f in self.fonts if os.path.basename(f).lower() == cur.lower()), None)
        if name:
            self.font_var.set(name)
        self.color_var.set(_label_for(COLOR_KEYS, preset["icon_color_mode"]))
        self.outline_var.set(bool(preset["icon_outline"]))
        self.stretch_var.set(float(preset["icon_stretch"]))
        self._preview()

    def _style(self):
        font_name = self.font_var.get()
        return {
            "icon_font": self.font_map.get(font_name, font_name),
            "icon_color_mode": _value_for(COLOR_KEYS, self.color_var.get()),
            "icon_outline": bool(self.outline_var.get()),
            "icon_stretch": round(float(self.stretch_var.get()), 2),
            "icon_red_when_low": bool(self.red_var.get()),
        }

    def _preview(self):
        if len(getattr(self, "prev_labels", [])) < 4 or not hasattr(self, "stretch_lbl"):
            return  # інтерфейс ще будується
        st = self._style()
        self.stretch_lbl.config(text="%.2f×" % st["icon_stretch"])
        size = winutil.tray_icon_size()
        self.previews = []
        for lbl, (pct, light) in zip(self.prev_labels, [(57, True), (14, True), (57, False), (14, False)]):
            try:
                color = iconrender.pick_color(pct, st, light=light)
                icon = iconrender.make_icon(str(pct), color, st, size)
                bg = (243, 243, 243, 255) if light else (32, 32, 32, 255)
                cell = Image.new("RGBA", (size + 8, size + 8), bg)
                cell.alpha_composite(icon, (4, 4))
                photo = ImageTk.PhotoImage(cell.resize((88, 88), Image.NEAREST))
                self.previews.append(photo)
                lbl.config(image=photo)
            except Exception:
                lbl.config(image="", text="?")

    def save(self):
        try:
            poll = max(5, min(3600, int(self.poll_var.get())))
            low = max(1, min(50, int(self.low_var.get())))
            remind = max(0, min(1440, int(self.remind_var.get())))
            idle_min = max(0, min(120, int(self.idle_var.get())))
        except ValueError:
            messagebox.showerror(t("set_title"), t("err_numbers"), parent=self.win)
            return
        updates = dict(self._style())
        updates.update({
            "icon_style": _value_for(STYLE_KEYS, self.style_var.get()),
            "poll_seconds": poll, "low_battery_percent": low,
            "low_reminder_minutes": remind, "idle_after_seconds": idle_min * 60,
            "notify_full": bool(self.full_var.get()), "auto_detect": bool(self.detect_var.get()),
            "quiet_fullscreen": bool(self.quiet_fs_var.get()),
            "widget_hotkey": "" if self.whotkey_var.get() == t("hotkey_none") else self.whotkey_var.get(),
            "language": _value_for(LANG_KEYS, self.lang_var.get()),
            "window_theme": _value_for(THEME_KEYS, self.theme_var.get()),
            "widget_enabled": bool(self.widget_var.get()),
            "widget_mode": _value_for(WIDGET_MODES, self.wmode_var.get()),
            "widget_size": _value_for(WIDGET_SIZES, self.wsize_var.get()),
            "widget_scale": round(float(self.wscale_var.get()), 2),
            "widget_opacity": round(float(self.wopacity_var.get()), 2),
            "widget_snap": bool(self.wsnap_var.get()),
            "widget_clickthrough": bool(self.wclick_var.get()),
            "widget_hide_fullscreen": bool(self.whide_var.get()),
            "widget_red_low": bool(self.wred_var.get()),
            "check_updates": bool(self.upd_var.get()),
        })
        try:
            hr.save_config(updates)
            winutil.set_autostart(bool(self.auto_var.get()))
        except OSError as e:
            messagebox.showerror(t("set_title"), t("err_save", e), parent=self.win)
            return
        self.close()
        reload_theme(self.mgr)       # мова/тема/віджет застосовуються одразу
        self.app.reload_hotkey()
        self.app.service.refresh()   # оновить іконку й підказку

    def close(self):
        self.mgr.windows.pop("settings", None)
        try:
            if self._after:
                self.win.after_cancel(self._after)
            self.win.destroy()
        except tk.TclError:
            pass


# ═════════════════════════ майстер пошуку мишки ═════════════════════════

class WizardWindow:
    def __init__(self, mgr, parent, target=0):
        self.target = target
        self.mgr = mgr
        self.app = mgr.app
        self.pal = mgr.pal
        self.top = tk.Toplevel(parent)
        self.top.title(t("wiz_title"))
        self.top.resizable(False, False)
        self.top.configure(bg=self.pal["bg"])
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        theme.dark_title_bar(self.top, mgr.dark)
        self.stop = threading.Event()
        self.cands = []
        self.cap = {}
        self.charge_result = None
        self.devices = detect.list_devices()
        self.matches = detect.match_profiles()
        self._build()

    def _listbox(self, parent, height, width):
        pal = self.pal
        return tk.Listbox(parent, height=height, width=width, exportselection=False, bg=pal["field"],
                          fg=pal["fg"], selectbackground=pal["accent"], selectforeground="#ffffff",
                          highlightthickness=1, highlightbackground=pal["border"], relief="flat")

    def _build(self):
        pad = dict(padx=6, pady=3)
        outer = ttk.Frame(self.top, padding=12)
        outer.pack(fill="both", expand=True)

        tgt = ttk.Frame(outer)
        tgt.pack(fill="x", pady=(0, 8))
        ttk.Label(tgt, text=t("lbl_target")).pack(side="left")
        self.mice_names = [hr.device_name(d) for d in hr.device_configs(_cfg())]
        choices = self.mice_names + [t("target_new")]
        self.target_var = tk.StringVar()
        self.target_combo = ttk.Combobox(tgt, textvariable=self.target_var, state="readonly", width=40,
                                         values=choices)
        self.target_combo.pack(side="left", padx=8)
        self.target_combo.current(len(self.mice_names) if self.target == -1
                                  else max(0, min(self.target, len(self.mice_names) - 1)))

        a = ttk.LabelFrame(outer, text=t("wiz_known"), padding=8)
        a.pack(fill="x")
        self.known = self._listbox(a, 2, 78)
        self.known.pack(fill="x")
        if self.matches:
            for m in self.matches:
                self.known.insert("end", m["name"])
            self.known.selection_set(0)
        else:
            self.known.insert("end", t("wiz_none"))
        ttk.Button(a, text=t("wiz_use"), command=self.apply_known,
                   state="normal" if self.matches else "disabled").pack(anchor="e", pady=(6, 0))

        b = ttk.LabelFrame(outer, text=t("wiz_learn"), padding=8)
        b.pack(fill="x", pady=(8, 0))
        ttk.Label(b, wraplength=560, justify="left", text=t("wiz_learn_help")).grid(
            row=0, column=0, columnspan=3, sticky="w", **pad)
        ttk.Label(b, text=t("lbl_device")).grid(row=1, column=0, sticky="w", **pad)
        values = ["%04X:%04X  %s" % d for d in self.devices] or ["—"]
        self.dev_var = tk.StringVar(value=values[0])
        ttk.Combobox(b, textvariable=self.dev_var, values=values, state="readonly", width=56).grid(
            row=1, column=1, columnspan=2, sticky="w", **pad)
        ttk.Label(b, text=t("lbl_pct")).grid(row=2, column=0, sticky="w", **pad)
        self.pct_var = tk.StringVar()
        ttk.Entry(b, textvariable=self.pct_var, width=8).grid(row=2, column=1, sticky="w", **pad)
        self.start_btn = ttk.Button(b, text=t("btn_start"), command=self.start_learn)
        self.start_btn.grid(row=2, column=2, sticky="e", **pad)
        self.progress = ttk.Progressbar(b, maximum=100, length=560)
        self.progress.grid(row=3, column=0, columnspan=3, **pad)
        self.msg = ttk.Label(b, text="", wraplength=560, justify="left")
        self.msg.grid(row=4, column=0, columnspan=3, sticky="w", **pad)
        self.results = self._listbox(b, 4, 90)
        self.results.grid(row=5, column=0, columnspan=3, **pad)
        self.share_btn = ttk.Button(b, text=t("btn_share"), command=self.share_learned, state="disabled")
        self.share_btn.grid(row=6, column=1, sticky="e", **pad)
        self.apply_btn = ttk.Button(b, text=t("btn_apply"), command=self.apply_learned, state="disabled")
        self.apply_btn.grid(row=6, column=2, sticky="e", **pad)

        c = ttk.LabelFrame(outer, text=t("wiz_charge"), padding=8)
        c.pack(fill="x", pady=(8, 0))
        ttk.Label(c, wraplength=560, justify="left", text=t("wiz_charge_help")).grid(
            row=0, column=0, columnspan=3, sticky="w", **pad)
        self.off_btn = ttk.Button(c, text=t("btn_cap_off"), command=lambda: self.capture("off"))
        self.off_btn.grid(row=1, column=0, sticky="w", **pad)
        self.on_btn = ttk.Button(c, text=t("btn_cap_on"), command=lambda: self.capture("on"))
        self.on_btn.grid(row=1, column=1, sticky="w", **pad)
        self.charge_apply = ttk.Button(c, text=t("btn_apply_charge"), command=self.apply_charge, state="disabled")
        self.charge_apply.grid(row=1, column=2, sticky="e", **pad)
        self.charge_msg = ttk.Label(c, text="", wraplength=560, justify="left")
        self.charge_msg.grid(row=2, column=0, columnspan=3, sticky="w", **pad)

        ttk.Button(outer, text=t("btn_close"), command=self.close).pack(anchor="e", pady=(10, 0))

    def _target_pos(self):
        """Позиція мишки для збереження: 0 — основна, k — додаткова, -1 — нова."""
        idx = self.target_combo.current()
        return -1 if idx < 0 or idx >= len(self.mice_names) else idx

    def _post(self, fn, *args):
        """Виклик у потоці UI з робочого потоку (через чергу менеджера)."""
        self.mgr.q.put(("_wizard_call", (fn, args)))

    # --- відомі моделі ---
    def apply_known(self):
        sel = self.known.curselection()
        if not sel or not self.matches:
            return
        profile = self.matches[sel[0]]
        hr.save_device(self._target_pos(), profile["updates"])
        self.app.service.refresh()
        messagebox.showinfo(t("wiz_title"), t("wiz_saved", profile["name"]), parent=self.top)

    # --- навчання за відсотком ---
    def _selected_device(self):
        try:
            vid, pid = self.dev_var.get().split()[0].split(":")
            return int(vid, 16), int(pid, 16)
        except (ValueError, IndexError):
            return None

    def start_learn(self):
        dev = self._selected_device()
        if dev is None:
            self.msg.config(text=t("wiz_pick_dev"))
            return
        try:
            percent = int(self.pct_var.get())
            if not 1 <= percent <= 100:
                raise ValueError
        except ValueError:
            self.msg.config(text=t("wiz_bad_pct"))
            return
        self.vid, self.pid = dev
        self.start_btn.config(state="disabled")
        self.apply_btn.config(state="disabled")
        self.share_btn.config(state="disabled")
        self.results.delete(0, "end")
        self.msg.config(text=t("wiz_listening"))
        self.progress["value"] = 0
        threading.Thread(target=self._worker, args=(percent,), daemon=True).start()

    def _worker(self, percent):
        try:
            cands, count = detect.learn(
                self.vid, self.pid, percent, seconds=12, stop=self.stop,
                progress=lambda p, n: self._post(self._set_progress, p))
            self._post(self._done, cands, count, None)
        except Exception as e:
            self._post(self._done, [], 0, str(e))

    def _set_progress(self, value):
        self.progress["value"] = value

    def _done(self, cands, count, error):
        self.start_btn.config(state="normal")
        self.progress["value"] = 100
        if error:
            self.msg.config(text=t("wiz_error", error))
            return
        self.cands = cands
        if not cands:
            self.msg.config(text=t("wiz_nothing", count))
            return
        self.msg.config(text=t("wiz_found", len(cands)))
        for c in cands:
            info = c["info"]
            self.results.insert("end", t("wiz_cand", info["interface_number"], "%04X" % info["usage_page"],
                                         "%04X" % info["usage"], c["index"], c["hits"], c["total"], c["example"]))
        self.results.selection_set(0)
        self.apply_btn.config(state="normal")
        self.share_btn.config(state="normal")

    def share_learned(self):
        sel = self.results.curselection()
        if not sel:
            return
        import json
        cand = self.cands[sel[0]]
        upd = detect.updates_from_candidate(cand, self.vid, self.pid)
        title = "Mouse profile: %04X:%04X" % (self.vid, self.pid)
        body = (
            "### Mouse model\n_(please write your mouse model here)_\n\n"
            "### Detected config\n```json\n%s\n```\n\n"
            "Example packet: `%s`\n"
        ) % (json.dumps(upd, indent=2, ensure_ascii=False), cand.get("example", ""))
        url = version.GITHUB_URL + "/issues/new?" + urllib.parse.urlencode({"title": title, "body": body})
        webbrowser.open(url)

    def apply_learned(self):
        sel = self.results.curselection()
        if not sel:
            return
        hr.save_device(self._target_pos(), detect.updates_from_candidate(self.cands[sel[0]], self.vid, self.pid))
        self.app.service.refresh()
        messagebox.showinfo(t("wiz_title"), t("wiz_applied"), parent=self.top)

    # --- навчання статусу зарядки ---
    def capture(self, phase):
        try:
            dcfgs = hr.device_configs(hr.load_config())
            pos = self._target_pos()
            cfg = dcfgs[len(dcfgs) - 1 if pos < 0 else pos]
        except (hr.ConfigError, IndexError) as e:
            self.charge_msg.config(text=t("wiz_error", e))
            return
        self.off_btn.config(state="disabled")
        self.on_btn.config(state="disabled")
        self.charge_msg.config(text=t("wiz_listening"))

        def work():
            try:
                samples = detect.capture_reports(cfg, seconds=8, stop=self.stop)
                self._post(self._captured, phase, samples, cfg, None)
            except Exception as e:
                self._post(self._captured, phase, [], cfg, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _captured(self, phase, samples, cfg, error):
        self.off_btn.config(state="normal")
        self.on_btn.config(state="normal")
        if error:
            self.charge_msg.config(text=t("wiz_error", error))
            return
        self.cap[phase] = samples
        text = t("wiz_cap_got", len(samples))
        if not samples:
            text += " " + t("wiz_cap_none")
        elif "off" in self.cap and "on" in self.cap:
            found = detect.analyse_charging(self.cap["off"], self.cap["on"],
                                            hr.to_int(cfg["battery_byte_index"]))
            if found:
                self.charge_result = found[0]
                text += " " + t("wiz_charge_found", found[0]["index"], "0x%02X" % found[0]["off_value"],
                                "0x%02X" % found[0]["on_value"])
                self.charge_apply.config(state="normal")
            else:
                text += " " + t("wiz_charge_none")
        self.charge_msg.config(text=text)

    def apply_charge(self):
        if not self.charge_result:
            return
        r = self.charge_result
        pos = self._target_pos()
        hr.save_device(0 if pos < 0 else pos, {"charging_byte_index": r["index"], "charging_mask": "0xFF",
                                               "charging_value": "0x%02X" % r["on_value"]})
        self.app.service.refresh()
        messagebox.showinfo(t("wiz_title"), t("wiz_charge_saved"), parent=self.top)

    def close(self):
        self.stop.set()
        self.mgr.windows.pop("wizard", None)
        try:
            self.top.destroy()
        except tk.TclError:
            pass


def _wizard_call(mgr, fn, args):
    """Виклик методу майстра з робочого потоку; ігнорує, якщо вікно вже закрите."""
    if "wizard" not in mgr.windows:
        return
    try:
        fn(*args)
    except tk.TclError:
        pass
