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

DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL",
    "https://discord.com/api/webhooks/1573287473558061077/TWkaPHq1s9_hTUfFj5JBjbnqdtRAyH1OxdbFOygM8R0NiwVmJgzeXSU16ca3IEeXiOXx",
).strip()

# Alok49x session only
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
            log(f"[Discord] Sent notification (HTTP {resp.status}).")
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
    log("[Alok49x] Injected userData session into localStorage.")


def is_already_joined(page) -> bool:
    joined_status = page.locator("p.joined[role='status']")
    return joined_status.count() > 0 and joined_status.first.is_visible()


def try_join_giveaway(user_data_str: str, headless: bool = True) -> tuple[str, str]:
    """
    Returns (status, detail_message) where status is one of:
      - "already_joined"
      - "joined"
      - "failed"
    """
    profile_dir = Path("/tmp/rblx_profile_alok").resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            viewport={"width": 1366, "height": 820},
            locale="en-US",
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )

        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.set_default_timeout(15000)

            log(f"[Alok49x] Opening {BASE_URL} to set session (headless={headless})...")
            page.goto(BASE_URL, wait_until="domcontentloaded")

            inject_local_storage(page, user_data_str)

            log(f"[Alok49x] Navigating to {GIVEAWAY_URL}...")
            page.goto(GIVEAWAY_URL, wait_until="domcontentloaded")
            human_sleep(2.5, 4.0)

            if "/giveaway" not in page.url:
                log(f"[Alok49x] Redirected to {page.url}; navigating back to {GIVEAWAY_URL}...")
                page.goto(GIVEAWAY_URL, wait_until="domcontentloaded")
                human_sleep(2.0, 3.5)

            found_button = False
            deadline = time.time() + 15
            while time.time() < deadline:
                if is_already_joined(page):
                    log("[Alok49x] Status: Joined already ('You're in this draw. Good luck!').")
                    return "already_joined", "Already in this draw."

                btn = page.locator("button.re-btn", has_text="Join giveaway").first
                if btn.count() > 0 and btn.is_visible() and btn.is_enabled():
                    found_button = True
                    break

                time.sleep(0.5)

            if not found_button:
                msg = f"Could not find Join button or Joined banner (URL: {page.url})."
                log(f"[Alok49x] Status: {msg}")
                return "failed", msg

            btn = page.locator("button.re-btn", has_text="Join giveaway").first
            btn.scroll_into_view_if_needed(timeout=5000)
            human_sleep(0.6, 1.3)

            box = btn.bounding_box(timeout=3000)
            if box:
                target_x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
                target_y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
                page.mouse.move(target_x, target_y, steps=random.randint(8, 16))
                human_sleep(0.2, 0.6)

            btn.click(timeout=5000)
            log("[Alok49x] Clicked 'Join giveaway' button. Waiting for confirmation...")

            confirm_deadline = time.time() + 15
            while time.time() < confirm_deadline:
                if is_already_joined(page):
                    log("[Alok49x] Status: Joined! ('You're in this draw. Good luck!').")
                    human_sleep(1.0, 2.0)
                    return "joined", "Successfully joined the new giveaway draw!"
                time.sleep(0.5)

            msg = "Clicked Join button, but confirmation banner did not appear within 15s."
            log(f"[Alok49x] Status: {msg}")
            return "failed", msg

        except Exception as exc:
            msg = f"Error: {exc}"
            log(f"[Alok49x] {msg}")
            return "failed", msg
        finally:
            context.close()


def main() -> None:
    status, detail = try_join_giveaway(user_data_str=ALOK_USER_DATA, headless=True)

    if status == "joined":
        send_discord(f"✅ **[Alok49x]** {detail}")
        sys.exit(0)
    elif status == "already_joined":
        send_discord(f"ℹ️ **[Alok49x]** {detail}")
        sys.exit(0)
    else:
        send_discord(f"❌ **[Alok49x]** Giveaway check failed — {detail}")
        sys.exit(1)


if __name__ == "__main__":
    main()
