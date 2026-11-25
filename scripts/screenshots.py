"""Capture real screenshots with headless Chrome over CDP (no extra deps beyond websocket-client)."""
from __future__ import annotations

import base64
import http.cookiejar
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import websocket

BASE = "http://127.0.0.1:8000"
PORT = 9333
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
OUT = Path.home() / "Desktop" / "FUTURE PATH - لقطات"
CREDS = Path.home() / "Desktop" / "FUTURE PATH - بيانات الدخول.txt"


def login_token(email: str, password: str) -> str:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def post(path, data):
        body = urllib.parse.urlencode(data, encoding="utf-8").encode()
        req = urllib.request.Request(BASE + path, data=body)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            return opener.open(req)
        except urllib.error.HTTPError as exc:
            return exc

    html = opener.open(BASE + "/auth/login").read().decode("utf-8")
    csrf = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
    post("/auth/login", {"csrf": csrf, "email": email, "password": password})
    for cookie in jar:
        if cookie.name == "fp_session":
            return cookie.value
    raise SystemExit("login failed: no session cookie")


class CDP:
    def __init__(self, ws_url: str) -> None:
        self.ws = websocket.create_connection(ws_url, timeout=30)
        self.next_id = 0

    def send(self, method: str, params: dict | None = None) -> dict:
        self.next_id += 1
        self.ws.send(json.dumps({"id": self.next_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get("id") == self.next_id:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})

    def close(self) -> None:
        self.ws.close()


def wait_ready(cdp: CDP) -> None:
    for _ in range(80):
        result = cdp.send("Runtime.evaluate", {"expression": "document.readyState", "returnByValue": True})
        if result.get("result", {}).get("value") == "complete":
            return
        time.sleep(0.1)


def capture(cdp: CDP, url: str, filename: str, token: str | None = None,
            width: int = 1440, height: int = 950, mobile: bool = False,
            clip: tuple[int, int, int, int] | None = None) -> None:
    cdp.send("Emulation.setDeviceMetricsOverride", {
        "width": width, "height": height, "deviceScaleFactor": 1 if not mobile else 2, "mobile": mobile,
    })
    cdp.send("Network.clearBrowserCookies")
    if token:
        cdp.send("Network.setCookie", {
            "name": "fp_session", "value": token, "domain": "127.0.0.1", "path": "/", "httpOnly": True,
        })
    cdp.send("Page.navigate", {"url": url})
    wait_ready(cdp)
    time.sleep(2.2)
    height_px = cdp.send("Runtime.evaluate", {
        "expression": "Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)",
        "returnByValue": True,
    })["result"]["value"]
    if clip:
        x, y, w, h = clip
    else:
        x, y, w, h = 0, 0, width, min(int(height_px), 6000)
    result = cdp.send("Page.captureScreenshot", {
        "format": "png",
        "captureBeyondViewport": True,
        "fromSurface": True,
        "clip": {"x": x, "y": y, "width": w, "height": h, "scale": 1},
    })
    (OUT / filename).write_bytes(base64.b64decode(result["data"]))
    print(f"saved {filename} ({w}x{h})")


def main() -> None:
    if not CHROME.exists():
        raise SystemExit("Chrome not found")
    text = CREDS.read_text(encoding="utf-8")
    passwords = re.findall(r"كلمة المرور:\s*(\S+)", text)
    student_token = login_token("ahmed.demo@example.com", passwords[0])
    admin_token = login_token("admin@future-path.app", passwords[1])

    OUT.mkdir(parents=True, exist_ok=True)
    profile_dir = tempfile.mkdtemp(prefix="fp-chrome-")
    chrome = subprocess.Popen([
        str(CHROME), "--headless=new", "--disable-gpu", "--hide-scrollbars",
        f"--remote-debugging-port={PORT}", f"--user-data-dir={profile_dir}",
        "--no-first-run", "--no-default-browser-check", "--window-size=1440,950", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        for _ in range(80):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1)
                break
            except Exception:
                time.sleep(0.25)
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?about:blank", method="PUT")
        target = json.loads(urllib.request.urlopen(req).read())
        cdp = CDP(target["webSocketDebuggerUrl"])
        cdp.send("Page.enable")
        cdp.send("Network.enable")

        listing = urllib.request.urlopen(BASE + "/opportunities").read().decode("utf-8")
        opp_id = re.search(r'href="(/opportunities/[0-9a-f-]{36})"', listing).group(1)

        capture(cdp, BASE + "/", "01-الرئيسية.png")
        capture(cdp, BASE + "/", "01b-الهيرو.png", clip=(0, 66, 1440, 760))
        capture(cdp, BASE + "/auth/login", "02-تسجيل-الدخول.png")
        capture(cdp, BASE + "/opportunities", "03-الفرص.png")
        capture(cdp, BASE + opp_id, "04-تفاصيل-فرصة.png")
        capture(cdp, BASE + "/skills", "05-مسارات-المهارات.png")
        capture(cdp, BASE + "/dashboard", "06-لوحة-الطالب.png", student_token)
        capture(cdp, BASE + "/profile", "07-الملف-المهني.png", student_token)
        capture(cdp, BASE + "/cv", "08-السيرة-الذاتية.png", student_token)
        capture(cdp, BASE + "/discover", "09-اكتشف-نفسك.png", student_token)
        capture(cdp, BASE + "/applications", "10-طلباتي.png", student_token)
        capture(cdp, BASE + "/admin", "11-لوحة-الإدارة.png", admin_token)
        capture(cdp, BASE + "/admin/opportunities", "12-إدارة-الفرص.png", admin_token)
        capture(cdp, BASE + "/admin/applications", "13-إدارة-الطلبات.png", admin_token)
        capture(cdp, BASE + "/", "14-الجوال-الرئيسية.png", width=390, height=844, mobile=True)
        cdp.close()
    finally:
        chrome.terminate()
        try:
            chrome.wait(timeout=10)
        except subprocess.TimeoutExpired:
            chrome.kill()
        shutil.rmtree(profile_dir, ignore_errors=True)
    print(f"Screenshots in: {OUT}")


if __name__ == "__main__":
    main()
