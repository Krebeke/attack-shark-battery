# -*- coding: utf-8 -*-
"""Спільна логіка читання заряду через HID.

Використовується і треєм (tray_battery.py), і допоміжним скриптом (find_device.py),
тому індекси байтів у обох завжди збігаються.

Домовленість про індекси: байт 0 = перший байт, який повернув hidapi.
Якщо пристрій використовує нумеровані репорти, це і є Report ID.
"""
import json
import os
import shutil
import sys
import time
from collections import namedtuple

try:
    import hid  # пакет PyPI "hidapi" (НЕ "hid")
except ImportError:
    hid = None


class DeviceNotFound(Exception):
    """Потрібний HID-інтерфейс не знайдено (мишка вимкнена / не той VID/PID)."""


class ReadError(Exception):
    """Інтерфейс є, але відповідь не отримано або вона некоректна."""


class MouseAsleep(ReadError):
    """Ресивер на зв'язку, але мишка спить / поза зоною (прийшов «sleep»-репорт)."""


class ConfigError(Exception):
    """Помилка в config.json."""


Status = namedtuple("Status", "percent charging raw info")

DEFAULT_CONFIG = {
    "model_name": "R1",
    "vid": "0x248A",
    "pid": "0x8266",            # число/рядок або список, напр. ["0x8266", "0x8267"]
    "usage_page": "0xFF02",     # 0 = будь-яка
    "usage": "0x0002",          # 0 = будь-який
    "interface_number": -1,     # -1 = будь-який
    "method": "feature",        # feature | feature_get | output_input | input
    "request_hex": "00 00",     # перший байт = Report ID (00, якщо нумерованих репортів нема)
    "request_length": 0,        # доповнити запит нулями до цієї довжини (0 = не доповнювати)
    "response_report_id": 0,    # для feature / feature_get
    "response_length": 65,
    "response_prefix_hex": "",  # якщо задано, відповідь має починатися з цих байтів
    "response_delay_ms": 50,    # пауза між запитом і читанням відповіді (feature)
    "response_timeout_ms": 800, # очікування відповіді (output_input / input)
    "battery_byte_index": 1,
    "battery_mask": "0xFF",     # напр. 0x7F, якщо старший біт = прапорець зарядки
    "battery_raw_max": 100,     # яке значення байта відповідає 100% (100 або 255)
    "charging_byte_index": None,  # None = статус зарядки невідомий
    "charging_mask": "0xFF",
    "charging_value": "0x01",   # (байт & mask) == value  ->  заряджається
    "poll_seconds": 60,
    "low_battery_percent": 15,
    "read_retries": 2,
    "sleep_prefix_hex": "",     # початок репорта «мишка спить» (для input), напр. "03 55 01"
    "auto_detect": True,        # шукати відому мишку автоматично, якщо вказана не знайдена
    "language": "auto",         # auto | uk | en
    "window_theme": "auto",     # auto | light | dark
    "widget_enabled": False,    # міні-віджет поверх екрана
    "widget_x": None,
    "widget_y": None,
    "notify_full": True,        # сповіщати, коли заряд 100%
    "low_reminder_minutes": 30, # повторне нагадування про низький заряд (0 = вимкнено)
    "idle_after_seconds": 300,  # якщо за ПК нікого стільки секунд — опитувати рідше (0 = вимкнено)
    "idle_poll_seconds": 600,   # період опитування в режимі простою
    "icon_style": "windows",    # windows | colored (решта icon_* — перевизначення пресета)
    "debug": False,
}


