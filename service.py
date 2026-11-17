# -*- coding: utf-8 -*-
"""Фонове опитування мишки. Не залежить від інтерфейсу: результат віддається через listener.

Економія ресурсів: потік більшу частину часу спить (wake кожні TICK секунд), читання HID
блокуюче (без активного очікування), а коли за комп'ютером нікого немає (немає вводу
`idle_after_seconds`) і жодне вікно не відкрите — опитування сповільнюється до `idle_poll_seconds`.
"""
import logging
import threading
import time
from collections import namedtuple

import detect
import history
import hidreader as hr
import winutil

LOG = logging.getLogger("asbattery")

# error: "" | "not_found" | "asleep" | "config"; для "asleep" percent/charging — останні відомі
State = namedtuple("State", "ok percent charging ts error")
EMPTY = State(False, None, None, None, "not_found")

TICK = 5.0


class BatteryService:
    def __init__(self, listener):
        """listener(results, cfg) викликається з робочого потоку після кожного опитування.
        results = [(конфіг_мишки, State), …]; перша — основна мишка, cfg — загальний конфіг."""
        self.listener = listener
        self.state = EMPTY          # стан основної мишки
        self.results = []           # [(dcfg, State)] усіх мишок
        self.cfg = dict(hr.DEFAULT_CONFIG)
        self.is_watched = lambda: False  # True, якщо відкрите вікно/віджет (тоді не сповільнюємось)
        self._last = {}             # _id -> (percent, charging) останній відомий
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._force = True
        self._thread = None

    # --- керування ---
    def start(self):
        history.prune()
        detect.fill_missing()
        self._thread = threading.Thread(target=self._loop, name="battery-poll", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()

    def refresh(self):
        self._force = True
        self._wake.set()

    # --- опитування ---
    def poll(self):
        """Опитує всі мишки. Повертає ([(dcfg, State)], загальний cfg)."""
        try:
            cfg = hr.load_config()
        except hr.ConfigError as e:
            LOG.error("%s", e)
            err = State(False, None, None, time.time(), "config")
            return [(dict(self.cfg, _id=0), err)], self.cfg
        self.cfg = cfg
        dcfgs = hr.device_configs(cfg)

        results = self._read_all(dcfgs)
        primary = results[0][1]
        if not primary.ok and primary.error == "not_found" and cfg.get("auto_detect", True):
            for profile in detect.match_profiles():
                if any(detect.same_device(d, profile["updates"]) for d in dcfgs):
                    continue  # ця мишка вже є в списку (основна чи додаткова)
                LOG.info("автовизначено: %s", profile["name"])
                try:
                    hr.save_config(profile["updates"])
                    cfg = hr.load_config()
                    self.cfg = cfg
                except (OSError, hr.ConfigError):
                    LOG.exception("не вдалось зберегти автовизначену мишку")
                    break
                dcfgs = hr.device_configs(cfg)
                results = self._read_all(dcfgs)
                break

        for dcfg, state in results:
            if state.ok:
                self._last[dcfg["_id"]] = (state.percent, state.charging)
                history.append(state.percent, state.charging, device=dcfg["_id"])
        return results, cfg

    def _read_all(self, dcfgs):
        """Читає всі мишки; при кількох — паралельно (мишка, що спить, не затримує решту)."""
        if len(dcfgs) == 1:
            return [(dcfgs[0], self._read(dcfgs[0]))]
        out = [None] * len(dcfgs)

        def work(i, d):
            out[i] = self._read(d)

        threads = [threading.Thread(target=work, args=(i, d), daemon=True) for i, d in enumerate(dcfgs)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        return [(d, st if st is not None else EMPTY) for d, st in zip(dcfgs, out)]

    def _read(self, cfg):
        last_pct, last_charging = self._last.get(cfg.get("_id", 0), (None, None))
        retries = max(1, hr.to_int(cfg["read_retries"], 2))
        for attempt in range(retries):
            try:
                st = hr.read_status(cfg)
                if cfg.get("debug"):
                    LOG.debug("[%s] raw=%s", cfg.get("_id"), st.raw.hex(" "))
                return State(True, st.percent, st.charging, time.time(), "")
            except hr.ConfigError as e:
                LOG.error("config: %s", e)
                return State(False, None, None, time.time(), "config")
            except hr.MouseAsleep:
                return State(False, last_pct, last_charging, time.time(), "asleep")
            except (hr.DeviceNotFound, hr.ReadError) as e:
                LOG.info("не вдалось прочитати (%d/%d): %s", attempt + 1, retries, e)
            except Exception:
                LOG.exception("несподівана помилка читання")
            if attempt < retries - 1:
                time.sleep(0.4)
        return State(False, None, None, time.time(), "not_found")

    # --- цикл ---
    def _loop(self):
        last_poll = -1e9
        was_idle = False
        while not self._stop.is_set():
            try:
                cfg = hr.load_config()
                base = max(5, hr.to_int(cfg["poll_seconds"], 60))
                idle_after = hr.to_int(cfg.get("idle_after_seconds"), 300)
                idle = (idle_after > 0 and not self.is_watched()
                        and winutil.idle_seconds() >= idle_after)
                interval = max(base, hr.to_int(cfg.get("idle_poll_seconds"), 600)) if idle else base
                now = time.monotonic()
                if self._force or now - last_poll >= interval or (was_idle and not idle):
                    self._force = False
                    last_poll = now
                    results, cfg = self.poll()
                    self.results = results
                    self.state = results[0][1]
                    self.listener(results, cfg)
                was_idle = idle
            except Exception:
                LOG.exception("poll")
            self._wake.wait(TICK)
            self._wake.clear()
