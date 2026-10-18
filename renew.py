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

        # حقن الكوكيز في المتصفح
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
            print("Navigating directly to panel dashboard...")
            response = page.goto(
                PANEL_URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )
            page.wait_for_timeout(5000)

            print("HTTP status:", response.status if response else "unknown")
            current_url = page.url
            print("Current URL:", current_url)
            print("Page title:", page.title())

            if "auth/login" in current_url:
                print("FAILED: Session expired or rejected. Redirected to login page.")
            else:
                print("SUCCESS: Session valid! Reached server panel dashboard.")

                # البحث عن روابط السيرفرات في اللوحة
                server_links = page.locator('a[href*="/server/"]')
                count = server_links.count()
                print(f"Found {count} server link(s) on dashboard.")

                for i in range(count):
                    link = server_links.nth(i)
                    href = link.get_attribute("href")
                    text = link.inner_text().strip().replace("\n", " ")
                    print(f"  - Server {i+1}: {text} -> {href}")

        finally:
            browser.close()


if __name__ == "__main__":
    run()