def app_dir():
    """Папка поруч з .exe (або зі скриптом)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def data_dir():
    """Папка з даними користувача: %APPDATA%\\AttackSharkBattery (конфіг, історія, лог)."""
    base = os.environ.get("APPDATA") or app_dir()
    path = os.path.join(base, "AttackSharkBattery")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        path = app_dir()
    return path


def config_path():
    """Шлях до config.json. При першому запуску копіюється з папки програми."""
    path = os.path.join(data_dir(), "config.json")
    if not os.path.exists(path):
        for name in ("config.json", "config.default.json"):
            src = os.path.join(app_dir(), name)
            if os.path.exists(src) and os.path.abspath(src) != os.path.abspath(path):
                try:
                    shutil.copyfile(src, path)
                    return path
                except OSError:
                    pass
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
    return path


def save_config(updates, path=None):
    """Оновлює вказані ключі в config.json, решту (і службові _коментарі) не чіпає."""
    path = path or config_path()
    try:
        with open(path, encoding="utf-8-sig") as f:
            current = json.load(f)
    except (OSError, ValueError):
        current = {}
    current.update(updates)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    _cfg_cache.pop(path, None)


def to_int(value, default=0):
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip(), 0)
    except ValueError:
        raise ConfigError("Не можу розібрати число: %r" % (value,))


def int_list(value):
    if isinstance(value, (list, tuple)):
        return [to_int(v) for v in value]
    return [to_int(value)]


def parse_hex(text):
    text = (text or "").replace(",", " ").replace("0x", "").replace("0X", "")
    out = bytearray()
    for tok in text.split():
        try:
            out.append(int(tok, 16))
        except ValueError:
            raise ConfigError("Некоректний hex-байт: %r" % tok)
    return bytes(out)


_cfg_cache = {}


def load_config(path=None):
    """Читає конфіг; результат кешується за часом зміни файлу (дешево викликати часто)."""
    path = path or config_path()
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = None
    hit = _cfg_cache.get(path)
    if hit and mtime is not None and hit[0] == mtime:
        return dict(hit[1])
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(path, encoding="utf-8-sig") as f:
            cfg.update(json.load(f))
    except FileNotFoundError:
        raise ConfigError("Не знайдено %s" % path)
    except ValueError as e:
        raise ConfigError("config.json: %s" % e)
    _cfg_cache[path] = (mtime, cfg)
    return dict(cfg)


def find_candidates(cfg):
    """Повертає список HID-інтерфейсів, що підходять під фільтр із конфігу."""
    if hid is None:
        raise ReadError("модуль hidapi не встановлено")
    vid = to_int(cfg["vid"])
    pids = int_list(cfg["pid"])
    usage_page = to_int(cfg["usage_page"])
    usage = to_int(cfg["usage"])
    iface = to_int(cfg["interface_number"], -1)

    result = []
    for info in hid.enumerate(vid, 0):
        if info["product_id"] not in pids:
            continue
        if usage_page and info["usage_page"] != usage_page:
            continue
        if usage and info["usage"] != usage:
            continue
        if iface >= 0 and info["interface_number"] != iface:
            continue
        result.append(info)
    return result


def _exchange(dev, cfg):
    method = cfg["method"]
    req = parse_hex(cfg["request_hex"])
    pad = to_int(cfg["request_length"])
    if req and pad > len(req):
        req += bytes(pad - len(req))
    rlen = to_int(cfg["response_length"], 65)
    prefix = parse_hex(cfg["response_prefix_hex"])
    sleep = parse_hex(cfg.get("sleep_prefix_hex", ""))

    if method in ("feature", "feature_get"):
        if method == "feature":
            if not req:
                raise ConfigError("method=feature потребує request_hex")
            dev.send_feature_report(list(req))
            time.sleep(to_int(cfg["response_delay_ms"]) / 1000.0)
        data = dev.get_feature_report(to_int(cfg["response_report_id"]), rlen)
        return bytes(data)

    if method in ("output_input", "input"):
        if method == "output_input":
            if not req:
                raise ConfigError("method=output_input потребує request_hex")
            if dev.write(list(req)) < 0:
                raise ReadError("write() повернув помилку")
        deadline = time.monotonic() + to_int(cfg["response_timeout_ms"]) / 1000.0
        saw_sleep = False
        while True:
            remain = int((deadline - time.monotonic()) * 1000)
            if remain <= 0:
                if saw_sleep:
                    raise MouseAsleep("мишка спить або поза зоною")
                raise ReadError("таймаут очікування відповіді")
            data = dev.read(rlen, remain)
            if not data:
                continue
            data = bytes(data)
            if sleep and data.startswith(sleep):
                saw_sleep = True  # можливо, наступний репорт буде вже нормальним
                continue
            if prefix and not data.startswith(prefix):
                continue  # чужий репорт (рух, кнопки тощо) — пропускаємо
            return data

    raise ConfigError("Невідомий method: %r" % method)


def read_raw(cfg, candidates=None):
    """Відкриває інтерфейс(и), робить обмін, закриває. Повертає (bytes, info).

    Пристрій відкривається лише на час запиту, щоб не заважати офіційному драйверу.
    """
    if candidates is None:
        candidates = find_candidates(cfg)
    if not candidates:
        raise DeviceNotFound("HID-інтерфейс за заданими VID/PID/usage не знайдено")

    last_err = None
    for info in candidates:
        dev = hid.device()
        try:
            dev.open_path(info["path"])
        except (OSError, IOError, ValueError) as e:
            last_err = ReadError("не вдалось відкрити пристрій: %s" % e)
            continue
        try:
            raw = _exchange(dev, cfg)
            return raw, info
        except (OSError, IOError, ValueError, ReadError) as e:
            last_err = e if isinstance(e, ReadError) else ReadError(str(e))
        finally:
            try:
                dev.close()
            except Exception:
                pass
    raise last_err or ReadError("невідома помилка читання")


def parse_status(raw, cfg, info=None):
    prefix = parse_hex(cfg["response_prefix_hex"])
    if prefix and not raw.startswith(prefix):
        raise ReadError("несподівана відповідь: %s" % raw[:8].hex(" "))
    if not any(raw):
        raise ReadError("порожня відповідь (мишка спить / вимкнена?)")

    idx = to_int(cfg["battery_byte_index"])
    if idx < 0 or idx >= len(raw):
        raise ReadError("battery_byte_index=%d поза відповіддю (%d байт)" % (idx, len(raw)))
    value = raw[idx] & to_int(cfg["battery_mask"], 0xFF)
    rmax = to_int(cfg["battery_raw_max"], 100) or 100
    if value > rmax:
        raise ReadError("значення заряду %d > %d — невірний індекс?" % (value, rmax))
    percent = max(0, min(100, int(round(value * 100.0 / rmax))))

    charging = None
    cidx = cfg.get("charging_byte_index")
    if cidx is not None and cidx != "":
        cidx = to_int(cidx)
        if 0 <= cidx < len(raw):
            charging = (raw[cidx] & to_int(cfg["charging_mask"], 0xFF)) == to_int(cfg["charging_value"], 1)
    return Status(percent, charging, raw, info)


def read_status(cfg):
    raw, info = read_raw(cfg)
    return parse_status(raw, cfg, info)
