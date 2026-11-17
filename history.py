# -*- coding: utf-8 -*-
"""Історія заряду (CSV у %APPDATA%\\AttackSharkBattery\\history.csv) і оцінка часу роботи."""
import os
import time

import hidreader as hr

KEEP_DAYS = 30
MIN_STEP_SECONDS = 600  # писати не частіше, ніж раз на 10 хв, якщо заряд не змінився

_last = None  # (epoch, percent, charging)


def path():
    return os.path.join(hr.data_dir(), "history.csv")


def _ch(value):
    return "-" if value is None else ("1" if value else "0")


def append(percent, charging, now=None, file=None):
    """Додає відлік, якщо змінився заряд/зарядка або минуло 10 хв."""
    global _last
    now = now or time.time()
    if _last and _last[1] == percent and _last[2] == charging and now - _last[0] < MIN_STEP_SECONDS:
        return False
    _last = (now, percent, charging)
    try:
        with open(file or path(), "a", encoding="utf-8") as f:
            f.write("%d,%d,%s\n" % (now, percent, _ch(charging)))
        return True
    except OSError:
        return False


def load(days=7, now=None, file=None):
    """Повертає [(epoch, percent, charging|None)] за останні `days` днів."""
    now = now or time.time()
    since = now - days * 86400
    out = []
    try:
        with open(file or path(), encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) != 3:
                    continue
                try:
                    ts, pct = int(parts[0]), int(parts[1])
                except ValueError:
                    continue
                if ts >= since:
                    out.append((ts, pct, None if parts[2] == "-" else parts[2] == "1"))
    except OSError:
        pass
    return out


def prune(file=None, now=None):
    """Видаляє записи старші за KEEP_DAYS (викликається при старті)."""
    file = file or path()
    rows = load(KEEP_DAYS, now=now, file=file)
    try:
        with open(file, "w", encoding="utf-8") as f:
            for ts, pct, ch in rows:
                f.write("%d,%d,%s\n" % (ts, pct, _ch(ch)))
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


def export_csv(dest, days=KEEP_DAYS, file=None):
    """Зберігає історію у CSV (UTF-8 з BOM, щоб Excel бачив кирилицю). Повертає кількість рядків."""
    rows = load(days, file=file)
    with open(dest, "w", encoding="utf-8-sig", newline="") as f:
        f.write("datetime,percent,charging\r\n")
        for ts, pct, ch in rows:
            state = "" if ch is None else ("yes" if ch else "no")
            f.write("%s,%d,%s\r\n" % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)), pct, state))
    return len(rows)
