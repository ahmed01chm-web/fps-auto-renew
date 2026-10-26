import json
import logging
import os
import sys
from playwright.sync_api import sync_playwright

PANEL_URL = "https://panel.fps.ms"
LOG_FILE = "renew_activity.log"

# إعداد الـ Logging لكتابة المخرجات في الكونسول وملف اللوج معاً
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
        logging.info("Launching headless Chromium...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        # حقن الكوكيز
        try:
            formatted_cookies = []
            for c in cookies:
                domain = c.get("domain", "panel.fps.ms")
                if domain.startswith("."):
                    domain = domain[1:]
                formatted_cookies.append(
                    {
                        "name": c.get("name"),
                        "value": c.get("value"),
                        "domain": domain,
                        "path": c.get("path", "/"),
                    }
                )
            context.add_cookies(formatted_cookies)
            logging.info(
                f"Injected {len(formatted_cookies)} session cookies successfully."
            )
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
                logging.error(
                    "FAILED: Session expired / redirected to login. Re-export cookies from your browser."
                )
                page.screenshot(path="server_status.png", full_page=True)
                return

            # البحث عن السيرفر في اللوحة
            server_links = page.locator('a[href*="/server/"]')
            server_count = server_links.count()

            if server_count == 0:
                logging.warning(
                    "No server cards found on the dashboard. Capturing view..."
                )
                page.screenshot(path="server_status.png", full_page=True)
                return

            first_server_href = server_links.first.get_attribute("href")
            server_full_url = (
                first_server_href
                if first_server_href.startswith("http")
                else f"https://panel.fps.ms{first_server_href}"
            )
            logging.info(f"Opening target server: {server_full_url}")

            page.goto(server_full_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(6000)

            logging.info(f"Page reached. Title: '{page.title()}'")

            # 1. فحص التوقيت المتبقي
            page_text = page.inner_text("body")
            expiry_lines = [
                line.strip()
                for line in page_text.split("\n")
                if any(
                    kw in line.lower()
                    for kw in ["expir", "renew", "hour", "time left"]
                )
            ]
            if expiry_lines:
                logging.info("Detected server status indicators:")
                for line in expiry_lines[:4]:
                    logging.info(f"  -> {line}")

            # 2. فحص والضغط على زر التجديد
            renew_buttons = page.locator(
                'button:has-text("Add"), button:has-text("Renew"), button:has-text("Hours")'
            )
            renewed = False
            for i in range(renew_buttons.count()):
                btn = renew_buttons.nth(i)
                btn_text = btn.inner_text().strip().replace("\n", " ")
                if btn.is_visible() and btn.is_enabled() and any(
                    kw in btn_text.lower() for kw in ["add", "renew"]
                ):
                    logging.info(f"Found active renewal button: '{btn_text}'. Clicking...")
                    btn.click()
                    page.wait_for_timeout(4000)
                    renewed = True
                    break

            if renewed:
                logging.info("SUCCESS: Server renewal clicked and confirmed!")
            else:
                logging.info(
                    "INFO: Renewal button is not actionable yet (time is still high)."
                )

            # 3. فحص والضغط على زر Start إن كان متوقفاً
            start_buttons = page.locator('button:has-text("Start")')
            started = False
            for i in range(start_buttons.count()):
                btn = start_buttons.nth(i)
                btn_text = btn.inner_text().strip()
                if (
                    btn.is_visible()
                    and btn.is_enabled()
                    and btn_text.lower() == "start"
                ):
                    logging.info("Server is offline. Pressing 'Start'...")
                    btn.click()
                    page.wait_for_timeout(4000)
                    started = True
                    break

            if started:
                logging.info("SUCCESS: 'Start' trigger sent successfully.")
            else:
                logging.info("INFO: Server is already running or start is disabled.")

            # حفظ لقطة الشاشة
            page.screenshot(path="server_status.png", full_page=True)
            logging.info("Status screenshot saved to 'server_status.png'.")

        except Exception as e:
            logging.error(f"Execution runtime error: {e}", exc_info=True)
            page.screenshot(path="server_status.png", full_page=True)
        finally:
            logging.info("Closing browser context.")
            browser.close()

    logging.info("=== Finished Execution Successfully ===")


if __name__ == "__main__":
    run()
