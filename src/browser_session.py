from __future__ import annotations

import os
import json
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import requests

DEFAULT_CDP_PORT = None
DEFAULT_PROFILE_DIR = Path("data/chrome/yourtextguru")
DEFAULT_START_URL = "https://yourtext.guru/login"
PORT_METADATA_FILE = ".seo-writer-chrome.json"


def find_chrome_binary() -> str:
    env_path = os.environ.get("SEO_WRITER_CHROME_BIN")
    if env_path:
        return env_path

    candidates = [
        "google-chrome",
        "google-chrome-stable",
        "chromium-browser",
        "chromium",
        "/usr/bin/google-chrome",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for candidate in candidates:
        resolved = shutil.which(candidate) if "/" not in candidate else candidate
        if resolved and Path(resolved).exists():
            return resolved
    raise RuntimeError("Chrome/Chromium binary not found. Set SEO_WRITER_CHROME_BIN to the executable path.")


def cdp_endpoint(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def get_cdp_version(port: int | None, timeout: float = 1.0) -> dict[str, Any] | None:
    if port is None:
        return None
    try:
        response = requests.get(f"{cdp_endpoint(port)}/json/version", timeout=timeout)
        if response.ok:
            return response.json()
    except requests.RequestException:
        return None
    return None


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _metadata_path(profile_dir: str | Path) -> Path:
    return Path(profile_dir) / PORT_METADATA_FILE


def read_profile_port(profile_dir: str | Path) -> int | None:
    path = _metadata_path(profile_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        port = payload.get("port")
        return int(port) if port else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def write_profile_port(profile_dir: str | Path, port: int) -> None:
    path = _metadata_path(profile_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"port": port, "endpoint": cdp_endpoint(port)}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def wait_for_cdp(port: int, timeout: float = 15.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        version = get_cdp_version(port)
        if version:
            return version
        time.sleep(0.25)
    raise RuntimeError(f"Chrome DevTools endpoint did not become ready on port {port}.")


def launch_chrome(
    profile_dir: str | Path = DEFAULT_PROFILE_DIR,
    port: int | None = DEFAULT_CDP_PORT,
    start_url: str = DEFAULT_START_URL,
    headless: bool = False,
) -> dict[str, Any]:
    profile_path = Path(profile_dir)
    if port is None:
        saved_port = read_profile_port(profile_path)
        if saved_port and get_cdp_version(saved_port):
            port = saved_port
        else:
            port = find_free_port()

    existing = get_cdp_version(port)
    if existing:
        write_profile_port(profile_dir, port)
        return {
            "started": False,
            "pid": None,
            "endpoint": cdp_endpoint(port),
            "port": port,
            "profile_dir": str(profile_dir),
            "browser": existing.get("Browser", ""),
            "message": "Chrome DevTools endpoint is already running.",
        }

    profile_path.mkdir(parents=True, exist_ok=True)
    chrome = find_chrome_binary()
    args = [
        chrome,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_path}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
    ]
    if headless:
        args.extend(["--headless=new", "--disable-gpu"])
    args.append(start_url)

    process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    version = wait_for_cdp(port)
    write_profile_port(profile_path, port)
    return {
        "started": True,
        "pid": process.pid,
        "endpoint": cdp_endpoint(port),
        "port": port,
        "profile_dir": str(profile_path),
        "browser": version.get("Browser", ""),
        "message": "Chrome launched. Log in once in this profile, then reuse it for authenticated tools.",
    }


def ensure_chrome(
    profile_dir: str | Path = DEFAULT_PROFILE_DIR,
    port: int | None = DEFAULT_CDP_PORT,
    start_url: str = DEFAULT_START_URL,
    launch_if_missing: bool = True,
    headless: bool = False,
) -> dict[str, Any]:
    if port is None:
        saved_port = read_profile_port(profile_dir)
        if saved_port and get_cdp_version(saved_port):
            port = saved_port

    version = get_cdp_version(port)
    if version:
        write_profile_port(profile_dir, int(port))
        return {
            "started": False,
            "endpoint": cdp_endpoint(port),
            "port": port,
            "profile_dir": str(profile_dir),
            "browser": version.get("Browser", ""),
        }
    if not launch_if_missing:
        saved = read_profile_port(profile_dir)
        endpoint = cdp_endpoint(saved) if saved else "a saved profile port"
        raise RuntimeError(f"No Chrome DevTools endpoint found at {endpoint}.")
    return launch_chrome(profile_dir=profile_dir, port=port, start_url=start_url, headless=headless)
