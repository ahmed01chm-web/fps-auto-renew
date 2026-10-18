import os
from playwright.sync_api import sync_playwright

LOGIN_URL = "https://panel.fps.ms/auth/login"


def run():
    email = os.environ.get("FPS_EMAIL")
    password = os.environ.get("FPS_PASSWORD")

    if not email or not password:
        print("Error: FPS_EMAIL or FPS_PASSWORD secret is missing in environment.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            print("Navigating to login page...")
            response = page.goto(
                LOGIN_URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )
            page.wait_for_timeout(3000)

            print("Initial HTTP status:", response.status if response else "unknown")

            # 1. إغلاق إشعار الكوكيز إن وجد لتفريغ الشاشة
            accept_btn = page.locator('button:has-text("Accept optional")')
            if accept_btn.count() > 0 and accept_btn.is_visible():
                print("Accepting optional cookies...")
                accept_btn.click()
                page.wait_for_timeout(1000)

            # 2. تعبئة بيانات الدخول
            print("Filling credentials...")
            page.fill('input[name="username"]', email)
            page.fill('input[name="password"]', password)

            # 3. فحص حالة التحقق من Cloudflare Turnstile
            page.wait_for_timeout(4000)
            turnstile_input = page.locator('input[name="cf-turnstile-response"]')
            token = turnstile_input.get_attribute("value") if turnstile_input.count() > 0 else ""
            print("Turnstile token generated automatically:", bool(token))

            # 4. الضغط على زر تسجيل الدخول
            print("Clicking Sign in button...")
            page.click('button[type="submit"]')

            # 5. انتظار النتيجة وفحص الرابط الناتج
            page.wait_for_timeout(6000)
            current_url = page.url
            print("URL after login attempt:", current_url)
            print("Page title after login attempt:", page.title())

            # 6. فحص ما إذا كانت هناك رسائل خطأ معروضة بالصفحة
            alerts = page.locator('[role="alert"], [class*="error"], [class*="alert"]').all_inner_texts()
            if alerts:
                clean_alerts = [a.strip() for a in alerts if a.strip()]
                if clean_alerts:
                    print("Page alerts/messages:", clean_alerts)

            if "auth/login" not in current_url:
                print("SUCCESS: Logged in successfully! Reached dashboard/server panel.")
            else:
                print("STILL ON LOGIN: Did not redirect. Review token or credentials.")

        finally:
            browser.close()


if __name__ == "__main__":
    run()
