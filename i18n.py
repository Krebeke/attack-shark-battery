# -*- coding: utf-8 -*-
"""Рядки інтерфейсу: українська / англійська. t("ключ", арг, ...) підставляє {0}, {1}…"""
import winutil

_lang = "uk"

S = {
    # трей
    "menu_open": ("Відкрити", "Open"),
    "menu_refresh": ("Оновити зараз", "Refresh now"),
    "menu_settings": ("Налаштування…", "Settings…"),
    "menu_widget": ("Міні-віджет", "Mini widget"),
    "menu_autostart": ("Автозапуск з Windows", "Start with Windows"),
    "menu_exit": ("Вихід", "Exit"),
    # підказка
    "tip_charging": ("заряджається", "charging"),
    "tip_not_charging": ("не заряджається", "not charging"),
    "tip_not_found": ("Мишку не знайдено", "Mouse not found"),
    "tip_asleep": ("Мишка спить (останній заряд {0}%)", "Mouse is asleep (last charge {0}%)"),
    "tip_asleep_nopct": ("Мишка спить", "Mouse is asleep"),
    "tip_config": ("Помилка config.json", "config.json error"),
    # сповіщення
    "notif_low": ("Низький заряд мишки: {0}%", "Mouse battery low: {0}%"),
    "notif_low_again": ("Мишка досі розряджена: {0}%. Поставте на зарядку.",
                        "Mouse is still low: {0}%. Please charge it."),
    "notif_full": ("Заряд 100% — можна відключати від зарядки.", "Fully charged (100%) — you can unplug."),
    "already_running": ("Програма вже запущена. Шукайте значок біля годинника (можливо, за стрілкою ^).",
                        "The app is already running. Look for the icon near the clock (maybe behind the ^ arrow)."),
    # головне вікно
    "main_title": ("Attack Shark — заряд мишки", "Attack Shark — mouse battery"),
    "status_charging": ("Заряджається", "Charging"),
    "status_not_charging": ("Не заряджається", "Not charging"),
    "status_unknown": ("Статус зарядки невідомий", "Charging status unknown"),
    "status_asleep": ("Мишка спить (останній відомий заряд)", "Mouse is asleep (last known charge)"),
    "status_off": ("Мишку не знайдено — вимкнена або не підключена", "Mouse not found — turned off or not connected"),
    "status_config": ("Помилка config.json", "config.json error"),
    "left": ("Залишилось: {0}", "Time left: {0}"),
    "updated": ("Оновлено: {0}", "Updated: {0}"),
    "history": ("Історія заряду", "Battery history"),
    "range_24h": ("24 години", "24 hours"),
    "range_7d": ("7 днів", "7 days"),
    "range_30d": ("30 днів", "30 days"),
    "legend": ("синя лінія — розряд, зелена — зарядка", "blue line — discharging, green — charging"),
    "no_history": ("Історії ще немає — зачекайте кілька опитувань", "No history yet — wait for a few polls"),
    "btn_refresh": ("Оновити", "Refresh"),
    "btn_settings": ("Налаштування…", "Settings…"),
    "btn_export": ("Експорт CSV…", "Export CSV…"),
    "btn_close": ("Закрити", "Close"),
    "unit_h": ("{0} год", "{0} h"),
    "unit_d": ("{0} дн", "{0} d"),
    "unit_m": ("{0} хв", "{0} min"),
    "export_done": ("Збережено рядків: {0}", "Rows saved: {0}"),
    "export_error": ("Не вдалось зберегти: {0}", "Could not save: {0}"),
    # налаштування
    "set_title": ("Налаштування — Attack Shark Battery", "Settings — Attack Shark Battery"),
    "grp_icon": ("Вигляд іконки в треї", "Tray icon appearance"),
    "lbl_style": ("Стиль", "Style"),
    "style_windows": ("Як у Windows", "Like Windows"),
    "style_colored": ("Кольоровий", "Colored"),
    "lbl_font": ("Шрифт", "Font"),
    "lbl_color": ("Колір цифр", "Digit color"),
    "color_theme": ("За темою Windows (білі / чорні)", "By Windows theme (white / black)"),
    "color_status": ("За рівнем заряду (зелені / жовті / червоні)", "By charge level (green / yellow / red)"),
    "chk_outline": ("Темний контур навколо цифр", "Dark outline around digits"),
    "chk_red": ("Червоні цифри, коли заряд нижче 20%", "Red digits below 20%"),
    "lbl_height": ("Висота цифр", "Digit height"),
    "lbl_preview": ("Перегляд (світла і темна панель):", "Preview (light and dark taskbar):"),
    "grp_work": ("Робота", "Behavior"),
    "lbl_poll": ("Опитувати кожні (сек)", "Poll every (sec)"),
    "lbl_low": ("Сповіщення нижче (%)", "Alert below (%)"),
    "lbl_remind": ("Нагадувати кожні (хв, 0 — вимкнено)", "Remind every (min, 0 = off)"),
    "chk_full": ("Сповіщати, коли заряд 100%", "Notify when charge is 100%"),
    "lbl_idle": ("Опитувати рідше, якщо за ПК нікого (хв, 0 — вимкнено)",
                 "Poll less often when away (min, 0 = off)"),
    "chk_autostart": ("Запускати разом із Windows", "Start with Windows"),
    "chk_detect": ("Автоматично шукати відому мишку, якщо вказана не знайдена",
                   "Auto-detect a known mouse if the configured one is not found"),
    "grp_app": ("Програма", "Application"),
    "lbl_lang": ("Мова", "Language"),
    "lang_auto": ("Автоматично", "Automatic"),
    "lang_uk": ("Українська", "Українська"),
    "lang_en": ("English", "English"),
    "lbl_theme": ("Тема вікон", "Window theme"),
    "theme_auto": ("Як у Windows", "Like Windows"),
    "theme_light": ("Світла", "Light"),
    "theme_dark": ("Темна", "Dark"),
    "chk_widget": ("Показувати міні-віджет поверх екрана", "Show floating mini widget"),
    "grp_mouse": ("Мишка", "Mouse"),
    "btn_find": ("Знайти мишку…", "Find mouse…"),
    "mouse_line": ("Attack Shark {0} — {1}, інтерфейс {2}", "Attack Shark {0} — {1}, interface {2}"),
    "cfg_error": ("Помилка в config.json", "Error in config.json"),
    "res_line": ("Ресурси програми: пам'ять {0} МБ · CPU {1}% (середнє)",
                 "App resources: RAM {0} MB · CPU {1}% (average)"),
    "btn_save": ("Зберегти", "Save"),
    "btn_cancel": ("Скасувати", "Cancel"),
    "err_numbers": ("Числові поля мають бути цілими числами.", "Numeric fields must be whole numbers."),
    "err_save": ("Не вдалось зберегти: {0}", "Could not save: {0}"),
    # майстер
    "wiz_title": ("Пошук мишки", "Find mouse"),
    "wiz_known": ("1. Відомі моделі", "1. Known models"),
    "wiz_none": ("(відомих моделей серед підключених пристроїв не знайдено)",
                 "(no known models among connected devices)"),
    "wiz_use": ("Використати вибрану", "Use selected"),
    "wiz_saved": ("Збережено: {0}", "Saved: {0}"),
    "wiz_learn": ("2. Навчання за відсотком з офіційного драйвера", "2. Learn from the official driver's percentage"),
    "wiz_learn_help": (
        "Увімкніть мишку, відкрийте офіційну програму Attack Shark і подивіться, який там заряд. "
        "Введіть це число нижче, оберіть ресивер і натисніть «Почати». Протягом ~12 секунд "
        "не рухайте мишку й не натискайте кнопки — програма слухатиме дані ресивера й знайде "
        "байт, що дорівнює цьому числу.",
        "Turn the mouse on, open the official Attack Shark app and note the charge it shows. "
        "Enter it below, pick the receiver and press Start. For ~12 seconds do not move the "
        "mouse or press buttons — the app will listen to the receiver and look for a byte "
        "equal to that number."),
    "lbl_device": ("Пристрій", "Device"),
    "lbl_pct": ("Заряд у драйвері (%)", "Charge in driver (%)"),
    "btn_start": ("Почати", "Start"),
    "wiz_listening": ("Слухаю пристрій… не рухайте мишку.", "Listening… do not move the mouse."),
    "wiz_pick_dev": ("Оберіть пристрій зі списку.", "Pick a device from the list."),
    "wiz_bad_pct": ("Введіть заряд із драйвера числом від 1 до 100.", "Enter the charge from the driver (1–100)."),
    "wiz_error": ("Помилка: {0}", "Error: {0}"),
    "wiz_nothing": (
        "Прийнято репортів: {0}, але байта з таким значенням не знайдено. Перевірте, що число збігається "
        "з драйвером, мишка ввімкнена й не рухається. Деякі моделі віддають заряд лише у відповідь на "
        "запит — тоді потрібен дамп USBPcap (див. README).",
        "Reports received: {0}, but no byte with that value was found. Check that the number matches the "
        "driver and the mouse is on and still. Some models only report charge in reply to a request — "
        "then a USBPcap dump is needed (see README)."),
    "wiz_found": ("Знайдено варіантів: {0} (кращі зверху). Оберіть і натисніть «Застосувати».",
                  "Candidates found: {0} (best first). Select one and press Apply."),
    "wiz_cand": ("інтерфейс {0} · usage {1}/{2} · байт {3} · збігів {4} з {5} · {6}",
                 "interface {0} · usage {1}/{2} · byte {3} · hits {4} of {5} · {6}"),
    "btn_apply": ("Застосувати вибране", "Apply selected"),
    "wiz_applied": ("Збережено. Значок оновиться за кілька секунд.", "Saved. The icon will update in a few seconds."),
    "wiz_charge": ("3. Статус «заряджається»", "3. \"Charging\" status"),
    "wiz_charge_help": (
        "Спершу натисніть «Записати БЕЗ зарядки» (мишка не на зарядці). Потім поставте мишку на зарядку "
        "(док або кабель), зачекайте 3 секунди й натисніть «Записати НА зарядці».",
        "First press \"Record NOT charging\" (mouse not on charge). Then put the mouse on charge "
        "(dock or cable), wait 3 seconds and press \"Record WHILE charging\"."),
    "btn_cap_off": ("Записати БЕЗ зарядки", "Record NOT charging"),
    "btn_cap_on": ("Записати НА зарядці", "Record WHILE charging"),
    "wiz_cap_got": ("Записано репортів: {0}.", "Reports recorded: {0}."),
    "wiz_cap_none": (
        "Репортів не отримано. Під час зарядки кабелем мишка може перейти в дротовий режим, і ресивер "
        "мовчить — тоді статус зарядки через ресивер недоступний. Спробуйте зарядку на док-станції.",
        "No reports received. While charging by cable the mouse may switch to wired mode and the receiver "
        "goes silent — then charging status is not available via the receiver. Try the charging dock."),
    "wiz_charge_found": ("Знайдено: байт {0} — {1} без зарядки, {2} на зарядці.",
                         "Found: byte {0} — {1} when not charging, {2} when charging."),
    "wiz_charge_none": ("Байта, що стабільно відрізняється, не знайдено.", "No byte that differs reliably was found."),
    "btn_apply_charge": ("Застосувати", "Apply"),
    "wiz_charge_saved": ("Збережено. Статус зарядки з'явиться за кілька секунд.",
                         "Saved. The charging status will appear in a few seconds."),
    # оновлення
    "menu_update": ("Оновити до {0}…", "Update to {0}…"),
    "notif_update": ("Доступна нова версія {0}. Відкрийте меню значка → «Оновити».",
                     "New version {0} is available. Open the tray menu → \"Update\"."),
    "notif_uptodate": ("У вас остання версія.", "You have the latest version."),
    "notif_upd_failed": ("Не вдалось перевірити оновлення.", "Could not check for updates."),
    "notif_upd_download": ("Завантажую оновлення {0}…", "Downloading update {0}…"),
    "upd_title": ("Оновлення Attack Shark Battery", "Attack Shark Battery update"),
    "upd_confirm": ("Доступна версія {0} (у вас {1}).\n\n{2}\n\nЗавантажити й встановити зараз? Програма перезапуститься.",
                    "Version {0} is available (you have {1}).\n\n{2}\n\nDownload and install now? The app will restart."),
    "grp_update": ("Оновлення", "Updates"),
    "chk_updates": ("Перевіряти нові версії на GitHub", "Check for new versions on GitHub"),
    "lbl_version": ("Версія: {0}", "Version: {0}"),
    "btn_check_updates": ("Перевірити зараз", "Check now"),
    # кілька мишок
    "menu_clickthrough": ("Віджет: пропускати кліки", "Widget: click-through"),
    "lbl_mouse": ("Мишка:", "Mouse:"),
    "tab_icon": ("Іконка", "Icon"),
    "tab_work": ("Робота", "General"),
    "tab_widget": ("Віджет", "Widget"),
    "tab_mice": ("Мишки", "Mice"),
    "grp_widget": ("Віджет поверх екрана", "Floating widget"),
    "lbl_wmode": ("Положення", "Position"),
    "wmode_top": ("Поверх усіх вікон", "Always on top"),
    "wmode_desktop": ("Прикріплений до робочого столу (під вікнами)", "Pinned to the desktop (under windows)"),
    "lbl_wsize": ("Розмір", "Size"),
    "wsize_compact": ("Компакт (лише цифри)", "Compact (digits only)"),
    "wsize_bar": ("Смуга (цифри + шкала)", "Bar (digits + gauge)"),
    "wsize_graph": ("З міні-графіком за 24 год", "With 24 h mini graph"),
    "lbl_wscale": ("Масштаб", "Scale"),
    "lbl_wopacity": ("Прозорість", "Opacity"),
    "chk_wsnap": ("Прилипати до країв екрана", "Snap to screen edges"),
    "chk_wclick": ("Клікати крізь віджет (вимкнути можна в меню значка)",
                   "Click through the widget (turn off from the tray menu)"),
    "chk_whide": ("Ховати у повноекранних іграх і відео", "Hide in fullscreen games and videos"),
    "chk_wred": ("Червона рамка й цифри, коли заряд нижче порогу сповіщення",
                 "Red frame and digits when below the alert threshold"),
    "widget_hint": ("Перетягуйте віджет мишею. Колесо над віджетом змінює масштаб, подвійний клік відкриває вікно.",
                    "Drag the widget with the mouse. Mouse wheel over it changes scale, double-click opens the window."),
    "grp_mice": ("Підключені мишки", "Configured mice"),
    "mice_hint": ("Зміни в цьому списку застосовуються одразу, без «Зберегти». Основна мишка — перша.",
                  "Changes in this list apply immediately, no need to press Save. The first mouse is the primary one."),
    "btn_add_known": ("Додати знайдену", "Add detected"),
    "btn_add_learn": ("Додати нову (навчання)…", "Add new (learn)…"),
    "btn_rename": ("Перейменувати…", "Rename…"),
    "btn_remove": ("Видалити", "Remove"),
    "ask_name": ("Назва мишки:", "Mouse name:"),
    "mice_none_known": ("Нових відомих мишок серед підключених не знайдено. Увімкніть мишку й спробуйте ще раз, "
                        "або скористайтесь «Додати нову (навчання)».",
                        "No new known mice found among connected devices. Turn the mouse on and try again, "
                        "or use \"Add new (learn)\"."),
    "mice_added": ("Додано: {0}", "Added: {0}"),
    "mice_only_one": ("Це єдина мишка — її не можна видалити.", "This is the only mouse — it cannot be removed."),
    "mice_confirm_remove": ("Видалити «{0}» зі списку? Історія заряду лишиться у файлі.",
                            "Remove \"{0}\" from the list? Its charge history stays in the file."),
    "mice_row": ("{0}   [{1}]   {2}", "{0}   [{1}]   {2}"),
    "lbl_target": ("Зберегти для", "Save for"),
    "target_new": ("Нова мишка", "New mouse"),
    # віджет
    "w_click": ("Пропускати кліки (вимкнути — в меню значка)", "Click-through (turn off from the tray menu)"),
    "w_open": ("Відкрити вікно", "Open window"),
    "w_close": ("Закрити віджет", "Close widget"),
    # нові функції (v1.3)
    "chk_quiet_fs": ("Тихий режим сповіщень у повноекранних іграх",
                     "Mute notifications in fullscreen games"),
    "lbl_whotkey": ("Гаряча клавіша (показати/сховати)", "Global hotkey (show/hide)"),
    "hotkey_none": ("Вимкнено", "Disabled"),
    "btn_share": ("Поділитися на GitHub", "Share on GitHub"),
    "btn_add_bt": ("Додати Bluetooth…", "Add Bluetooth…"),
    "bt_title": ("Bluetooth-мишки", "Bluetooth mice"),
    "bt_none": ("Підключених Bluetooth-пристроїв із даними про заряд не знайдено.",
                "No connected Bluetooth devices reporting battery level were found."),
    "bt_pick": ("Оберіть Bluetooth-пристрій для додавання:", "Select a Bluetooth device to add:"),
    "bt_added": ("Додано Bluetooth-пристрій: {0}", "Added Bluetooth device: {0}"),
    "stats_line": ("Розряд: {0} · Останній заряд: {1}", "Drain: {0} · Last full: {1}"),
    "stats_rate": ("≈ {0}%/год", "≈ {0}%/h"),
    "stats_ago": ("{0} тому", "{0} ago"),
}


def set_language(code):
    """Повертає застосований код ('uk' або 'en')."""
    global _lang
    if code not in ("uk", "en"):
        code = winutil.system_language()
    _lang = code
    return _lang


def t(key, *args):
    entry = S.get(key)
    if entry is None:
        return key
    text = entry[0] if _lang == "uk" else entry[1]
    return text.format(*args) if args else text
