import json
import os
import random
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "https://rblx.earth"
GIVEAWAY_URL = "https://rblx.earth/giveaway"

CHECK_INTERVAL_SEC = 60         # Every 1 minute
SESSION_DURATION_SEC = 5 * 60   # 5-minute loop

DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL",
    "https://discord.com/api/webhooks/1573287473558061077/TWkaPHq1s9_hTUfFj5JBjbnqdtRAyH1OxdbFOygM8R0NiwVmJgzeXSU16ca3IEeXiOXx",
).strip()

ALOK_USER_DATA = '{"username":"Alok49x","_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyYmx4VXNlcm5hbWUiOiJBbG9rNDl4IiwicmJseElkIjoiMTE0MDg1Mzk1NjUiLCJpYXQiOjE3OTUxNjM3MzR9.G6bOIKIorc1BZ5kYSQsmlx5zP9SDIXg2TH25u6alIGc","_robux":"1.43","_thumbnail":"https://tr.rbxcdn.com/30DAY-AvatarBust-051F4476AFFD563E8DFB42984F606CE5-Png/420/420/AvatarBust/Png/noFilter","_adminToken":""}'


def log(msg: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


def send_discord(message: str) -> None:
    if not DISCORD_WEBHOOK_URL or "discord.com/api/webhooks/" not in DISCORD_WEBHOOK_URL:
        return
    try:
        payload = json.dumps({"content": message}).encode("utf-8")
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            log(f"[Discord] Sent: {message} (HTTP {resp.status})")
    except Exception as exc:
        log(f"[Discord] Failed to send notification: {exc}")


def human_sleep(min_sec: float, max_sec: float) -> None:
    time.sleep(random.uniform(min_sec, max_sec))


def inject_local_storage(page, user_data_str: str) -> None:
    page.evaluate(
        """(val) => {
            localStorage.setItem("userData", val);
        }""",
        user_data_str,
    )


def is_already_joined(page) -> bool:
    joined_status = page.locator("p.joined[role='status']")
    return joined_status.count() > 0 and joined_status.first.is_visible()


def check_and_join_once(page, user_data_str: str) -> tuple[str, str]:
    try:
        page.goto(GIVEAWAY_URL, wait_until="domcontentloaded")
        human_sleep(1.5, 2.5)

        if "/giveaway" not in page.url:
            inject_local_storage(page, user_data_str)
            page.goto(GIVEAWAY_URL, wait_until="domcontentloaded")
            human_sleep(1.5, 2.5)

        deadline = time.time() + 10
        found_button = False

        while time.time() < deadline:
            if is_already_joined(page):
                return "already_joined", "already joined"

            btn = page.locator("button.re-btn", has_text="Join giveaway").first
            if btn.count() > 0 and btn.is_visible() and btn.is_enabled():
                found_button = True
                break

            time.sleep(0.4)

        if not found_button:
            return "error", f"error (Join button / Joined banner not found at {page.url})"

        btn = page.locator("button.re-btn", has_text="Join giveaway").first
        btn.wait_for(state="visible", timeout=5000)
        human_sleep(0.4, 0.8)

        try:
            btn.click(timeout=6000)
        except Exception:
            # If Angular re-rendered the button right as we clicked, re-query and click once more
            fresh_btn = page.locator("button.re-btn", has_text="Join giveaway").first
            fresh_btn.click(timeout=6000, force=True)

        btn.click(timeout=5000)
        log("[Alok49x] Clicked 'Join giveaway'. Waiting for confirmation...")

        confirm_deadline = time.time() + 12
        while time.time() < confirm_deadline:
            if is_already_joined(page):
                return "joined", "joined"
            time.sleep(0.4)

        return "error", "error (Clicked Join, but confirmation banner did not appear)"

    except Exception as exc:
        return "error", f"error ({exc})"


def main() -> None:
    profile_dir = Path("/tmp/rblx_profile_alok").resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    session_end = time.time() + SESSION_DURATION_SEC
    last_reported_state = None

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=True,
            viewport={"width": 1366, "height": 820},
            locale="en-US",
            args=["--disable-blink-features=AutomationControlled"],
        )

        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.set_default_timeout(15000)

            log(f"[Alok49x] Opening {BASE_URL} to inject session...")
            page.goto(BASE_URL, wait_until="domcontentloaded")
            inject_local_storage(page, ALOK_USER_DATA)

            cycle = 0
            while time.time() < session_end:
                cycle += 1
                loop_start = time.time()
                log(f"[Alok49x] --- Check #{cycle} ---")

                status, detail = check_and_join_once(page, ALOK_USER_DATA)
                log(f"[Alok49x] Result: {detail}")

                if status == "joined":
                    send_discord("✅ **[Alok49x]** joined")
                    last_reported_state = "joined"
                elif status == "already_joined":
                    if last_reported_state not in ("already_joined", "joined"):
                        send_discord("ℹ️ **[Alok49x]** already joined")
                    last_reported_state = "already_joined"
                else:
                    if last_reported_state != "error":
                        send_discord(f"❌ **[Alok49x]** {detail}")
                    last_reported_state = "error"

                elapsed = time.time() - loop_start
                sleep_time = max(5.0, CHECK_INTERVAL_SEC - elapsed)
                if time.time() + sleep_time >= session_end:
                    break
                time.sleep(sleep_time)

            log("[Alok49x] 5-minute loop complete.")

        except Exception as exc:
            send_discord(f"❌ **[Alok49x]** error ({exc})")
            sys.exit(1)
        finally:
            context.close()


if __name__ == "__main__":
    main()
