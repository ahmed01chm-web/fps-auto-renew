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
        logging.info("Launching Chromium instance...")
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--window-size=1920,1080",
            ],
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )

        # حقن الكوكيز
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
            logging.info(f"Navigating to: {PANEL_URL}")
            page.goto(PANEL_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)

            if "auth/login" in page.url:
                logging.error("FAILED: Session expired. Re-export cookies.")
                page.screenshot(path=SCREENSHOT_FILE, full_page=True)
                return

            server_links = page.locator('a[href*="/server/"]')
            if server_links.count() == 0:
                logging.warning("No servers found on dashboard.")
                page.screenshot(path=SCREENSHOT_FILE, full_page=True)
                return

            first_server_href = server_links.first.get_attribute("href")
            server_full_url = (
                first_server_href
                if first_server_href.startswith("http")
                else f"https://panel.fps.ms{first_server_href}"
            )
            logging.info(f"Navigating to server console: {server_full_url}")

            page.goto(server_full_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)

            # 1. مراقبة الكابتشا وزر التجديد (حتى 5.5 دقيقة)
            logging.info("Checking renewal requirements and waiting for security check...")
            renew_btn = page.locator('button:has-text("Renew Now"), button:has-text("Add")').first

            max_wait_seconds = 330  # 5 دقائق ونصف كحد أقصى
            interval = 15
            elapsed = 0
            renewed = False

            if renew_btn.count() > 0:
                while elapsed < max_wait_seconds:
                    if renew_btn.is_visible() and renew_btn.is_enabled():
                        logging.info(f"Verification complete! Renewal button is active after {elapsed}s. Clicking...")
                        renew_btn.click(force=True)
                        page.wait_for_timeout(5000)
                        renewed = True
                        break
                    
                    logging.info(f"Security verification in progress... ({elapsed}/{max_wait_seconds}s)")
                    page.wait_for_timeout(interval * 1000)
                    elapsed += interval

                if not renewed:
                    logging.info("Renewal button did not become actionable within timeout (or already renewed).")
            else:
                logging.info("No renewal button present on the page.")

            # 2. فحص وتشغيل السيرفر (Start) إذا كان مطفأ
            logging.info("Checking server power state...")
            page.wait_for_timeout(3000)

            start_btn = page.locator('button:has-text("Start")').first
            if start_btn.count() > 0 and start_btn.is_visible() and start_btn.is_enabled():
                btn_text = start_btn.inner_text().strip().lower()
                if btn_text == "start":
                    logging.info("Server is offline. Clicking 'Start' button...")
                    start_btn.click(force=True)
                    page.wait_for_timeout(5000)
                    logging.info("Start signal sent successfully.")
            else:
                logging.info("Server is already running or start button is unavailable.")

            # حفظ لقطة الشاشة النهائية
            page.screenshot(path=SCREENSHOT_FILE, full_page=True)
            logging.info("Final screenshot saved to server_status.png.")

        except Exception as e:
            logging.error(f"Runtime error occurred: {e}", exc_info=True)
            page.screenshot(path=SCREENSHOT_FILE, full_page=True)
        finally:
            browser.close()

    logging.info("=== Finished Execution Successfully ===")


if __name__ == "__main__":
    run()
