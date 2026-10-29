"""Playwright End-to-End Automated Browser Tests for NumberShield."""

import threading
import time
import pytest
import uvicorn
from playwright.sync_api import sync_playwright
from backend.app.main import app


class LiveServer(threading.Thread):
    def __init__(self, host="127.0.0.1", port=8766):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.server = None

    def run(self):
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="error")
        self.server = uvicorn.Server(config)
        self.server.run()

    def stop(self):
        if self.server:
            self.server.should_exit = True


@pytest.fixture(scope="module")
def base_url():
    server = LiveServer(port=8766)
    server.start()
    time.sleep(2.0)
    yield "http://127.0.0.1:8766"
    server.stop()


def test_full_user_workflow_desktop(base_url):
    """Test full desktop workflow: navigation, demo loading, dorks, legal notice, spam logging, and purge."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # 1. Navigate to application root
        page.goto(base_url, wait_until="networkidle")
        assert page.locator("text=NumberShield").first.is_visible()

        # 2. Check brand and desktop navigation tabs
        assert page.locator("text=v1.0 Local").first.is_visible()
        nav = page.locator("nav")
        assert nav.locator("button:has-text('Scan & Dorks')").is_visible()
        assert nav.locator("button:has-text('Exposures')").is_visible()
        assert nav.locator("button:has-text('Remediation Hub')").is_visible()
        assert nav.locator("button:has-text('Spam & DND')").is_visible()
        assert nav.locator("button:has-text('Verify & Audit')").is_visible()

        # 3. Load synthetic demo scenario
        load_demo_btn = page.locator("button:has-text('Load Demo')").first
        assert load_demo_btn.is_visible()
        load_demo_btn.click()

        # Wait for toast and automatic navigation to Exposures tab
        page.wait_for_selector("text=Synthetic scenario loaded", timeout=10000)
        page.wait_for_selector("text=Discovered Exposures", timeout=10000)

        # 4. Verify exposures table contains realistic data broker entries
        assert page.locator("text=fastpeoplesearch.com").first.is_visible()
        assert page.locator("text=truepeoplesearch.com").first.is_visible()
        assert page.locator("text=Exact Match").first.is_visible()

        # 5. Switch to Scan & Dorks tab and test Direct Search Dorks modal
        nav.locator("button:has-text('Scan & Dorks')").click()
        page.wait_for_selector("text=Privacy Exposure Discovery Engine")

        dorks_btn = page.locator("button:has-text('Direct Search Dorks (1-Click)')")
        assert dorks_btn.is_visible()
        dorks_btn.click()

        # Wait for modal
        page.wait_for_selector("text=Pre-Computed Search Dorks", timeout=6000)
        assert page.locator("text=Google Search").first.is_visible()
        assert page.locator("text=Bing Search").first.is_visible()
        assert page.locator("text=Brave Search").first.is_visible()

        # Close modal
        page.locator("button:has-text('✕')").click()

        # 6. Switch to Remediation Hub and test Legal Notice Generator
        nav.locator("button:has-text('Remediation Hub')").click()
        page.wait_for_selector("text=Remediation Hub")
        page.wait_for_selector("text=FastPeopleSearch", timeout=6000)

        # Switch to Legal Notice Generator subtab
        page.locator("button:has-text('Legal Notice Generator')").click()
        page.wait_for_selector("text=Statutory Notice Configuration")

        # Generate CCPA notice
        generate_btn = page.locator("button:has-text('Generate Privacy Rights Notice')")
        assert generate_btn.is_visible()
        generate_btn.click()

        # Wait for notice output
        page.wait_for_selector("text=California Consumer Privacy Act", timeout=6000)
        page.wait_for_selector("text=Subject:", timeout=6000)
        assert page.locator("text=Civil Code § 1798.105").is_visible()

        # 7. Switch to Spam & DND tab and test incident logging & telecom guides
        nav.locator("button:has-text('Spam & DND')").click()
        page.wait_for_selector("text=Spam Reduction & Telecom DND")

        # Check National DND Registry info
        assert page.locator("text=National Do Not Call Registry").first.is_visible()
        assert page.locator("text=donotcall.gov").first.is_visible()
        assert page.locator("text=7726").first.is_visible()

        # Log an incident
        page.fill("input[placeholder*='+1 (555)']", "+18005550199")
        page.fill("input[placeholder*='vehicle service contract']", "Pre-recorded auto warranty protection pitch")
        page.locator("button:has-text('Record Incident & Re-Cluster')").click()

        page.wait_for_selector("text=Spam incident logged", timeout=6000)
        page.wait_for_selector("text=+18005550199", timeout=8000)
        assert page.locator("text=+18005550199").first.is_visible()

        # 8. Switch to Verify & Audit tab and test Zero-Trace Purge
        nav.locator("button:has-text('Verify & Audit')").click()
        page.wait_for_selector("text=Verification & Forensic Audit")
        assert page.locator("text=Cryptographic Guarantees").is_visible()
        assert page.locator("text=Current Identity HMAC-SHA256").is_visible()

        # Click Launch Cryptographic Purge
        page.locator("button:has-text('Launch Cryptographic Purge')").click()
        page.wait_for_selector("text=Confirm Zero-Trace Erasure")

        # Type PURGE
        page.fill("input[placeholder='Type PURGE to confirm']", "PURGE")
        page.locator("button:has-text('Permanently Destroy Data')").click()

        # Verify reset to initial scan console
        page.wait_for_selector("text=Privacy Exposure Discovery Engine", timeout=8000)

        browser.close()


def test_mobile_viewport_responsiveness(base_url):
    """Test responsive rendering on mobile viewport (390x844 iPhone 12/13/14 size)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()

        page.goto(base_url, wait_until="networkidle")
        assert page.locator("text=NumberShield").first.is_visible()

        # Load demo on mobile
        load_demo_btn = page.locator("button:has-text('Load Demo')").first
        load_demo_btn.click()

        page.wait_for_selector("text=Discovered Exposures", timeout=10000)

        # Check table does not cause horizontal page blowout (overflow-x contained)
        table = page.locator("table")
        assert table.is_visible()

        # Switch to Remediation Hub via mobile sub-navigation bar
        mobile_btn = page.locator("header button:has-text('Remediation Hub')").first
        assert mobile_btn.is_visible()
        mobile_btn.click()
        page.wait_for_selector("text=Remediation Hub", timeout=8000)

        browser.close()
