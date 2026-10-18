
import os
from playwright.sync_api import sync_playwright

EMAIL = os.environ.get("FPS_EMAIL")
PASSWORD = os.environ.get("FPS_PASSWORD")


def run():
    if not EMAIL or not PASSWORD:
        raise RuntimeError("Missing GitHub Secrets")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            print("Opening FPS login page...")
            page.goto(
                "https://fps.ms/login",
                wait_until="domcontentloaded",
                timeout=60000,
            )

            print("Login page loaded.")
            print("Checking for human verification...")

            challenge = page.locator(
                'iframe[src*="challenges.cloudflare.com"]'
            )

            if challenge.count() > 0:
                print("Human verification detected. Stopping.")
                return

            print(
                "Initial check complete. "
                "Login and renewal selectors need verification."
            )

        finally:
            browser.close()


if __name__ == "__main__":
    run()
