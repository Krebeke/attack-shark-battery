# -*- coding: utf-8 -*-
"""Ліниве керування інтерфейсом.

tkinter і всі вікна живуть в окремому потоці, який створюється лише коли потрібне вікно
і завершується, коли закрито останнє. Поки відкритих вікон нема, у пам'яті лише трей і опитування.
Модуль не імпортує tkinter — це робить потік інтерфейсу.
"""
import logging
import queue
import threading

LOG = logging.getLogger("asbattery")


class UiManager:
    def __init__(self, app):
        self.app = app
        self.q = queue.Queue()
        self.lock = threading.Lock()
        self.alive = False
        self.root = None
        self.windows = {}      # назва -> об'єкт вікна (лише в потоці UI)
        self.pal = None
        self.dark = False
        self._mod = None

    # --- виклики з інших потоків ---
    def call(self, name, *args):
        """Виконати ui.<name>(mgr, *args) у потоці UI; потік запускається за потреби."""
        self.q.put((name, args))
        with self.lock:
            if self.alive:
                return
            self.alive = True
        threading.Thread(target=self._run, name="ui", daemon=True).start()

    def call_if_running(self, name, *args):
        with self.lock:
            running = self.alive
        if running:
            self.q.put((name, args))

    def running(self):
        with self.lock:
            return self.alive

    # --- потік UI ---
    def _run(self):
        try:
            import ui  # тут імпортується tkinter
            self._mod = ui
            ui.setup_root(self)
            self.root.after(100, self._pump)
            self.root.mainloop()
        except Exception:
            LOG.exception("помилка потоку інтерфейсу")
        finally:
            try:
                if self.root is not None:
                    self.root.destroy()
            except Exception:
                pass
            self.root = None
            self.windows.clear()
            with self.lock:
                self.alive = False
                restart = not self.q.empty()
            if restart:  # хтось додав виклик, поки ми завершувались
                with self.lock:
                    self.alive = True
                threading.Thread(target=self._run, name="ui", daemon=True).start()

    def _pump(self):
        try:
            while True:
                name, args = self.q.get_nowait()
                try:
                    getattr(self._mod, name)(self, *args)
                except Exception:
                    LOG.exception("помилка UI-виклику %s", name)
        except queue.Empty:
            pass
        if not self.windows and self.q.empty():
            self.root.quit()  # відкритих вікон нема — звільняємо tkinter
            return
        self.root.after(150, self._pump)
