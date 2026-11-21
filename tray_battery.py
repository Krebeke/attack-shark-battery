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
import sys
import threading
import time
import webbrowser

import pystray
from pystray import Menu
from pystray import MenuItem as Item

import hidreader as hr
import i18n
import iconrender
import updater
import winutil
from i18n import t
from service import BatteryService
from uimanager import UiManager

LOG = logging.getLogger("asbattery")


class App:
    def __init__(self):
        winutil.set_dpi_aware()
        self.lang = i18n.set_language(self._cfg().get("language", "auto"))
        self.notif = {}   # id мишки -> {"low_since", "full", "first"}
        self.last_view = None
        self.style = iconrender.icon_style(self._cfg())
        self.update_info = None
        self.update_notified = None
        self.stop_evt = threading.Event()
        self.hotkey = winutil.HotkeyListener(self.on_hotkey_widget)

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
        info = self.update_info
        update_items = ()
        if info:
            update_items = (Item(t("menu_update", info["version"]),
                                 lambda i, it: self.mgr.call("confirm_update", info)),)
        return Menu(
            *update_items,
            Item(t("menu_open"), lambda i, it: self.mgr.call("open_main"), default=True),
            Item(t("menu_refresh"), lambda i, it: self.service.refresh()),
            Item(t("menu_settings"), lambda i, it: self.mgr.call("open_settings")),
            Item(t("menu_widget"), self.on_toggle_widget,
                 checked=lambda item: bool(self._cfg().get("widget_enabled"))),
            Item(t("menu_clickthrough"), self.on_toggle_clickthrough,
                 checked=lambda item: bool(self._cfg().get("widget_clickthrough")),
                 visible=lambda item: bool(self._cfg().get("widget_enabled"))),
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

    def on_toggle_clickthrough(self, icon, item):
        try:
            hr.save_config({"widget_clickthrough": not bool(self._cfg().get("widget_clickthrough"))})
        except OSError:
            LOG.exception("clickthrough")
            return
        self.mgr.call_if_running("sync_widget")
        icon.update_menu()

    def on_toggle_autostart(self, icon, item):
        try:
            winutil.set_autostart(not winutil.autostart_enabled())
        except OSError:
            LOG.exception("autostart")
        icon.update_menu()

    def reload_hotkey(self):
        self.hotkey.start(self._cfg().get("widget_hotkey", ""))

    def on_hotkey_widget(self):
        self.on_toggle_widget(self.icon, None)

    def on_quit(self, icon, item):
        self.stop_evt.set()
        self.hotkey.stop()
        self.service.stop()
        icon.stop()

    # ── оновлення ──
    def check_updates(self, manual=False):
        """Перевірка оновлень у фоні. manual=True — повідомляти і про «все актуально»/помилку."""
        def work():
            try:
                info = updater.check(self._cfg().get("update_repo", ""))
            except Exception as e:
                LOG.info("перевірка оновлень не вдалась: %s", e)
                if manual:
                    self.notify(t("notif_upd_failed"), force=True)
                return
            self.update_info = info
            self.refresh_menu()
            if info:
                if manual or self.update_notified != info["version"]:
                    self.update_notified = info["version"]
                    self.notify(t("notif_update", info["version"]))
            elif manual:
                self.notify(t("notif_uptodate"), force=True)
        threading.Thread(target=work, name="update-check", daemon=True).start()

    def update_loop(self):
        if self.stop_evt.wait(90):  # не заважаємо запуску
            return
        while not self.stop_evt.is_set():
            cfg = self._cfg()
            if cfg.get("check_updates", True):
                self.check_updates(manual=False)
            hours = max(1, hr.to_int(cfg.get("update_check_hours"), 24))
            if self.stop_evt.wait(hours * 3600):
                return

    def apply_update(self, info):
        """Викликається після підтвердження в UI: завантажити й запустити інсталятор."""
        def work():
            try:
                if not getattr(sys, "frozen", False):
                    webbrowser.open(info.get("page") or "https://github.com")  # зі скриптів — лише сторінка релізу
                    return
                self.notify(t("notif_upd_download", info["version"]), force=True)
                path = updater.download(info)
                updater.launch_installer(path)
                self.on_quit(self.icon, None)
            except Exception as e:
                LOG.exception("оновлення не вдалось")
                self.notify(t("notif_upd_failed"), force=True)
        threading.Thread(target=work, name="update-apply", daemon=True).start()

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

    def notify(self, message, force=False):
        if not force and self._cfg().get("quiet_fullscreen", True) and winutil.foreground_fullscreen():
            LOG.info("тихий режим (повноекранна програма): %s", message)
            return
        try:
            self.icon.notify(message, "Attack Shark")
        except Exception:
            LOG.exception("notify")

    # ── результат опитування (робочий потік) ──
    @staticmethod
    def _tip_line(name, st, with_name):
        if st.ok:
            if st.charging is None:
                return "%s: %d%%" % (name, st.percent)
            return "%s: %d%%, %s" % (name, st.percent,
                                     t("tip_charging") if st.charging else t("tip_not_charging"))
        if st.error == "asleep":
            text = t("tip_asleep", st.percent) if st.percent is not None else t("tip_asleep_nopct")
        elif st.error == "config":
            text = t("tip_config")
        else:
            text = t("tip_not_found")
        return ("%s: %s" % (name, text)) if with_name else text

    def on_state(self, results, cfg):
        """results = [(конфіг_мишки, State)]. Іконка показує мишку з найменшим зарядом."""
        lang = i18n.set_language(cfg.get("language", "auto"))
        if lang != self.lang:
            self.lang = lang
            self.refresh_menu()
        self.style = iconrender.icon_style(cfg)
        multi = len(results) > 1

        lines = []
        for dcfg, st in results:
            name = hr.device_name(dcfg)
            lines.append(self._tip_line(name, st, multi))
            if st.ok:
                self.handle_notifications(dcfg["_id"], name, multi, st, dcfg)
        tip = "\n".join(lines)

        ok = [st for _, st in results if st.ok]
        asleep = [st for _, st in results if st.error == "asleep"]
        if ok:
            low = min(ok, key=lambda st: st.percent)
            self.show_icon(str(low.percent), low.percent, tip)
        elif asleep:
            known = [st for st in asleep if st.percent is not None]
            if known:
                low = min(known, key=lambda st: st.percent)
                self.show_icon(str(low.percent), None, tip, iconrender.GRAY)
            else:
                self.show_icon("--", None, tip, iconrender.GRAY)
        elif any(st.error == "config" for _, st in results):
            self.show_icon("!", 0, tip)
        else:
            self.show_icon("--", None, tip)

        self.mgr.call_if_running("update", results, cfg)

    def handle_notifications(self, dev_id, name, multi, state, cfg):
        ns = self.notif.setdefault(dev_id, {"low_since": None, "full": False, "first": True})
        pct = state.percent
        now = time.monotonic()
        charging = state.charging is True
        threshold = hr.to_int(cfg["low_battery_percent"], 15)
        remind = max(0, hr.to_int(cfg["low_reminder_minutes"], 30)) * 60

        def say(text):
            self.notify(("%s: %s" % (name, text)) if multi else text)

        if pct < threshold and not charging:
            if ns["low_since"] is None:
                say(t("notif_low", pct))
                ns["low_since"] = now
            elif remind and now - ns["low_since"] >= remind:
                say(t("notif_low_again", pct))
                ns["low_since"] = now
        elif pct >= threshold + 5 or charging:
            ns["low_since"] = None

        if ns["first"] and pct >= 100:
            ns["full"] = True  # вже повна при старті — не сповіщаємо
        elif cfg.get("notify_full", True):
            if pct >= 100 and not ns["full"] and state.charging is not False:
                say(t("notif_full"))
                ns["full"] = True
        if pct < 95:
            ns["full"] = False
        ns["first"] = False

    # ── запуск ──
    def run(self):
        self.reload_hotkey()
        self.service.start()
        threading.Thread(target=self.update_loop, name="update-loop", daemon=True).start()
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
