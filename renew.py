import json
import logging
import os
import sys
import time
from playwright.sync_api import sync_playwright

PANEL_URL = "https://panel.fps.ms"
LOG_FILE = "renew_activity.log"
SCREENSHOT_FILE = "server_status.png"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)


def run():
    logging.info("=== Starting FPS Auto-Renew Execution ===")

    session_raw = os.environ.get("FPS_SESSION_DATA")
    if not session_raw:
        logging.error("FPS_SESSION_DATA secret is missing in environment variables.")
        return

    try:
        cookies = json.loads(session_raw)
        logging.info("Session JSON successfully parsed.")
    except Exception as e:
        logging.error(f"Error parsing session JSON: {e}")
        return

    with sync_playwright() as p:
        logging.info("Launching Chromium instance with stealth parameters...")
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-size=1920,1080",
            ],
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )

        # 1. حقن الكوكيز الخاصة بالجلسة
        try:
            formatted_cookies = []
            for c in cookies:
                domain = c.get("domain", "panel.fps.ms")
                if domain.startswith("."):
                    domain = domain[1:]
                formatted_cookies.append({
                    "name": c.get("name"),
                    "value": c.get("value"),
                    "domain": domain,
                    "path": c.get("path", "/"),
                })
            context.add_cookies(formatted_cookies)
            logging.info(f"Injected {len(formatted_cookies)} cookies successfully.")
        except Exception as e:
            logging.error(f"Failed to inject cookies: {e}")
            browser.close()
            return

        page = context.new_page()

        try:
            logging.info(f"Navigating to dashboard: {PANEL_URL}")
            page.goto(PANEL_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)

            # التحقق من صلاحية الجلسة
            if "auth/login" in page.url:
                logging.error("FAILED: Session expired. Update FPS_SESSION_DATA secret.")
                page.screenshot(path=SCREENSHOT_FILE, full_page=True)
                return

            server_links = page.locator('a[href*="/server/"]')
            if server_links.count() == 0:
                logging.warning("No servers detected on the dashboard.")
                page.screenshot(path=SCREENSHOT_FILE, full_page=True)
                return

            first_server_href = server_links.first.get_attribute("href")
            server_full_url = (
                first_server_href
                if first_server_href.startswith("http")
                else f"https://panel.fps.ms{first_server_href}"
            )
            logging.info(f"Opening target server console: {server_full_url}")

            page.goto(server_full_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)

            # 2. الضغط على زر التجديد أولاً لإطلاق تحدي الكابتشا (Trigger)
            renew_btn = page.locator('button:has-text("Renew Now"), button:has-text("Add")').first
            if renew_btn.count() > 0 and renew_btn.is_visible():
                logging.info("Found renewal button. Clicking to trigger verification challenge...")
                renew_btn.click(force=True)
                page.wait_for_timeout(4000)
            else:
                logging.info("No active renewal button visible at the moment.")

            # 3. التفاعل مع مربع كابتشا Cloudflare Turnstile إن وُجد
            try:
                page.wait_for_selector('iframe[src*="cloudflare"], iframe[src*="turnstile"]', timeout=8000)
                frame = page.frame_locator('iframe[src*="cloudflare"], iframe[src*="turnstile"]')
                box = frame.locator('input[type="checkbox"], #challenge-stage, .ctp-checkbox-label')
                if box.count() > 0 and box.first.is_visible():
                    logging.info("Clicking Cloudflare Turnstile verification checkbox...")
                    box.first.click()
            except Exception:
                logging.info("No interactive checkbox required; background verification running.")

            # 4. مراقبة الـ DOM كل 15 ثانية (حتى 5.5 دقيقة) للتأكد من التجديد
            logging.info("Monitoring DOM state for auto-renewal confirmation (up to 5.5 minutes)...")
            max_wait_seconds = 330
            interval = 15
            elapsed = 0
            renewed = False

            while elapsed < max_wait_seconds:
                page_text = page.inner_text("body").lower()

                # فحص الـ DOM: هل اختفت عبارة انتهاء السيرفر أو ظهر عداد وقت إضافي؟
                is_expired = "free server expired" in page_text or "has expired" in page_text
                has_timer = any(kw in page_text for kw in ["24h", "23h", "hours left", "expires in", "valid until"])

                if not is_expired or has_timer:
                    logging.info(f"SUCCESS: Server renewed automatically! Detected DOM change after {elapsed}s.")
                    renewed = True
                    break

                logging.info(f"Waiting for security token confirmation... ({elapsed}/{max_wait_seconds}s)")
                page.wait_for_timeout(interval * 1000)
                elapsed += interval

            if not renewed:
                logging.warning("Wait duration completed without detecting state change. Check status image.")

            # 5. فحص حالة السيرفر وتشغيله عبر زر (Start) إذا كان متوقفاً
            logging.info("Checking server power state...")
            page.wait_for_timeout(2000)
            start_btn = page.locator('button:has-text("Start")').first
            if start_btn.count() > 0 and start_btn.is_visible() and start_btn.is_enabled():
                if start_btn.inner_text().strip().lower() == "start":
                    logging.info("Server is currently stopped. Sending 'Start' command...")
                    start_btn.click(force=True)
                    page.wait_for_timeout(5000)
                    logging.info("Start signal dispatched successfully.")
            else:
                logging.info("Server is already running or Start button is not actionable.")

            # حفظ لقطة الشاشة النهائية لحالة اللوحة
            page.screenshot(path=SCREENSHOT_FILE, full_page=True)
            logging.info("Final dashboard screenshot saved to server_status.png.")

        except Exception as e:
            logging.error(f"Runtime execution error: {e}", exc_info=True)
            page.screenshot(path=SCREENSHOT_FILE, full_page=True)
        finally:
            browser.close()

    logging.info("=== Finished Execution Successfully ===")


if __name__ == "__main__":
    run()
