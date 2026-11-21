# -*- coding: utf-8 -*-
"""Автовизначення мишки.

1) Відомі моделі (PROFILES) — підтверджено захопленням трафіку; знаходяться миттєво.
2) Навчання: користувач вводить відсоток із офіційного драйвера, програма кілька секунд
   слухає input-репорти пристрою і шукає байт, що дорівнює цьому відсотку.
   Працює для мишок, які самі періодично шлють заряд (як X11). Для моделей із запитом
   (request/response) потрібен дамп USBPcap.
"""
import json
import time
from collections import Counter, defaultdict

import hidreader as hr

try:
    import hid
except ImportError:
    hid = None

PROFILES = [
    {
        "name": "Attack Shark X11 (2.4G ресивер 1D57:FA60)",
        "updates": {
            "model_name": "X11",
            "vid": "0x1D57", "pid": ["0xFA60"],
            "usage_page": "0x000A", "usage": "0", "interface_number": 2,
            "method": "input", "request_hex": "", "request_length": 0,
            "response_length": 65, "response_prefix_hex": "03 55 40",
            "response_timeout_ms": 6000, "sleep_prefix_hex": "03 55 01",
            "battery_byte_index": 4, "battery_mask": "0xFF", "battery_raw_max": 100,
            "charging_byte_index": None,
        },
    },
]


def fill_missing():
    """Додає в збережений config.json нові ключі профілю відомої мишки (нічого не перезаписує)."""
    try:
        path = hr.config_path()
        with open(path, encoding="utf-8-sig") as f:
            raw = json.load(f)
        cfg = hr.load_config()
    except (OSError, ValueError, hr.ConfigError):
        return
    for profile in PROFILES:
        if same_device(cfg, profile["updates"]):
            add = {k: v for k, v in profile["updates"].items() if k not in raw}
            if add:
                try:
                    hr.save_config(add)
                except OSError:
                    pass
            return


def list_devices():
    """[(vid, pid, назва)] усіх HID-пристроїв; «схожі на мишку-ресивер» — першими."""
    if hid is None:
        return []
    seen = {}
    for d in hid.enumerate(0, 0):
        key = (d["vendor_id"], d["product_id"])
        name = (d.get("product_string") or "").strip()
        vendor = (d.get("manufacturer_string") or "").strip()
        if key not in seen or (name and not seen[key]):
            seen[key] = ("%s %s" % (vendor, name)).strip()

    def likely(item):
        text = item[1].lower()
        return not any(w in text for w in ("wireless", "shark", "2.4g", "receiver", "mouse"))

    items = sorted(((k, v) for k, v in seen.items()), key=lambda kv: (likely(kv), kv[0]))
    return [(k[0], k[1], v) for k, v in items]


def match_profiles():
    """Профілі відомих моделей, чий пристрій зараз підключений."""
    if hid is None:
        return []
    found = []
    for profile in PROFILES:
        u = profile["updates"]
        vid = hr.to_int(u["vid"])
        pids = hr.int_list(u["pid"])
        iface = hr.to_int(u["interface_number"], -1)
        page = hr.to_int(u["usage_page"])
        for info in hid.enumerate(vid, 0):
            if info["product_id"] in pids and \
                    (iface < 0 or info["interface_number"] == iface) and \
                    (not page or info["usage_page"] == page):
                found.append(profile)
                break
    return found


def new_known(dcfgs):
    """Профілі підключених відомих мишок, яких ще нема серед налаштованих (dcfgs — device_configs)."""
    return [p for p in match_profiles()
            if not any(same_device(d, p["updates"]) for d in dcfgs)]


def same_device(cfg, updates):
    try:
        return (hr.to_int(cfg["vid"]) == hr.to_int(updates["vid"]) and
                sorted(hr.int_list(cfg["pid"])) == sorted(hr.int_list(updates["pid"])) and
                hr.to_int(cfg["interface_number"], -1) == hr.to_int(updates["interface_number"], -1))
    except hr.ConfigError:
        return False


# ───────── навчання ─────────

def analyse(samples, infos, percent):
    """samples: [(номер інтерфейсу, bytes)]. Повертає кандидатів, найкращі першими."""
    groups = defaultdict(list)
    for n, data in samples:
        if data:
            groups[(n, data[0], len(data))].append(data)

    results = []
    for (n, rid, length), items in groups.items():
        for idx in range(1, length):
            hits = [b for b in items if b[idx] == percent]
            need = 2 if len(items) >= 2 else 1
            if len(hits) < need or len(hits) / float(len(items)) < 0.5:
                continue
            plen = 0
            while plen < min(idx, 3) and all(b[plen] == hits[0][plen] for b in hits):
                plen += 1
            info = infos[n]
            results.append({
                "info": info, "index": idx, "prefix": hits[0][:plen].hex(" ").upper(),
                "example": hits[0].hex(" ").upper(), "hits": len(hits), "total": len(items),
                "score": len(hits) / float(len(items)) + len(hits) / 100.0,
            })
    results.sort(key=lambda r: -r["score"])
    return results


