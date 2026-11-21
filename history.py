# -*- coding: utf-8 -*-
"""Історія заряду (CSV у %APPDATA%\\AttackSharkBattery\\history.csv) і оцінка часу роботи."""
import os
import time

import hidreader as hr

KEEP_DAYS = 30
MIN_STEP_SECONDS = 600  # писати не частіше, ніж раз на 10 хв, якщо заряд не змінився

_last = {}  # device -> (epoch, percent, charging)


def path():
    return os.path.join(hr.data_dir(), "history.csv")


def _ch(value):
    return "-" if value is None else ("1" if value else "0")


def _line(ts, pct, ch, device):
    """Основна мишка (0) пишеться у старому форматі з 3 колонок, решта — з 4-ю (номер мишки)."""
    if device:
        return "%d,%d,%s,%d\n" % (ts, pct, _ch(ch), device)
    return "%d,%d,%s\n" % (ts, pct, _ch(ch))


def append(percent, charging, now=None, file=None, device=0):
    """Додає відлік, якщо змінився заряд/зарядка або минуло 10 хв."""
    now = now or time.time()
    last = _last.get(device)
    if last and last[1] == percent and last[2] == charging and now - last[0] < MIN_STEP_SECONDS:
        return False
    _last[device] = (now, percent, charging)
    try:
        with open(file or path(), "a", encoding="utf-8") as f:
            f.write(_line(now, percent, charging, device))
        return True
    except OSError:
        return False


def _rows(days, now=None, file=None):
    """[(epoch, percent, charging|None, device)] усіх мишок за останні `days` днів."""
    now = now or time.time()
    since = now - days * 86400
    out = []
    try:
        with open(file or path(), encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) not in (3, 4):
                    continue
                try:
                    ts, pct = int(parts[0]), int(parts[1])
                    dev = int(parts[3]) if len(parts) == 4 else 0
                except ValueError:
                    continue
                if ts >= since:
                    out.append((ts, pct, None if parts[2] == "-" else parts[2] == "1", dev))
    except OSError:
        pass
    return out


def load(days=7, now=None, file=None, device=0):
    """Повертає [(epoch, percent, charging|None)] однієї мишки за останні `days` днів."""
    return [(ts, pct, ch) for ts, pct, ch, dev in _rows(days, now, file) if dev == device]


def prune(file=None, now=None):
    """Видаляє записи старші за KEEP_DAYS (викликається при старті)."""
    file = file or path()
    rows = _rows(KEEP_DAYS, now=now, file=file)
    try:
        with open(file, "w", encoding="utf-8") as f:
            for ts, pct, ch, dev in rows:
                f.write(_line(ts, pct, ch, dev))
    except OSError:
        pass


def estimate_hours_left(samples):
    """Оцінка, скільки годин лишилось, за останнім відрізком розряду.

    Беремо останній безперервний відрізок без зарядки/зростання заряду,
    лінійна регресія по ньому. Потрібно ≥ 30 хв і падіння ≥ 2 п.п.
    """
    if len(samples) < 2:
        return None
    start = 0
    for i in range(1, len(samples)):
        if samples[i][1] > samples[i - 1][1] or samples[i][2]:
            start = i
    seg = samples[start:]
    if seg and seg[-1][2]:
        return None  # зараз заряджається
    if len(seg) < 2:
        return None
    t0 = seg[0][0]
    xs = [(t - t0) / 3600.0 for t, _, _ in seg]
    ys = [p for _, p, _ in seg]
    if xs[-1] < 0.5 or ys[0] - ys[-1] < 2:
        return None
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom  # п.п. за годину (<0)
    if slope >= -0.01:
        return None
    return max(0.0, ys[-1] / -slope)


def stats(samples, now=None):
    """Повертає міні-статистику:
    - drain_per_hour: середня швидкість розряду (%/год) за останнім відрізком або None
    - last_full_hours: скільки годин тому заряд був >= 99% (або заряджався) або None
    """
    now = now or time.time()
    last_full_ts = None
    for ts, pct, ch in samples:
        if pct >= 99 or ch is True:
            last_full_ts = ts
    last_full_hours = max(0.0, (now - last_full_ts) / 3600.0) if last_full_ts is not None else None

    drain_per_hour = None
    if len(samples) >= 2:
        start = 0
        for i in range(1, len(samples)):
            if samples[i][1] > samples[i - 1][1] or samples[i][2]:
                start = i
        seg = samples[start:]
        if len(seg) >= 2 and not seg[-1][2]:
            t0 = seg[0][0]
            xs = [(t - t0) / 3600.0 for t, _, _ in seg]
            ys = [p for _, p, _ in seg]
            if xs[-1] >= 0.5 and ys[0] - ys[-1] >= 2:
                n = len(xs)
                mx, my = sum(xs) / n, sum(ys) / n
                denom = sum((x - mx) ** 2 for x in xs)
                if denom > 0:
                    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
                    if slope <= -0.01:
                        drain_per_hour = -slope
    return {"drain_per_hour": drain_per_hour, "last_full_hours": last_full_hours}


def export_csv(dest, days=KEEP_DAYS, file=None, names=None):
    """Зберігає історію всіх мишок у CSV (UTF-8 з BOM, щоб Excel бачив кирилицю).
    names: {номер мишки: назва}. Повертає кількість рядків."""
    rows = _rows(days, file=file)
    names = names or {}
    with open(dest, "w", encoding="utf-8-sig", newline="") as f:
        f.write("datetime,percent,charging,mouse\r\n")
        for ts, pct, ch, dev in rows:
            state = "" if ch is None else ("yes" if ch else "no")
            name = str(names.get(dev, "mouse %d" % dev)).replace(",", " ")
            f.write("%s,%d,%s,%s\r\n" % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)),
                                           pct, state, name))
    return len(rows)
