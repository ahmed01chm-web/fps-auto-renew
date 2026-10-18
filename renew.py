
import os
from playwright.sync_api import sync_playwright

LOGIN_URL = "https://fps.ms/login"


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

            print("HTTP status:", response.status if response else "unknown")
            print("Page title:", page.title())
            print("Current URL:", page.url)

            print(
                "Email fields:",
                page.locator('input[type="email"]').count(),
            )
            print(
                "Password fields:",
                page.locator('input[type="password"]').count(),
            )
            print(
                "Submit buttons:",
                page.locator('button[type="submit"]').count(),
            )

            print("Page inspection completed.")

        finally:
            browser.close()


if __name__ == "__main__":
    run()