def learn(vid, pid, percent, seconds=12, stop=None, progress=None):
    """Слухає всі інтерфейси пристрою (крім миші/клавіатури) і шукає байт == percent."""
    if hid is None:
        raise hr.ReadError("модуль hidapi не встановлено")
    infos, devs = [], []
    for info in hid.enumerate(vid, pid):
        if info["usage_page"] == 1 and info["usage"] in (2, 6):
            continue  # миша/клавіатура: Windows не дає відкрити, і заряду там нема
        dev = hid.device()
        try:
            dev.open_path(info["path"])
            dev.set_nonblocking(1)
        except (OSError, IOError, ValueError):
            continue
        infos.append(info)
        devs.append(dev)
    if not devs:
        raise hr.DeviceNotFound("не вдалось відкрити жодного інтерфейсу пристрою")

    samples = []
    start = time.monotonic()
    last_report = 0.0
    try:
        while time.monotonic() - start < seconds and not (stop is not None and stop.is_set()):
            got = False
            for n, dev in enumerate(devs):
                for _ in range(64):
                    data = dev.read(64)
                    if not data:
                        break
                    samples.append((n, bytes(data)))
                    got = True
            now = time.monotonic()
            if progress and now - last_report > 0.2:
                last_report = now
                progress(min(100, int((now - start) * 100 / seconds)), len(samples))
            if not got:
                time.sleep(0.02)
    finally:
        for dev in devs:
            try:
                dev.close()
            except Exception:
                pass
    return analyse(samples, infos, percent), len(samples)


def updates_from_candidate(cand, vid, pid, model_name=None):
    info = cand["info"]
    updates = {
        "vid": "0x%04X" % vid, "pid": ["0x%04X" % pid],
        "usage_page": "0x%04X" % info["usage_page"], "usage": "0x%04X" % info["usage"],
        "interface_number": info["interface_number"],
        "method": "input", "request_hex": "", "request_length": 0,
        "response_length": 65, "response_prefix_hex": cand["prefix"],
        "response_timeout_ms": 6000,
        "battery_byte_index": cand["index"], "battery_mask": "0xFF", "battery_raw_max": 100,
        "charging_byte_index": None,
    }
    if model_name:
        updates["model_name"] = model_name
    return updates


# ───────── навчання статусу «заряджається» ─────────

def capture_reports(cfg, seconds=8, stop=None, progress=None):
    """Збирає репорти налаштованого інтерфейсу (лише з потрібним префіксом, без «sleep»)."""
    if hid is None:
        raise hr.ReadError("модуль hidapi не встановлено")
    cands = hr.find_candidates(cfg)
    if not cands:
        raise hr.DeviceNotFound("пристрій не знайдено")
    prefix = hr.parse_hex(cfg["response_prefix_hex"])
    sleep = hr.parse_hex(cfg.get("sleep_prefix_hex", ""))
    devs = []
    for info in cands:
        dev = hid.device()
        try:
            dev.open_path(info["path"])
            dev.set_nonblocking(1)
            devs.append(dev)
        except (OSError, IOError, ValueError):
            continue
    if not devs:
        raise hr.ReadError("не вдалось відкрити пристрій")
    out = []
    start = time.monotonic()
    last = 0.0
    try:
        while time.monotonic() - start < seconds and not (stop is not None and stop.is_set()):
            got = False
            for dev in devs:
                for _ in range(32):
                    data = dev.read(64)
                    if not data:
                        break
                    got = True
                    data = bytes(data)
                    if sleep and data.startswith(sleep):
                        continue
                    if prefix and not data.startswith(prefix):
                        continue
                    out.append(data)
            now = time.monotonic()
            if progress and now - last > 0.2:
                last = now
                progress(min(100, int((now - start) * 100 / seconds)))
            if not got:
                time.sleep(0.02)
    finally:
        for dev in devs:
            try:
                dev.close()
            except Exception:
                pass
    return out


def analyse_charging(off_samples, on_samples, battery_index):
    """Шукає байт, що стабільно відрізняється між «без зарядки» й «на зарядці»."""
    if not off_samples or not on_samples:
        return []
    length = min(min(len(x) for x in off_samples), min(len(x) for x in on_samples))
    results = []
    for idx in range(1, length):
        if idx == battery_index:
            continue
        a = Counter(x[idx] for x in off_samples)
        b = Counter(x[idx] for x in on_samples)
        if set(a) & set(b):
            continue
        (a_val, a_n), (b_val, b_n) = a.most_common(1)[0], b.most_common(1)[0]
        if a_n / len(off_samples) < 0.8 or b_n / len(on_samples) < 0.8:
            continue
        results.append({"index": idx, "off_value": a_val, "on_value": b_val})
    return results
