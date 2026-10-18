import json
import os
from playwright.sync_api import sync_playwright

PANEL_URL = "https://panel.fps.ms"


def run():
    session_raw = os.environ.get("FPS_SESSION_DATA")

    if not session_raw:
        print("Error: FPS_SESSION_DATA secret is missing in environment.")
        return

    try:
        cookies = json.loads(session_raw)
    except Exception as e:
        print(f"Error parsing session JSON: {e}")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        # حقن الكوكيز المعتمدة
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
            print(f"Injected {len(formatted_cookies)} session cookies successfully.")
        except Exception as e:
            print(f"Failed to inject cookies: {e}")
            return

        page = context.new_page()

        try:
            print("Navigating to panel dashboard...")
            page.goto(PANEL_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)

            if "auth/login" in page.url:
                print("FAILED: Session expired. Please re-export cookies from your browser.")
                return

            # البحث عن السيرفر في اللوحة
            server_links = page.locator('a[href*="/server/"]')
            server_count = server_links.count()

            if server_count == 0:
                print("No servers found on the dashboard.")
                page.screenshot(path="server_status.png", full_page=True)
                return

            first_server_href = server_links.first.get_attribute("href")
            server_full_url = (
                first_server_href
                if first_server_href.startswith("http")
                else f"https://panel.fps.ms{first_server_href}"
            )
            print(f"Opening server page: {server_full_url}")

            # الانتقال لصفحة السيرفر
            page.goto(server_full_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(6000)

            print(f"Server page title: {page.title()}")

            # فحص النصوص المتعلقة بانتهاء الصلاحية والتجديد
            page_text = page.inner_text("body")
            expiry_lines = [
                line.strip()
                for line in page_text.split("\n")
                if any(kw in line.lower() for kw in ["expir", "renew", "hour", "time left"])
            ]
            if expiry_lines:
                print("Detected server timer / status:")
                for line in expiry_lines[:4]:
                    print(f"  - {line}")

            # البحث عن زر التجديد (+ Add XX Hours أو Renew)
            renew_buttons = page.locator('button:has-text("Add"), button:has-text("Renew"), button:has-text("Hours")')
            btn_count = renew_buttons.count()
            print(f"Found {btn_count} candidate renewal button(s).")

            renewed = False
            for i in range(btn_count):
                btn = renew_buttons.nth(i)
                btn_text = btn.inner_text().strip().replace("\n", " ")
                is_disabled = btn.is_disabled()
                is_visible = btn.is_visible()
                print(f"  - Button {i+1}: '{btn_text}' (visible={is_visible}, disabled={is_disabled})")

                if is_visible and not is_disabled and any(kw in btn_text.lower() for kw in ["add", "renew"]):
                    print(f"Clicking renewal button: '{btn_text}'...")
                    btn.click()
                    page.wait_for_timeout(4000)
                    renewed = True
                    break

            if renewed:
                print("SUCCESS: Server renewal executed successfully!")
            else:
                print("INFO: Renewal button not clickable right now (server time is still above renewal threshold).")

            # التقاط صورة شاشة لحالة السيرفر
            page.screenshot(path="server_status.png", full_page=True)
            print("Saved screenshot to server_status.png.")

        finally:
            browser.close()


if __name__ == "__main__":
    run()
