# -*- coding: utf-8 -*-
"""Допоміжний скрипт: пошук мишки серед HID-пристроїв і перевірка команди.

  py find_device.py list                 # усі HID-інтерфейси (VID/PID, usage page, usage)
  py find_device.py list --grep shark    # фільтр за назвою/виробником
  py find_device.py probe                # виконати запит із config.json, показати байти
  py find_device.py probe --count 10 --interval 2
  py find_device.py listen --seconds 30  # пасивно слухати input-репорти (без запитів)

ВАЖЛИВО: скрипт сам нічого "навмання" не відправляє. Записувати у пристрій
варто лише ті байти, які ви побачили в дампі офіційного драйвера.
"""
import argparse
import sys
import time

import hidreader as hr

try:
    import hid
except ImportError:
    hid = None


def need_hid():
    if hid is None:
        print("Не встановлено hidapi:  pip install hidapi   (саме hidapi, а не hid)")
        sys.exit(2)


def s(value):
    return value if isinstance(value, str) else str(value)


def cmd_list(args):
    need_hid()
    devices = hid.enumerate(0, 0)
    if args.grep:
        g = args.grep.lower()
        devices = [d for d in devices
                   if g in (s(d["product_string"]) + " " + s(d["manufacturer_string"])).lower()]
    devices.sort(key=lambda d: (d["vendor_id"], d["product_id"], d["interface_number"],
                                d["usage_page"], d["usage"]))
    if not devices:
        print("Нічого не знайдено.")
        return 1

    last = None
    for d in devices:
        key = (d["vendor_id"], d["product_id"])
        if key != last:
            last = key
            print("\n=== VID:PID %04X:%04X  %s | %s" % (
                d["vendor_id"], d["product_id"], s(d["manufacturer_string"]), s(d["product_string"])))
        mark = "   <-- vendor-specific (кандидат)" if d["usage_page"] >= 0xFF00 else ""
        print("  interface=%-2s usage_page=0x%04X usage=0x%04X%s" % (
            d["interface_number"], d["usage_page"], d["usage"], mark))
        if args.paths:
            print("      path=%s" % d["path"].decode(errors="replace"))
    print("\nПідказка: відкрийте/закрийте мишку (або вимкніть і ввімкніть) і порівняйте списки,")
    print("щоб побачити, які записи належать саме їй. Мишка через ресивер і через кабель")
    print("зазвичай мають РІЗНІ PID — тоді вкажіть обидва в config.json: \"pid\": [\"0x..\", \"0x..\"].")
    return 0


def dump(raw):
    print("      індекс:  " + " ".join("%02d" % i for i in range(min(len(raw), 32))))
    print("      байти :  " + " ".join("%02X" % b for b in raw[:32]))
    if len(raw) > 32:
        print("      ... усього %d байт" % len(raw))


def cmd_probe(args):
    cfg = hr.load_config(args.config)
    cands = hr.find_candidates(cfg)
    print("Кандидатів за фільтром config.json: %d" % len(cands))
    if not cands:
        print("Перевірте vid/pid/usage_page/usage/interface_number (див. команду list).")
        return 1

    for n in range(args.count):
        if n:
            time.sleep(args.interval)
        print("\n--- спроба %d/%d ---" % (n + 1, args.count))
        for i, info in enumerate(cands):
            print("  [%d] interface=%s usage_page=0x%04X usage=0x%04X" % (
                i, info["interface_number"], info["usage_page"], info["usage"]))
            try:
                raw, _ = hr.read_raw(cfg, [info])
            except Exception as e:
                print("      помилка: %s" % e)
                continue
            dump(raw)
            try:
                st = hr.parse_status(raw, cfg, info)
                print("      => заряд %d%%, зарядка: %s" % (
                    st.percent, {None: "невідомо", True: "так", False: "ні"}[st.charging]))
            except hr.ReadError as e:
                print("      => розбір не вдався: %s" % e)
    return 0


def cmd_listen(args):
    need_hid()
    cfg = hr.load_config(args.config)
    cands = hr.find_candidates(cfg)
    if not cands:
        print("Кандидатів немає — перевірте config.json.")
        return 1
    info = cands[min(args.index, len(cands) - 1)]
    print("Слухаю interface=%s usage_page=0x%04X usage=0x%04X, %d с. Ctrl+C — зупинити."
          % (info["interface_number"], info["usage_page"], info["usage"], args.seconds))
    dev = hid.device()
    dev.open_path(info["path"])
    try:
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            data = dev.read(64, 1000)
            if data:
                print("%s  %s" % (time.strftime("%H:%M:%S"), " ".join("%02X" % b for b in data)))
    except KeyboardInterrupt:
        pass
    finally:
        dev.close()
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")

    pl = sub.add_parser("list", help="перелік усіх HID-інтерфейсів")
    pl.add_argument("--grep", help="підрядок у назві/виробнику")
    pl.add_argument("--paths", action="store_true", help="показувати шляхи пристроїв")

    pp = sub.add_parser("probe", help="виконати запит із config.json")
    pp.add_argument("--config")
    pp.add_argument("--count", type=int, default=1)
    pp.add_argument("--interval", type=float, default=2.0)

    ps = sub.add_parser("listen", help="слухати input-репорти")
    ps.add_argument("--config")
    ps.add_argument("--seconds", type=int, default=30)
    ps.add_argument("--index", type=int, default=0, help="номер кандидата зі списку probe")

    args = p.parse_args()
    handler = {"list": cmd_list, "probe": cmd_probe, "listen": cmd_listen}.get(args.cmd)
    if not handler:
        args = p.parse_args(["list"])
        handler = cmd_list
    try:
        sys.exit(handler(args))
    except hr.ConfigError as e:
        print("Помилка конфігу:", e)
        sys.exit(2)


if __name__ == "__main__":
    main()
