import random
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "https://rblx.earth"
GIVEAWAY_URL = "https://rblx.earth/giveaway"

# Alok49x session only
ALOK_USER_DATA = '{"username":"Alok49x","_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyYmx4VXNlcm5hbWUiOiJBbG9rNDl4IiwicmJseElkIjoiMTE0MDg1Mzk1NjUiLCJpYXQiOjE3OTUxNjM3MzR9.G6bOIKIorc1BZ5kYSQsmlx5zP9SDIXg2TH25u6alIGc","_robux":"1.43","_thumbnail":"https://tr.rbxcdn.com/30DAY-AvatarBust-051F4476AFFD563E8DFB42984F606CE5-Png/420/420/AvatarBust/Png/noFilter","_adminToken":""}'


def log(msg: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


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


def try_join_giveaway(user_data_str: str, headless: bool = True) -> str:
    """
    Returns one of:
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
                    return "already_joined"

                btn = page.locator("button.re-btn", has_text="Join giveaway").first
                if btn.count() > 0 and btn.is_visible() and btn.is_enabled():
                    found_button = True
                    break

                time.sleep(0.5)

            if not found_button:
                log(f"[Alok49x] Status: Could not find Join button or Joined banner (URL: {page.url}).")
                return "failed"

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
                    return "joined"
                time.sleep(0.5)

            log("[Alok49x] Status: Clicked button, but confirmation banner did not appear within 15s.")
            return "failed"

        except Exception as exc:
            log(f"[Alok49x] Error during attempt: {exc}")
            return "failed"
        finally:
            context.close()


def main() -> None:
    status = try_join_giveaway(user_data_str=ALOK_USER_DATA, headless=True)
    sys.exit(0 if status in ("joined", "already_joined") else 1)


if __name__ == "__main__":
    main()