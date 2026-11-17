# -*- coding: utf-8 -*-
"""Attack Shark Battery — заряд мишки в треї Windows.

Головний потік — трей (pystray), опитування мишки — окремий потік, а вікна (tkinter) живуть
в окремому потоці, який створюється лише на час, поки відкрите хоч одне вікно (див. uimanager.py).

Запуск без консолі:  pythonw tray_battery.py   (або зібраний AttackSharkBattery.exe)
"""
import ctypes
import logging
import logging.handlers
import os
import time

import pystray
from pystray import Menu
from pystray import MenuItem as Item

import hidreader as hr
import i18n
import iconrender
import winutil
from i18n import t
from service import BatteryService
from uimanager import UiManager

LOG = logging.getLogger("asbattery")


class App:
    def __init__(self):
        winutil.set_dpi_aware()
        self.lang = i18n.set_language(self._cfg().get("language", "auto"))
        self.low_since = None
        self.full_notified = False
        self.first_state = True
        self.last_view = None
        self.style = iconrender.icon_style(self._cfg())

        self.mgr = UiManager(self)
        self.service = BatteryService(self.on_state)
        self.service.is_watched = self.mgr.running  # відкрите вікно/віджет → не сповільнюємось
        self.icon = pystray.Icon(
            winutil.APP_NAME,
            iconrender.make_icon("--", iconrender.pick_color(None, self.style), self.style),
            t("tip_not_found"), self.build_menu())

    @staticmethod
    def _cfg():
        try:
            return hr.load_config()
        except hr.ConfigError:
            return dict(hr.DEFAULT_CONFIG)

    # ── меню ──
    def build_menu(self):
        return Menu(
            Item(t("menu_open"), lambda i, it: self.mgr.call("open_main"), default=True),
            Item(t("menu_refresh"), lambda i, it: self.service.refresh()),
            Item(t("menu_settings"), lambda i, it: self.mgr.call("open_settings")),
            Item(t("menu_widget"), self.on_toggle_widget,
                 checked=lambda item: bool(self._cfg().get("widget_enabled"))),
            Item(t("menu_autostart"), self.on_toggle_autostart,
                 checked=lambda item: winutil.autostart_enabled()),
            Menu.SEPARATOR,
            Item(t("menu_exit"), self.on_quit),
        )

    def refresh_menu(self):
        try:
            self.icon.menu = self.build_menu()
            self.icon.update_menu()
        except Exception:
            LOG.exception("menu")

    def on_toggle_widget(self, icon, item):
        enable = not bool(self._cfg().get("widget_enabled"))
        try:
            hr.save_config({"widget_enabled": enable})
        except OSError:
            LOG.exception("widget")
            return
        if enable:
            self.mgr.call("sync_widget")
        else:
            self.mgr.call_if_running("sync_widget")
        icon.update_menu()

    def on_toggle_autostart(self, icon, item):
        try:
            winutil.set_autostart(not winutil.autostart_enabled())
        except OSError:
            LOG.exception("autostart")
        icon.update_menu()

    def on_quit(self, icon, item):
        self.service.stop()
        icon.stop()

    # ── іконка ──
    def show_icon(self, text, percent, tooltip, color=None):
        color = color or iconrender.pick_color(percent, self.style)
        view = (text, tuple(color), tooltip, tuple(sorted(self.style.items())))
        if view == self.last_view:
            return
        self.last_view = view
        try:
            self.icon.icon = iconrender.make_icon(text, color, self.style)
            self.icon.title = tooltip[:127]
        except Exception:
            LOG.exception("не вдалось оновити іконку")

    def notify(self, message):
        try:
            self.icon.notify(message, "Attack Shark")
        except Exception:
            LOG.exception("notify")

    # ── результат опитування (робочий потік) ──
    def on_state(self, state, cfg):
        lang = i18n.set_language(cfg.get("language", "auto"))
        if lang != self.lang:
            self.lang = lang
            self.refresh_menu()
        self.style = iconrender.icon_style(cfg)
        model = ("Attack Shark %s" % cfg.get("model_name", "")).strip()

        if state.ok:
            if state.charging is None:
                tip = "%s: %d%%" % (model, state.percent)
            else:
                tip = "%s: %d%%, %s" % (model, state.percent,
                                        t("tip_charging") if state.charging else t("tip_not_charging"))
            self.show_icon(str(state.percent), state.percent, tip)
            self.handle_notifications(state, cfg)
        elif state.error == "asleep":
            if state.percent is not None:
                self.show_icon(str(state.percent), None, t("tip_asleep", state.percent), iconrender.GRAY)
            else:
                self.show_icon("--", None, t("tip_asleep_nopct"), iconrender.GRAY)
        elif state.error == "config":
            self.show_icon("!", 0, t("tip_config"))
        else:
            self.show_icon("--", None, t("tip_not_found"))

        self.mgr.call_if_running("update", state, cfg)

    def handle_notifications(self, state, cfg):
        pct = state.percent
        now = time.monotonic()
        charging = state.charging is True
        threshold = hr.to_int(cfg["low_battery_percent"], 15)
        remind = max(0, hr.to_int(cfg["low_reminder_minutes"], 30)) * 60

        if pct < threshold and not charging:
            if self.low_since is None:
                self.notify(t("notif_low", pct))
                self.low_since = now
            elif remind and now - self.low_since >= remind:
                self.notify(t("notif_low_again", pct))
                self.low_since = now
        elif pct >= threshold + 5 or charging:
            self.low_since = None

        if self.first_state and pct >= 100:
            self.full_notified = True  # вже повна при старті — не сповіщаємо
        elif cfg.get("notify_full", True):
            if pct >= 100 and not self.full_notified and state.charging is not False:
                self.notify(t("notif_full"))
                self.full_notified = True
        if pct < 95:
            self.full_notified = False
        self.first_state = False

    # ── запуск ──
    def run(self):
        self.service.start()
        if self._cfg().get("widget_enabled"):
            self.mgr.call("sync_widget")
        try:
            self.icon.run()  # блокує до «Вихід»
        finally:
            self.service.stop()


def setup_logging():
    debug = False
    try:
        debug = bool(hr.load_config().get("debug"))
    except Exception:
        pass
    handler = logging.handlers.RotatingFileHandler(
        os.path.join(hr.data_dir(), "battery.log"),
        maxBytes=200_000, backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOG.addHandler(handler)
    LOG.setLevel(logging.DEBUG if debug else logging.INFO)


def main():
    if not winutil.single_instance():
        try:
            lang = i18n.set_language(App._cfg().get("language", "auto"))
            ctypes.windll.user32.MessageBoxW(0, t("already_running"), "Attack Shark Battery", 0x40)
        except Exception:
            pass
        return
    setup_logging()
    App().run()


if __name__ == "__main__":
    main()
