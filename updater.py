# -*- coding: utf-8 -*-
"""Перевірка та встановлення оновлень із GitHub Releases.

Мережа використовується лише для: GET api.github.com (остання версія) і завантаження
інсталятора з github.com. Ніяких даних про вас чи мишку не надсилається (лише User-Agent з версією).
Завантажений файл перевіряється за розміром і SHA-256 з метаданих GitHub (якщо вони є).
"""
import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.parse
import urllib.request

import version

API = "https://api.github.com/repos/%s/releases/latest"
HOST_SUFFIXES = ("github.com", "githubusercontent.com")


class UpdateError(Exception):
    pass


def parse_version(text):
    nums = [int(x) for x in re.findall(r"\d+", str(text).split("-")[0])][:3]
    return tuple(nums + [0] * (3 - len(nums)))


def is_newer(candidate, current):
    return parse_version(candidate) > parse_version(current)


def _check_url(url):
    parts = urllib.parse.urlparse(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not any(host == s or host.endswith("." + s) for s in HOST_SUFFIXES):
        raise UpdateError("недовірена адреса оновлення: %s" % url)


def _open(url, timeout=15):
    _check_url(url)
    req = urllib.request.Request(url, headers={
        "User-Agent": "AttackSharkBattery/%s" % version.VERSION,
        "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)


def check(repo, current=None):
    """Повертає dict {version, url, size, sha256, page, notes}, якщо є новіша версія, інакше None."""
    if not re.match(r"^[\w.-]+/[\w.-]+$", repo or ""):
        raise UpdateError("некоректний репозиторій: %r" % repo)
    with _open(API % repo) as resp:
        data = json.load(resp)
    if data.get("draft") or data.get("prerelease"):
        return None
    tag = str(data.get("tag_name", ""))
    if not is_newer(tag, current or version.VERSION):
        return None
    asset = next((a for a in data.get("assets", [])
                  if str(a.get("name", "")).lower().endswith("setup.exe")), None)
    if asset is None:
        raise UpdateError("у релізі %s немає файлу *Setup.exe" % tag)
    digest = str(asset.get("digest") or "")
    return {
        "version": tag.lstrip("vV"),
        "url": asset["browser_download_url"],
        "size": int(asset.get("size") or 0),
        "sha256": digest.split(":", 1)[1].lower() if digest.startswith("sha256:") else "",
        "page": data.get("html_url", ""),
        "notes": (data.get("body") or "").strip()[:600],
    }


def download(info, progress=None):
    """Завантажує інсталятор у Temp і перевіряє цілісність. Повертає шлях до файлу."""
    dest = os.path.join(tempfile.gettempdir(), "AttackSharkBattery-Setup-%s.exe" % info["version"])
    sha = hashlib.sha256()
    total = 0
    try:
        with _open(info["url"], timeout=30) as resp, open(dest, "wb") as out:
            length = int(resp.headers.get("Content-Length") or info.get("size") or 0)
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                out.write(chunk)
                sha.update(chunk)
                total += len(chunk)
                if progress and length:
                    progress(min(100, total * 100 // length))
        if info.get("size") and total != info["size"]:
            raise UpdateError("розмір файлу не збігається (%d ≠ %d)" % (total, info["size"]))
        if info.get("sha256") and sha.hexdigest() != info["sha256"]:
            raise UpdateError("контрольна сума SHA-256 не збігається")
    except Exception:
        try:
            os.remove(dest)
        except OSError:
            pass
        raise
    return dest


def launch_installer(path):
    """Тихо запускає інсталятор (Inno Setup); він сам закриє програму й запустить нову версію."""
    flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                     close_fds=True, creationflags=flags if os.name == "nt" else 0)
