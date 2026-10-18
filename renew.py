import os
from playwright.sync_api import sync_playwright

LOGIN_URL = "https://panel.fps.ms"


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            response = page.goto(
                LOGIN_URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            # مهلة قصيرة لاكتمال تحميل واجهة جافاسكربت
            page.wait_for_timeout(5000)

            print("HTTP status:", response.status if response else "unknown")
            print("Page title:", page.title())
            print("Current URL:", page.url)

            # فحص كل حقول الإدخال ومعرفة أسمائها وأنواعها
            input_count = page.locator("input").count()
            print(f"Total input fields: {input_count}")
            for i in range(input_count):
                inp = page.locator("input").nth(i)
                inp_type = inp.get_attribute("type") or "text"
                inp_name = inp.get_attribute("name") or "unnamed"
                placeholder = inp.get_attribute("placeholder") or ""
                print(f"  - Input {i+1}: type='{inp_type}', name='{inp_name}', placeholder='{placeholder}'")

            # فحص الأزرار ونصوصها
            button_count = page.locator("button").count()
            print(f"Total buttons: {button_count}")
            for i in range(button_count):
                btn = page.locator("button").nth(i)
                btn_type = btn.get_attribute("type") or ""
                btn_text = btn.inner_text().strip().replace("\n", " ")
                print(f"  - Button {i+1}: type='{btn_type}', text='{btn_text}'")

            print("Page inspection completed.")

        finally:
            browser.close()


if __name__ == "__main__":
    run()
